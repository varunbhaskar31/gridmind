"""The primary 15-minute rolling control orchestrator for GridMind.

Coordinates the end-to-end autonomous cycle across every time step:
1. Environment state retrieval from Simulator
2. Forecast generation via Forecaster (P10, P50, P90)
3. Anomaly and disturbance detection via MonitorAgent
4. Strategic decision making via StrategyAgent (with candidate plan comparison)
5. Pre-execution safety validation via GuardrailValidator
6. Operator approval / override handling
7. Physical actuation via DispatchExecutor
8. Human-interpretable shift briefings via ExplainerAgent
9. Structured JSONL audit logging via DecisionLogger
10. Continuous KPI tracking via MetricsTracker

Supports:
- Headless execution for N intervals or full datasets
- Single-step advancement for dashboard interactive mode
- Pause / resume / reset capabilities
- Mid-run dynamic event injection
- Manual operator approval gates and action overrides
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

from gridmind.agents.explainer import ExplainerAgent
from gridmind.agents.llm_client import LLMClient
from gridmind.agents.mock_logic import mock_explanation
from gridmind.agents.monitor import MonitorAgent
from gridmind.agents.schemas import Explanation, MonitorReport, StrategyDecision
from gridmind.agents.strategist import StrategyAgent
from gridmind.executor import DispatchExecutor
from gridmind.forecast.forecaster import Forecaster
from gridmind.guard.guardrails import GuardrailValidator, ValidationResult
from gridmind.logging_utils import DecisionLogger
from gridmind.metrics import MetricsTracker, PortfolioMetrics
from gridmind.optimize.heuristics import safe_mode_dispatch
from gridmind.optimize.milp import DispatchPlan, MilpOptimizer
from gridmind.sim.events import Event
from gridmind.sim.simulator import Simulator
from gridmind.sim.state import DispatchAction, GridState


@dataclass
class StepResult:
    """Complete summary of a single 15-minute orchestration step."""
    interval_index: int
    timestamp: str
    state: GridState
    report: MonitorReport
    decision: StrategyDecision
    plan: DispatchPlan
    validation: ValidationResult
    executed_action: DispatchAction
    explanation: Explanation
    metrics: PortfolioMetrics
    is_safe_mode: bool = False
    strategy_refreshed: bool = True
    waiting_for_approval: bool = False


class GridMindOrchestrator:
    """The central agentic renewable energy portfolio orchestrator."""

    def __init__(
        self,
        dataset_path: Path,
        assets_config_path: Path,
        market_config_path: Path,
        agent_config_path: Path,
        llm_client: Optional[LLMClient] = None,
        run_id: Optional[str] = None,
        logs_dir: Optional[Path] = None,
        auto_approve_operator: bool = True,
        strategy_refresh_interval: int = 4,  # refresh every 1 hour (4 x 15-min) unless anomaly triggered
    ) -> None:
        self.dataset_path = dataset_path
        self.assets_config_path = assets_config_path
        self.market_config_path = market_config_path
        self.agent_config_path = agent_config_path

        # Load configurations
        with open(assets_config_path, "r", encoding="utf-8") as f:
            self.assets_cfg = yaml.safe_load(f)
        with open(market_config_path, "r", encoding="utf-8") as f:
            self.market_cfg = yaml.safe_load(f)
        with open(agent_config_path, "r", encoding="utf-8") as f:
            self.agent_cfg = yaml.safe_load(f)

        self.auto_approve = auto_approve_operator
        self.strategy_refresh_interval = strategy_refresh_interval

        # Core engines
        self.simulator = Simulator(dataset_path, assets_config_path, market_config_path)
        self.executor = DispatchExecutor(self.simulator)
        self.forecaster = Forecaster(dataset_path, assets_config_path, market_config_path, horizon_intervals=32)
        self.optimizer = MilpOptimizer(assets_config_path, market_config_path)
        self.guardrail = GuardrailValidator(assets_config_path, market_config_path)

        # Agentic Intelligence layer
        self.llm_client = llm_client or LLMClient()
        self.monitor = MonitorAgent(agent_config_path, self.llm_client)
        self.strategist = StrategyAgent(agent_config_path, self.optimizer, self.guardrail, self.llm_client)
        self.explainer = ExplainerAgent(self.llm_client)

        # Logging and Metrics
        self.logger = DecisionLogger(logs_dir=logs_dir, run_id=run_id)
        self.batteries_dict = {b["id"]: b for b in self.assets_cfg["batteries"]}
        self.consumers_dict = {c["id"]: c for c in self.assets_cfg["consumers"]}
        self.metrics_tracker = MetricsTracker(
            batteries_config=self.batteries_dict,
            consumers_config=self.consumers_dict,
            emission_factor_tco2_per_mwh=float(
                self.market_cfg["carbon"].get("grid_emission_factor_tco2_per_mwh", 0.71)
            ),
            carbon_price_inr_per_tco2=float(self.market_cfg["carbon"].get("carbon_price_inr_per_tco2", 1500.0)),
            shortfall_penalty_inr=float(
                self.market_cfg["penalties"].get("contract_shortfall_inr_per_mwh", 15000.0)
            ),
            voll_inr=float(self.market_cfg["penalties"].get("value_of_lost_load_inr_per_mwh", 100000.0)),
        )

        # Internal state
        self.is_paused: bool = False
        self.last_decision: Optional[StrategyDecision] = None
        self.last_mode: Optional[str] = None
        self.pending_approval: Optional[StepResult] = None
        self.history: List[StepResult] = []

    def reset(self) -> GridState:
        """Reset orchestrator, simulator, metrics tracker, and internal history."""
        self.is_paused = False
        self.last_decision = None
        self.last_mode = None
        self.pending_approval = None
        self.history.clear()
        self.metrics_tracker.reset()
        return self.simulator.reset()

    def inject_event(self, event: Event) -> None:
        """Inject a disturbance or announcement mid-simulation."""
        self.simulator.inject_event(event)

    def pause(self) -> None:
        """Pause rolling execution."""
        self.is_paused = True

    def resume(self) -> None:
        """Resume rolling execution."""
        self.is_paused = False

    def step(self, operator_override_action: Optional[DispatchAction] = None) -> StepResult:
        """Advance the orchestrator by one 15-minute interval."""
        state = self.simulator.current_state()
        curr_int = state.interval_index

        # 1. Forecast state over rolling horizon
        forecast = self.forecaster.forecast(
            current_state=state,
            event_manager=self.simulator.event_manager,
            num_scenarios=5,
            seed=42 + curr_int,
        )

        # 2. Monitor telemetry & detect deviations
        report = self.monitor.run(state, forecast)

        # 3. Strategy Refresh Evaluation
        strategy_refreshed = False
        if (
            self.last_decision is None
            or report.replan_required
            or (curr_int % self.strategy_refresh_interval == 0)
        ):
            strategy_refreshed = True
            decision, plan, val = self.strategist.run(report, state, forecast)
            self.last_decision = decision
        else:
            # Re-run optimizer with active decision weights and parameters
            decision = self.last_decision
            plan = self.optimizer.solve(
                current_state=state,
                forecast=forecast,
                weights=decision.weights,
                reserve_floor=decision.reserve_floor,
                terminal_soc_target=decision.terminal_soc_target,
            )
            val = self.guardrail.validate(plan, state)

        # 4. Fallback if Guardrail rejected
        is_safe = False
        if not val.passed:
            is_safe = True
            safe_act = safe_mode_dispatch(state, self.batteries_dict, self.consumers_dict)
            action = safe_act
        else:
            action = plan.first_interval

        # Apply operator override if provided
        if operator_override_action is not None:
            action = operator_override_action

        # Check operator approval gate if required and auto-approval disabled
        if decision.requires_operator_approval and not self.auto_approve and operator_override_action is None:
            # Stage result and pause
            pending = StepResult(
                interval_index=curr_int,
                timestamp=state.timestamp,
                state=state,
                report=report,
                decision=decision,
                plan=plan,
                validation=val,
                executed_action=action,
                explanation=Explanation(
                    headline="Awaiting operator confirmation for high-impact dispatch",
                    what_we_did="Holding dispatch pending manual approval",
                    why="Action flagged for required operator oversight",
                    tradeoff="Slight delay in dispatch actuation",
                    what_would_change_our_mind="Operator approves or overrides dispatch setpoints",
                ),
                metrics=self.metrics_tracker.current_metrics(),
                is_safe_mode=is_safe,
                strategy_refreshed=strategy_refreshed,
                waiting_for_approval=True,
            )
            self.pending_approval = pending
            return pending

        # 5. Actuate dispatch action on simulator
        next_state = self.executor.apply(action)

        # 6. Generate operator explanation
        if strategy_refreshed or report.severity in ["high", "critical"] or is_safe:
            explanation = self.explainer.run(decision, action, state)
        else:
            explanation = mock_explanation(decision, action, state)

        self.last_mode = decision.mode

        # 7. Update metrics tracker
        kpis = self.metrics_tracker.record_interval(
            grid_import_mw=action.grid_import,
            grid_export_mw=action.grid_export,
            price_actual=state.price_actual,
            solar_actual_mw=sum(state.solar_actual.values()),
            wind_actual_mw=sum(state.wind_actual.values()),
            curtailment_mw=sum(action.solar_curtailment.values()) + sum(action.wind_curtailment.values()),
            battery_charge=action.battery_charge,
            battery_discharge=action.battery_discharge,
            demand_response=action.demand_response,
            contract_shortfall=action.contract_shortfall,
            unserved_critical=action.unserved_critical,
            hard_violations=len(val.violations) if not val.passed else 0,
            is_safe_mode=is_safe,
            solve_time_sec=plan.solve_time_seconds,
            llm_called=not self.llm_client.is_mock,
            fallback_used=self.llm_client.fallback_count > 0,
        )

        # 8. Record structured JSONL log
        self.logger.log_interval(
            interval_index=curr_int,
            timestamp=state.timestamp,
            state=state,
            monitor_report=report,
            strategy_decision=decision,
            guardrail_result=val,
            action=action,
            explanation=explanation,
            metrics_snapshot=kpis.to_dict(),
            is_safe_mode=is_safe,
            strategy_refreshed=strategy_refreshed,
        )

        result = StepResult(
            interval_index=curr_int,
            timestamp=state.timestamp,
            state=next_state,
            report=report,
            decision=decision,
            plan=plan,
            validation=val,
            executed_action=action,
            explanation=explanation,
            metrics=kpis,
            is_safe_mode=is_safe,
            strategy_refreshed=strategy_refreshed,
            waiting_for_approval=False,
        )
        self.history.append(result)
        return result

    def run_headless(self, num_intervals: Optional[int] = None) -> PortfolioMetrics:
        """Run the simulation loop headlessly until completion or step limit."""
        steps_to_run = (
            num_intervals
            if num_intervals is not None
            else (self.simulator.total_intervals - self.simulator.current_interval_idx)
        )
        for _ in range(steps_to_run):
            if self.is_paused or self.simulator.is_done():
                break
            self.step()
        return self.metrics_tracker.current_metrics()
