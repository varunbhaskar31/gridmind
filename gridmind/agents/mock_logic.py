"""Deterministic rule-based mock logic for GridMind agents.

Guarantees 100% offline functionality without API keys or external services,
producing identical Pydantic schemas and exercising the exact same tools and math.
"""

from typing import Any, Dict, List
import yaml
from pathlib import Path

from gridmind.agents.schemas import (
    CandidatePlanSummary,
    Explanation,
    MonitorReport,
    Signal,
    StrategyDecision,
)
from gridmind.forecast.forecaster import ForecastResult
from gridmind.optimize.milp import DispatchPlan, MilpOptimizer
from gridmind.optimize.risk import evaluate_plan_risk, get_conservative_plan
from gridmind.sim.state import DispatchAction, GridState


def mock_monitor_report(
    signals: List[Signal],
    severity: str,
    replan_required: bool,
    active_events: List[Any],
) -> MonitorReport:
    """Generate deterministic situation summary from telemetry signals."""
    if active_events:
        event_names = ", ".join(e.event_type for e in active_events)
        summary = (
            f"Active grid events detected: {event_names}. Operational conditions disturbed; "
            f"monitoring asset availability and reserve constraints."
        )
    elif severity in ["high", "critical"]:
        high_signals = [s.description for s in signals if abs(s.delta_pct) > 20.0]
        s_desc = "; ".join(high_signals[:2]) if high_signals else "Significant telemetry divergence"
        summary = f"Significant operational deviation detected: {s_desc}. Immediate dispatch replan recommended."
    elif severity == "medium":
        summary = "Moderate telemetry variation observed across solar/wind outputs and exchange price."
    else:
        summary = "Portfolio operating smoothly within nominal bounds. Generation and customer loads balanced."

    return MonitorReport(
        severity=severity,
        signals=signals,
        summary=summary,
        replan_required=replan_required,
    )


