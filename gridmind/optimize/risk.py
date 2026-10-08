"""Monte Carlo risk evaluation and robust plan synthesis.

1. evaluate_plan(plan, scenarios):
   Replays candidate dispatch plans across N sampled forecast scenarios with simple recourse.
   Returns expected cost, P90 cost, probability of contract shortfall, and VOLL risk.

2. get_conservative_plan(...):
   Synthesizes a robust defensive candidate using pessimistic inputs (P10 renewables, P90 demand, P90 prices).
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np

from gridmind.forecast.forecaster import ForecastResult, ForecastScenario
from gridmind.optimize.milp import DispatchPlan, MilpOptimizer
from gridmind.sim.state import GridState


@dataclass
class PlanRiskMetrics:
    """Risk and robustness profile of a candidate dispatch plan across N scenarios."""
    plan_id: str
    expected_cost_inr: float
    p90_cost_inr: float
    p_shortfall: float               # Probability (0.0 - 1.0) of any contract shortfall
    p_unserved: float                # Probability (0.0 - 1.0) of any unserved critical load
    expected_curtailment_mwh: float
    min_soc_reached: Dict[str, float]


def evaluate_plan_risk(
    plan: DispatchPlan,
    forecast: ForecastResult,
    battery_specs: Dict[str, Dict[str, Any]],
    consumer_specs: Dict[str, Dict[str, Any]],
    eval_intervals: int = 16,        # Evaluate first 4 hours of decisions
) -> PlanRiskMetrics:
    """Evaluate candidate plan against forecast scenarios with realistic recourse.

    Recourse logic:
    - Attempt candidate's battery dispatch.
    - If scenario has renewable deficit relative to plan: cover with imports up to line limit,
      then contract shortfall up to non-critical limit, then VOLL unserved load.
    - If scenario has surplus: export up to line limit, then curtail.
    """
    if not plan.is_feasible:
        return PlanRiskMetrics(
            plan_id=plan.plan_id,
            expected_cost_inr=99999999.0,
            p90_cost_inr=99999999.0,
            p_shortfall=1.0,
            p_unserved=1.0,
            expected_curtailment_mwh=0.0,
            min_soc_reached={b: 0.0 for b in battery_specs},
        )

    scenarios = forecast.scenarios
    if not scenarios:
        return PlanRiskMetrics(
            plan_id=plan.plan_id,
            expected_cost_inr=plan.objective_terms.get("cost", 0.0),
            p90_cost_inr=plan.objective_terms.get("cost", 0.0),
            p_shortfall=0.0,
            p_unserved=0.0,
            expected_curtailment_mwh=0.0,
            min_soc_reached={b: 0.5 for b in battery_specs},
        )

    num_scenarios = len(scenarios)
    K = min(eval_intervals, len(plan.horizon_actions), forecast.horizon_intervals)
    dt = 0.25  # 15 minutes

    scenario_costs: List[float] = []
    shortfall_occurred: List[bool] = []
    unserved_occurred: List[bool] = []
    curtailment_totals: List[float] = []
    min_socs: Dict[str, List[float]] = {b: [] for b in battery_specs}

    for sc in scenarios:
        sc_cost = 0.0
        has_shortfall = False
        has_unserved = False
        sc_curt = 0.0

        # Track battery SoC in this scenario
        b_soc = {b: plan.soc_trajectory[b][0] if plan.soc_trajectory[b] else 100.0 for b in battery_specs}

        for t in range(K):
            act = plan.horizon_actions[t]

            # Scenario generation and demand realizations
            sc_re = sum(sc.solar[s][t] for s in sc.solar) + sum(sc.wind[w][t] for w in sc.wind)
            sc_dem = sum(sc.demand[c][t] for c in sc.demand)
            price = sc.price[t]

            # Battery planned power
            b_ch = sum(act.battery_charge.values())
            b_dis = sum(act.battery_discharge.values())

            # Net physical balance before grid exchange
            net_energy = sc_re + b_dis - b_ch - sc_dem

            t_cost = 0.0
            if net_energy >= 0:
                # Surplus power: export up to line limit, curtail remainder
                exp_lim = sc.export_limit[t]
                grid_exp = min(exp_lim, net_energy)
                curt = net_energy - grid_exp
                sc_curt += curt * dt
                t_cost -= grid_exp * price * 0.97 * dt
                t_cost += curt * dt * 1000.0  # Curtailment penalty
            else:
                # Deficit power: import up to line limit, then shortfall, then VOLL
                deficit = -net_energy
                imp_lim = sc.import_limit[t]
                grid_imp = min(imp_lim, deficit)
                rem_def = deficit - grid_imp
                t_cost += grid_imp * price * dt

                if rem_def > 1e-4:
                    # Distribute across non-critical loads
                    total_non_crit = sum(
                        sc.demand[c][t] * (1.0 - float(consumer_specs[c].get("critical_fraction", 0.5)))
                        for c in sc.demand
                    )
                    short = min(total_non_crit, rem_def)
                    unserv = rem_def - short

                    if short > 1e-3:
                        has_shortfall = True
                        t_cost += short * dt * 15000.0
                    if unserv > 1e-3:
                        has_unserved = True
                        t_cost += unserv * dt * 100000.0

            # Battery degradation cost
            t_cost += (b_ch + b_dis) * dt * 500.0
            sc_cost += t_cost

        scenario_costs.append(sc_cost)
        shortfall_occurred.append(has_shortfall)
        unserved_occurred.append(has_unserved)
        curtailment_totals.append(sc_curt)

    expected_cost = float(np.mean(scenario_costs))
    p90_cost = float(np.percentile(scenario_costs, 90))
    p_shortfall = float(np.mean(shortfall_occurred))
    p_unserved = float(np.mean(unserved_occurred))
    exp_curt = float(np.mean(curtailment_totals))

    min_soc_summary = {
        b: min([min(plan.soc_trajectory[b])] if plan.soc_trajectory.get(b) else [0.5])
        / float(battery_specs[b]["energy_mwh"])
        for b in battery_specs
    }

    return PlanRiskMetrics(
        plan_id=plan.plan_id,
        expected_cost_inr=round(expected_cost, 2),
        p90_cost_inr=round(p90_cost, 2),
        p_shortfall=round(p_shortfall, 3),
        p_unserved=round(p_unserved, 3),
        expected_curtailment_mwh=round(exp_curt, 2),
        min_soc_reached=min_soc_summary,
    )


def get_conservative_plan(
    optimizer: MilpOptimizer,
    current_state: GridState,
    forecast: ForecastResult,
    reserve_floor: float = 0.35,
) -> DispatchPlan:
    """Solve MILP using pessimistic inputs: P10 renewables, P90 demand, P90 prices.

    Yields a defensive, highly reliable candidate plan for comparison against aggressive plans.
    """
    # Create pessimistic synthetic forecast object
    pessimistic_fcst = ForecastResult(
        horizon_intervals=forecast.horizon_intervals,
        lead_hours=forecast.lead_hours,
        timestamps=forecast.timestamps,
        solar_p50=forecast.solar_p10,       # Low solar
        wind_p50=forecast.wind_p10,         # Low wind
        demand_p50=forecast.demand_p90,     # High demand
        price_p50=forecast.price_p90,       # High purchase price
        solar_p10=forecast.solar_p10,
        solar_p90=forecast.solar_p90,
        wind_p10=forecast.wind_p10,
        wind_p90=forecast.wind_p90,
        demand_p10=forecast.demand_p10,
        demand_p90=forecast.demand_p90,
        price_p10=forecast.price_p10,
        price_p90=forecast.price_p90,
        export_limit=forecast.export_limit,
        import_limit=forecast.import_limit,
        scenarios=[],
    )

    robust_weights = {
        "cost": 1.0,
        "carbon": 0.5,
        "curtailment": 0.5,
        "degradation": 0.5,
        "reliability": 5.0,  # Max reliability focus
    }

    return optimizer.solve(
        current_state=current_state,
        forecast=pessimistic_fcst,
        weights=robust_weights,
        reserve_floor=reserve_floor,
        terminal_soc_target=0.35,
    )
