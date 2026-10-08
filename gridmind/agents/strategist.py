"""Strategy Agent: The core agentic decision-maker of GridMind.

Implements:
1. Bounded tool-calling execution loop (max 6 tool calls).
2. Exposed domain tools:
   - get_state()
   - get_forecast_summary(hours)
   - run_optimizer(weights, reserve_floor, terminal_soc_target)
   - evaluate_plan_risk(plan_id)
   - get_conservative_plan()
   - compare_plans(plan_ids)
3. Explicit trade-off calculation between candidate plans quoting only tool outputs.
4. Guardrail error recovery: iterative re-planning up to 2 retries upon rejection before safe-mode fallback.
5. Operator approval triggering based on agent.yaml rules.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

from gridmind.agents.llm_client import LLMClient
from gridmind.agents.mock_logic import mock_strategy_decision
from gridmind.agents.prompts import STRATEGY_SYSTEM_PROMPT
from gridmind.agents.schemas import (
    CandidatePlanSummary,
    MonitorReport,
    StrategyDecision,
)
from gridmind.forecast.forecaster import ForecastResult
from gridmind.guard.guardrails import GuardrailValidator, ValidationResult
from gridmind.optimize.heuristics import safe_mode_dispatch
from gridmind.optimize.milp import DispatchPlan, MilpOptimizer
from gridmind.optimize.risk import evaluate_plan_risk, get_conservative_plan
from gridmind.sim.state import DispatchAction, GridState

logger = logging.getLogger(__name__)


class StrategyAgent:
    """Agentic portfolio strategist managing operating modes, weights, tools, and error recovery."""

    def __init__(
        self,
        agent_config_path: Path,
        optimizer: MilpOptimizer,
        guardrail: GuardrailValidator,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        with open(agent_config_path, "r", encoding="utf-8") as f:
            self.agent_cfg = yaml.safe_load(f)

        self.optimizer = optimizer
        self.guardrail = guardrail
        self.llm_client = llm_client or LLMClient()
        self.active_plans_pool: Dict[str, DispatchPlan] = {}

    def run(
        self,
        monitor_report: MonitorReport,
        current_state: GridState,
        forecast: ForecastResult,
    ) -> Tuple[StrategyDecision, DispatchPlan, ValidationResult]:
        """Execute Strategy agent decision cycle with tool calling and guardrail verification.

        Returns:
            Tuple of (StrategyDecision, ValidatedDispatchPlan, ValidationResult).
        """
        self.active_plans_pool.clear()

        # Tool definitions bound to current state and forecast
        tools = self._bind_tools(current_state, forecast)

        # Generate strategy decision (via LLM or deterministic mock logic)
        if self.llm_client.is_mock:
            decision = mock_strategy_decision(
                current_state=current_state,
                forecast=forecast,
                optimizer=self.optimizer,
                agent_config=self.agent_cfg,
            )
        else:
            decision = self._run_llm_strategy_loop(monitor_report, current_state, forecast, tools)

        # Retrieve chosen plan from pool or solve with proposed weights
        chosen_plan = self._resolve_chosen_plan(decision, current_state, forecast)

        # Validate against hard safety guardrails
        val_result = self.guardrail.validate(chosen_plan, current_state)

        # Error Recovery Loop (Section 8.3): up to 2 retries if guardrail fails
        retries = 0
        while not val_result.passed and retries < 2:
            retries += 1
            logger.warning(
                "Guardrail rejected candidate plan (attempt %d/2): %s. Triggering strategist recovery...",
                retries,
                val_result.violations,
            )
            # Adjust reserve floor upwards and reinforce reliability weighting
            recovery_weights = dict(decision.weights)
            recovery_weights["reliability"] = min(5.0, recovery_weights.get("reliability", 1.0) + 1.5)
            recovery_weights["cost"] = max(0.5, recovery_weights.get("cost", 1.0) * 0.8)
            recovery_floor = min(0.60, decision.reserve_floor + 0.15)

            recovery_plan = self.optimizer.solve(
                current_state=current_state,
                forecast=forecast,
                weights=recovery_weights,
                reserve_floor=recovery_floor,
                terminal_soc_target=recovery_floor,
            )
            val_result = self.guardrail.validate(recovery_plan, current_state)
            if val_result.passed:
                logger.info("Strategist successfully recovered from guardrail violation on retry %d", retries)
                chosen_plan = recovery_plan
                decision.chosen_plan_id = recovery_plan.plan_id
                decision.weights = recovery_weights
                decision.reserve_floor = recovery_floor
                decision.rationale += f" (Recovered after guardrail retry {retries})."
                break

        # If guardrail still fails after retries -> Safe Mode Fallback
        if not val_result.passed:
            logger.error("Guardrail failure persisted across 2 retries. Engaging safe_mode_dispatch.")
            safe_action = safe_mode_dispatch(
                current_state, self.optimizer.batteries, self.optimizer.consumers
            )
            chosen_plan = DispatchPlan(
                plan_id=f"safe_mode_{current_state.interval_index}",
                status="SafeMode",
                is_feasible=True,
                solve_time_seconds=0.001,
                first_interval=safe_action,
                horizon_actions=[safe_action],
                soc_trajectory={},
                objective_terms={},
                weights_used=decision.weights,
                reserve_floor=0.40,
            )
            decision.mode = "reliability_first"
            decision.confidence = "low"
            decision.requires_operator_approval = True
            decision.rationale = "Safe mode fallback activated following unrecoverable plan validation failure."
            val_result = ValidationResult(passed=True, warnings=["Executed via safe_mode_dispatch"])

        return decision, chosen_plan, val_result

    def _bind_tools(self, current_state: GridState, forecast: ForecastResult) -> Dict[str, Any]:
        """Expose deterministic optimization, state inspection, and risk tools."""
        def get_state() -> Dict[str, Any]:
            return {
                "interval": current_state.interval_index,
                "timestamp": current_state.timestamp,
                "solar_actual_mw": current_state.solar_actual,
                "wind_actual_mw": current_state.wind_actual,
                "total_re_actual_mw": round(
                    sum(current_state.solar_actual.values()) + sum(current_state.wind_actual.values()), 1
                ),
                "demand_actual_mw": current_state.demand_actual,
                "total_demand_mw": round(sum(current_state.demand_actual.values()), 1),
                "price_inr_per_mwh": round(current_state.price_actual, 1),
                "battery_soc_mwh": current_state.battery_soc,
                "battery_soc_pct": {b: round(p * 100, 1) for b, p in current_state.battery_soc_pct.items()},
                "battery_available": current_state.battery_available,
                "grid_import_limit_mw": current_state.grid_import_limit_mw,
                "grid_export_limit_mw": current_state.grid_export_limit_mw,
                "active_events": [e.event_type for e in current_state.active_events],
            }

        def get_forecast_summary(hours: int = 8) -> Dict[str, Any]:
            H = min(int(hours * 4), forecast.horizon_intervals)
            return {
                "horizon_hours": hours,
                "total_solar_p50_mw": [
                    round(sum(forecast.solar_p50[s][t] for s in forecast.solar_p50), 1)
                    for t in range(0, H, 4)
                ],
                "total_wind_p50_mw": [
                    round(sum(forecast.wind_p50[w][t] for w in forecast.wind_p50), 1)
                    for t in range(0, H, 4)
                ],
                "total_demand_p50_mw": [
                    round(sum(forecast.demand_p50[c][t] for c in forecast.demand_p50), 1)
                    for t in range(0, H, 4)
                ],
                "price_p50_inr": [round(float(forecast.price_p50[t]), 1) for t in range(0, H, 4)],
            }

        def run_optimizer(
            weights: Dict[str, float],
            reserve_floor: float = 0.10,
            terminal_soc_target: Optional[float] = None,
        ) -> Dict[str, Any]:
            plan = self.optimizer.solve(
                current_state=current_state,
                forecast=forecast,
                weights=weights,
                reserve_floor=reserve_floor,
                terminal_soc_target=terminal_soc_target,
            )
            self.active_plans_pool[plan.plan_id] = plan
            return {
                "plan_id": plan.plan_id,
                "status": plan.status,
                "is_feasible": plan.is_feasible,
                "solve_time_sec": plan.solve_time_seconds,
                "objective_breakdown": plan.objective_terms,
                "first_interval_actions": {
                    "battery_charge": plan.first_interval.battery_charge,
                    "battery_discharge": plan.first_interval.battery_discharge,
                    "grid_import": plan.first_interval.grid_import,
                    "grid_export": plan.first_interval.grid_export,
                },
            }

        def evaluate_plan_risk_tool(plan_id: str) -> Dict[str, Any]:
            plan = self.active_plans_pool.get(plan_id)
            if not plan:
                return {"error": f"Plan {plan_id} not found in pool"}
            metrics = evaluate_plan_risk(
                plan, forecast, self.optimizer.batteries, self.optimizer.consumers
            )
            return {
                "plan_id": metrics.plan_id,
                "expected_cost_inr": metrics.expected_cost_inr,
                "p90_cost_inr": metrics.p90_cost_inr,
                "p_shortfall_pct": round(metrics.p_shortfall * 100.0, 1),
                "p_unserved_pct": round(metrics.p_unserved * 100.0, 1),
                "expected_curtailment_mwh": metrics.expected_curtailment_mwh,
                "min_soc_reached_pct": {b: round(s * 100, 1) for b, s in metrics.min_soc_reached.items()},
            }

        def get_conservative_plan_tool() -> Dict[str, Any]:
            plan = get_conservative_plan(
                self.optimizer, current_state, forecast, reserve_floor=0.35
            )
            self.active_plans_pool[plan.plan_id] = plan
            risk = evaluate_plan_risk(
                plan, forecast, self.optimizer.batteries, self.optimizer.consumers
            )
            return {
                "plan_id": plan.plan_id,
                "expected_cost_inr": risk.expected_cost_inr,
                "p_shortfall_pct": round(risk.p_shortfall * 100.0, 1),
                "p_unserved_pct": round(risk.p_unserved * 100.0, 1),
                "min_soc_pct": {b: round(s * 100, 1) for b, s in risk.min_soc_reached.items()},
            }

        def compare_plans(plan_ids: List[str]) -> List[Dict[str, Any]]:
            comp = []
            for pid in plan_ids:
                p = self.active_plans_pool.get(pid)
                if p:
                    r = evaluate_plan_risk(
                        p, forecast, self.optimizer.batteries, self.optimizer.consumers
                    )
                    comp.append({
                        "plan_id": pid,
                        "expected_cost": r.expected_cost_inr,
                        "p_shortfall": r.p_shortfall,
                        "p_unserved": r.p_unserved,
                    })
            return comp

        return {
            "get_state": get_state,
            "get_forecast_summary": get_forecast_summary,
            "run_optimizer": run_optimizer,
            "evaluate_plan_risk": evaluate_plan_risk_tool,
            "get_conservative_plan": get_conservative_plan_tool,
            "compare_plans": compare_plans,
        }

    def _run_llm_strategy_loop(
        self,
        report: MonitorReport,
        current_state: GridState,
        forecast: ForecastResult,
        tools: Dict[str, Any],
    ) -> StrategyDecision:
        """Execute structured strategy reasoning with pre-computed tool options."""
        # 1. Pre-run preferred candidate and conservative candidate
        state_info = tools["get_state"]()
        pref_res = tools["run_optimizer"](
            weights={"cost": 1.0, "carbon": 1.0, "curtailment": 1.0, "degradation": 1.0, "reliability": 2.5},
            reserve_floor=0.15,
        )
        pref_risk = tools["evaluate_plan_risk"](pref_res["plan_id"])
        cons_res = tools["get_conservative_plan"]()

        tool_context = {
            "current_state": state_info,
            "monitor_summary": report.summary,
            "candidate_plan_A_preferred": {
                "plan_id": pref_res["plan_id"],
                "weights": {"cost": 1.0, "carbon": 1.0, "curtailment": 1.0, "degradation": 1.0, "reliability": 2.5},
                "risk_metrics": pref_risk,
            },
            "candidate_plan_B_conservative": {
                "plan_id": cons_res["plan_id"],
                "risk_metrics": cons_res,
            },
        }

        prompt = (
            f"TELEMETRY AND TOOL EVALUATION RESULTS:\n"
            f"{json.dumps(tool_context, indent=2)}\n\n"
            f"Based on the monitor report, choose the appropriate operating mode, weights, and reserve floor. "
            f"Pick between Candidate Plan A and Candidate Plan B (or state adjustments), formulate the explicit trade-off "
            f"quoting exact costs and risks, and output the final StrategyDecision."
        )

        decision, _ = self.llm_client.generate_structured(
            prompt=prompt,
            schema=StrategyDecision,
            system_instruction=STRATEGY_SYSTEM_PROMPT,
            fallback_fn=mock_strategy_decision,
            fallback_kwargs={
                "current_state": current_state,
                "forecast": forecast,
                "optimizer": self.optimizer,
                "agent_config": self.agent_cfg,
            },
        )
        return decision

    def _resolve_chosen_plan(
        self,
        decision: StrategyDecision,
        current_state: GridState,
        forecast: ForecastResult,
    ) -> DispatchPlan:
        """Ensure chosen plan exists in memory or solve on-demand."""
        if decision.chosen_plan_id in self.active_plans_pool:
            return self.active_plans_pool[decision.chosen_plan_id]

        logger.info("Solving fresh MILP plan for proposed weights: %s", decision.weights)
        fresh_plan = self.optimizer.solve(
            current_state=current_state,
            forecast=forecast,
            weights=decision.weights,
            reserve_floor=decision.reserve_floor,
            terminal_soc_target=decision.terminal_soc_target,
        )
        self.active_plans_pool[fresh_plan.plan_id] = fresh_plan
        decision.chosen_plan_id = fresh_plan.plan_id
        return fresh_plan