def mock_strategy_decision(
    current_state: GridState,
    forecast: ForecastResult,
    optimizer: MilpOptimizer,
    agent_config: Dict[str, Any],
) -> StrategyDecision:
    """Deterministic strategist using rule table, tool execution, and risk scoring."""
    # 1. Determine Mode from operational rule table
    has_storm = any(
        e.event_type == "storm_alert" for e in current_state.active_events
    ) or any(
        e.event_type == "storm_alert" for e in getattr(current_state, "announced_events", [])
    )
    has_battery_outage = any(not avail for avail in current_state.battery_available.values())
    is_line_constrained = current_state.grid_export_limit_mw < 150.0
    is_high_price = current_state.price_actual > 6500.0

    if has_storm:
        mode = "storm_preparation"
    elif has_battery_outage:
        mode = "outage_recovery"
    elif is_line_constrained:
        mode = "congestion_management"
    elif is_high_price:
        mode = "economic"
    else:
        mode = "green"

    # 2. Extract preset weights and reserve floor from agent.yaml
    mode_cfg = agent_config.get("modes", {}).get(mode, {})
    preferred_weights = mode_cfg.get(
        "weights",
        {"cost": 1.0, "carbon": 1.0, "curtailment": 1.0, "degradation": 1.0, "reliability": 1.0},
    )
    reserve_floor = float(mode_cfg.get("reserve_floor", 0.15))

    # 3. Execute Candidate 1: Preferred Mode Plan
    plan_pref = optimizer.solve(
        current_state=current_state,
        forecast=forecast,
        weights=preferred_weights,
        reserve_floor=reserve_floor,
        terminal_soc_target=reserve_floor,
    )

    # 4. Execute Candidate 2: Conservative Robust Plan
    plan_cons = get_conservative_plan(
        optimizer=optimizer,
        current_state=current_state,
        forecast=forecast,
        reserve_floor=max(0.35, reserve_floor),
    )

    # 5. Risk Evaluation via Monte Carlo tool
    risk_pref = evaluate_plan_risk(
        plan_pref, forecast, optimizer.batteries, optimizer.consumers
    )
    risk_cons = evaluate_plan_risk(
        plan_cons, forecast, optimizer.batteries, optimizer.consumers
    )

    # Risk scoring: expected_cost + 1.0 * p_shortfall * shortfall_penalty (₹15,000)
    score_pref = risk_pref.expected_cost_inr + (risk_pref.p_shortfall * 15000.0)
    score_cons = risk_cons.expected_cost_inr + (risk_cons.p_shortfall * 15000.0)

    # In storm preparation or outage recovery, always default to conservative
    if mode in ["storm_preparation", "outage_recovery"] or score_cons < score_pref:
        chosen_plan = plan_cons
        chosen_risk = risk_cons
        chosen_weights = {
            "cost": 1.0, "carbon": 0.5, "curtailment": 0.5, "degradation": 0.5, "reliability": 5.0
        }
        chosen_floor = max(0.35, reserve_floor)
        tradeoff = (
            f"Chosen conservative plan costs ₹{risk_cons.expected_cost_inr:,.0f} expected (vs ₹{risk_pref.expected_cost_inr:,.0f}), "
            f"reducing contract shortfall risk to {risk_cons.p_shortfall*100:.1f}% (vs {risk_pref.p_shortfall*100:.1f}%)."
        )
    else:
        chosen_plan = plan_pref
        chosen_risk = risk_pref
        chosen_weights = preferred_weights
        chosen_floor = reserve_floor
        tradeoff = (
            f"Chosen preferred {mode} plan costs ₹{risk_pref.expected_cost_inr:,.0f} expected with "
            f"{risk_pref.p_shortfall*100:.1f}% shortfall probability and min SoC {min(risk_pref.min_soc_reached.values())*100:.0f}%."
        )

    candidates = [
        CandidatePlanSummary(
            plan_id=plan_pref.plan_id,
            weights=preferred_weights,
            expected_cost=risk_pref.expected_cost_inr,
            p_shortfall=risk_pref.p_shortfall,
            p_unserved=risk_pref.p_unserved,
            min_soc=min(risk_pref.min_soc_reached.values()),
        ),
        CandidatePlanSummary(
            plan_id=plan_cons.plan_id,
            weights={"cost": 1.0, "carbon": 0.5, "curtailment": 0.5, "degradation": 0.5, "reliability": 5.0},
            expected_cost=risk_cons.expected_cost_inr,
            p_shortfall=risk_cons.p_shortfall,
            p_unserved=risk_cons.p_unserved,
            min_soc=min(risk_cons.min_soc_reached.values()),
        ),
    ]

    # Operator approval criteria (Section 8.5)
    first_act = chosen_plan.first_interval
    dr_total = sum(first_act.demand_response.values())
    is_selling_during_storm = has_storm and first_act.grid_export > 1e-3
    is_deep_soc_discharge = any(
        (chosen_plan.soc_trajectory[b][0] / float(optimizer.batteries[b]["energy_mwh"])) < 0.25
        for b in optimizer.batteries
    )

    req_approval = bool(
        dr_total > 30.0 or is_selling_during_storm or is_deep_soc_discharge
    )

    rationale = (
        f"Selected {mode.replace('_', ' ')} strategy to navigate current conditions. "
        f"Weights balanced for reliable customer supply with reserve floor at {chosen_floor*100:.0f}%."
    )

    return StrategyDecision(
        mode=mode,
        weights=chosen_weights,
        reserve_floor=chosen_floor,
        terminal_soc_target=chosen_floor,
        chosen_plan_id=chosen_plan.plan_id,
        candidates_considered=candidates,
        tradeoff_statement=tradeoff,
        confidence="high",
        requires_operator_approval=req_approval,
        rationale=rationale,
    )


def mock_explanation(
    decision: StrategyDecision,
    action: DispatchAction,
    state: GridState,
) -> Explanation:
    """Generate template-based operator explanation citing concrete numbers."""
    b_ch = sum(action.battery_charge.values())
    b_dis = sum(action.battery_discharge.values())
    net_grid = action.grid_import - action.grid_export

    if b_ch > 1.0:
        bess_action = f"charging batteries at {b_ch:.1f} MW"
    elif b_dis > 1.0:
        bess_action = f"discharging batteries at {b_dis:.1f} MW"
    else:
        bess_action = "holding batteries on standby"

    if net_grid > 1.0:
        grid_action = f"importing {net_grid:.1f} MW from grid"
    elif net_grid < -1.0:
        grid_action = f"exporting {-net_grid:.1f} MW to market"
    else:
        grid_action = "balanced with zero grid exchange"

    headline = f"Dispatched in {decision.mode.replace('_', ' ')} mode: {bess_action}."
    what_we_did = f"Commanded {bess_action} and {grid_action} while serving contracted loads."
    why = decision.rationale
    tradeoff = decision.tradeoff_statement
    what_would_change_our_mind = (
        "Sudden price drop below ₹3,000/MWh or cancellation of the active disturbance alert."
    )

    return Explanation(
        headline=headline[:100],
        what_we_did=what_we_did,
        why=why,
        tradeoff=tradeoff,
        what_would_change_our_mind=what_would_change_our_mind,
    )
