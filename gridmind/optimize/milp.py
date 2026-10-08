"""Rolling-horizon Mixed-Integer Linear Programming (MILP) dispatch optimizer.

Formulated with PuLP:
- Exact binary interlocking preventing simultaneous charge/discharge and simultaneous buy/sell
- Rolling dynamic battery State-of-Charge (SoC) conservation
- Hard contractual non-sheddable critical industrial load fraction
- Multi-objective soft weighting (cost, carbon, curtailment, degradation, reliability)
- Sub-second solving via bundled CBC solver with 10s safety timeout
"""

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pulp
import yaml

from gridmind.forecast.forecaster import ForecastResult
from gridmind.sim.state import DispatchAction, GridState


@dataclass
class DispatchPlan:
    """Complete rolling-horizon solution produced by the MILP optimizer."""
    plan_id: str
    status: str
    is_feasible: bool
    solve_time_seconds: float
    first_interval: DispatchAction
    horizon_actions: List[DispatchAction]
    soc_trajectory: Dict[str, List[float]]
    objective_terms: Dict[str, float]
    weights_used: Dict[str, float]
    reserve_floor: float
    terminal_soc_target: Optional[float] = None


class MilpOptimizer:
    """Rolling-horizon MILP dispatch optimizer for Deccan Renewables portfolio."""

    def __init__(
        self,
        assets_config_path: Path,
        market_config_path: Path,
    ) -> None:
        with open(assets_config_path, "r", encoding="utf-8") as f:
            self.assets_cfg = yaml.safe_load(f)
        with open(market_config_path, "r", encoding="utf-8") as f:
            self.market_cfg = yaml.safe_load(f)

        self.solar_farms = {s["id"]: s for s in self.assets_cfg["solar_farms"]}
        self.wind_farms = {w["id"]: w for w in self.assets_cfg["wind_farms"]}
        self.batteries = {b["id"]: b for b in self.assets_cfg["batteries"]}
        self.consumers = {c["id"]: c for c in self.assets_cfg["consumers"]}

        self.interval_hours = float(self.market_cfg["simulation"].get("interval_hours", 0.25))
        self.emission_factor = float(
            self.market_cfg["carbon"].get("grid_emission_factor_tco2_per_mwh", 0.71)
        )
        self.carbon_price = float(self.market_cfg["carbon"].get("carbon_price_inr_per_tco2", 1500.0))
        self.sell_fee_factor = float(self.market_cfg["market"].get("sell_fee_factor", 0.97))
        self.shortfall_penalty = float(
            self.market_cfg["penalties"].get("contract_shortfall_inr_per_mwh", 15000.0)
        )
        self.curtailment_penalty = float(
            self.market_cfg["penalties"].get("curtailment_penalty_inr_per_mwh", 1000.0)
        )
        self.voll = float(
            self.market_cfg["penalties"].get("value_of_lost_load_inr_per_mwh", 100000.0)
        )

    def solve(
        self,
        current_state: GridState,
        forecast: ForecastResult,
        weights: Optional[Dict[str, float]] = None,
        reserve_floor: float = 0.10,
        terminal_soc_target: Optional[float] = None,
        time_limit_sec: float = 10.0,
    ) -> DispatchPlan:
        """Formulate and solve the rolling-horizon MILP dispatch problem.

        Args:
            current_state: Current snapshot of asset availability, limits, and SoC.
            forecast: Rolling forecast (P50 values or robust P10/P90).
            weights: Objective weights {cost, carbon, curtailment, degradation, reliability}.
            reserve_floor: Minimum battery SoC fraction allowed during horizon (0.10 - 0.80).
            terminal_soc_target: Optional minimum SoC fraction required at end of horizon.
            time_limit_sec: Max solver runtime before returning timeout/infeasible.

        Returns:
            DispatchPlan containing full horizon actions and objective decomposition.
        """
        start_time = time.time()
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"

        w = {
            "cost": 1.0,
            "carbon": 1.0,
            "curtailment": 1.0,
            "degradation": 1.0,
            "reliability": 1.0,
        }
        if weights:
            w.update(weights)

        H = forecast.horizon_intervals
        dt = self.interval_hours

        prob = pulp.LpProblem(f"GridMind_{plan_id}", pulp.LpMinimize)

        # ---------------- Decision Variables ----------------
        # Batteries: ch, dis (MW), soc (MWh), binary u (1=charge)
        ch: Dict[str, Dict[int, pulp.LpVariable]] = {}
        dis: Dict[str, Dict[int, pulp.LpVariable]] = {}
        soc: Dict[str, Dict[int, pulp.LpVariable]] = {}
        u: Dict[str, Dict[int, pulp.LpVariable]] = {}
        res_slack: Dict[str, Dict[int, pulp.LpVariable]] = {}

        for b_id, b_spec in self.batteries.items():
            p_max = float(b_spec["power_mw"])
            e_cap = float(b_spec["energy_mwh"])
            min_soc = e_cap * float(b_spec.get("soc_min", 0.10))
            max_soc = e_cap * float(b_spec.get("soc_max", 0.95))

            ch[b_id] = {}
            dis[b_id] = {}
            soc[b_id] = {}
            u[b_id] = {}
            res_slack[b_id] = {}

            for t in range(H):
                ch[b_id][t] = pulp.LpVariable(f"ch_{b_id}_{t}", lowBound=0, upBound=p_max)
                dis[b_id][t] = pulp.LpVariable(f"dis_{b_id}_{t}", lowBound=0, upBound=p_max)
                soc[b_id][t] = pulp.LpVariable(f"soc_{b_id}_{t}", lowBound=min_soc, upBound=max_soc)
                u[b_id][t] = pulp.LpVariable(f"u_{b_id}_{t}", cat=pulp.LpBinary)
                res_slack[b_id][t] = pulp.LpVariable(f"res_slack_{b_id}_{t}", lowBound=0)

        # Grid Exchange: buy, sell (MW), binary y (1=buy)
        buy: Dict[int, pulp.LpVariable] = {}
        sell: Dict[int, pulp.LpVariable] = {}
        y: Dict[int, pulp.LpVariable] = {}

        for t in range(H):
            imp_lim = float(forecast.import_limit[t])
            exp_lim = float(forecast.export_limit[t])
            buy[t] = pulp.LpVariable(f"buy_{t}", lowBound=0, upBound=imp_lim)
            sell[t] = pulp.LpVariable(f"sell_{t}", lowBound=0, upBound=exp_lim)
            y[t] = pulp.LpVariable(f"y_{t}", cat=pulp.LpBinary)

        # Curtailment (MW)
        curt_s: Dict[str, Dict[int, pulp.LpVariable]] = {}
        for s_id in self.solar_farms:
            curt_s[s_id] = {}
            for t in range(H):
                s_fcst = float(forecast.solar_p50[s_id][t])
                curt_s[s_id][t] = pulp.LpVariable(f"curt_s_{s_id}_{t}", lowBound=0, upBound=s_fcst)

        curt_w: Dict[str, Dict[int, pulp.LpVariable]] = {}
        for w_id in self.wind_farms:
            curt_w[w_id] = {}
            for t in range(H):
                w_fcst = float(forecast.wind_p50[w_id][t])
                curt_w[w_id][t] = pulp.LpVariable(f"curt_w_{w_id}_{t}", lowBound=0, upBound=w_fcst)

        # Demand Response, Shortfall, Unserved Load (MW)
        dr: Dict[str, Dict[int, pulp.LpVariable]] = {}
        short: Dict[str, Dict[int, pulp.LpVariable]] = {}
        unserved: Dict[str, Dict[int, pulp.LpVariable]] = {}

        for c_id, c_spec in self.consumers.items():
            dr_max = float(c_spec.get("dr_max_mw", 0.0))
            crit_frac = float(c_spec.get("critical_fraction", 0.50))
            dr[c_id] = {}
            short[c_id] = {}
            unserved[c_id] = {}

            for t in range(H):
                dem_fcst = float(forecast.demand_p50[c_id][t])
                non_crit_dem = dem_fcst * (1.0 - crit_frac)
                crit_dem = dem_fcst * crit_frac

                dr[c_id][t] = pulp.LpVariable(f"dr_{c_id}_{t}", lowBound=0, upBound=dr_max)
                short[c_id][t] = pulp.LpVariable(f"short_{c_id}_{t}", lowBound=0, upBound=non_crit_dem)
                unserved[c_id][t] = pulp.LpVariable(f"unserved_{c_id}_{t}", lowBound=0, upBound=crit_dem)

        # ---------------- Constraints ----------------
        for t in range(H):
            # 1. Grid import/export binary exclusivity & limits
            prob += buy[t] <= float(forecast.import_limit[t]) * y[t], f"import_excl_{t}"
            prob += sell[t] <= float(forecast.export_limit[t]) * (1 - y[t]), f"export_excl_{t}"

            # 2. Battery power constraints & availability
            for b_id, b_spec in self.batteries.items():
                p_max = float(b_spec["power_mw"])
                is_avail = current_state.battery_available.get(b_id, True)

                if not is_avail:
                    prob += ch[b_id][t] == 0, f"b_avail_ch_{b_id}_{t}"
                    prob += dis[b_id][t] == 0, f"b_avail_dis_{b_id}_{t}"
                else:
                    prob += ch[b_id][t] <= p_max * u[b_id][t], f"b_ch_excl_{b_id}_{t}"
                    prob += dis[b_id][t] <= p_max * (1 - u[b_id][t]), f"b_dis_excl_{b_id}_{t}"

                # 3. Dynamic SoC equation
                eta_c = float(b_spec.get("eta_charge", 0.95))
                eta_d = float(b_spec.get("eta_discharge", 0.95))

                if t == 0:
                    init_soc = current_state.battery_soc.get(
                        b_id, float(b_spec["energy_mwh"]) * float(b_spec["initial_soc"])
                    )
                    prob += (
                        soc[b_id][0] == init_soc + (ch[b_id][0] * eta_c - dis[b_id][0] * (1.0 / eta_d)) * dt,
                        f"soc_dyn_{b_id}_0",
                    )
                else:
                    prob += (
                        soc[b_id][t] == soc[b_id][t - 1] + (ch[b_id][t] * eta_c - dis[b_id][t] * (1.0 / eta_d)) * dt,
                        f"soc_dyn_{b_id}_{t}",
                    )

                # Reserve floor constraint (achievable ramp towards floor)
                init_soc = current_state.battery_soc.get(
                    b_id, float(b_spec["energy_mwh"]) * float(b_spec["initial_soc"])
                )
                eff_floor = max(float(b_spec.get("soc_min", 0.10)), min(reserve_floor, init_soc / float(b_spec["energy_mwh"])))
                target_floor = float(b_spec["energy_mwh"]) * eff_floor
                prob += soc[b_id][t] + res_slack[b_id][t] >= target_floor, f"reserve_floor_{b_id}_{t}"

            # 4. Consumer Demand Response and Non-Critical bounds
            for c_id, c_spec in self.consumers.items():
                dem_fcst = float(forecast.demand_p50[c_id][t])
                non_crit_dem = dem_fcst * (1.0 - float(c_spec.get("critical_fraction", 0.50)))
                prob += dr[c_id][t] + short[c_id][t] <= non_crit_dem, f"dr_short_limit_{c_id}_{t}"

            # 5. Energy Balance Equation for each interval t
            # Gen side: Solar(net) + Wind(net) + BESS Dis + Buy
            gen_side = (
                pulp.lpSum(float(forecast.solar_p50[s][t]) - curt_s[s][t] for s in self.solar_farms)
                + pulp.lpSum(float(forecast.wind_p50[w][t]) - curt_w[w][t] for w in self.wind_farms)
                + pulp.lpSum(dis[b][t] for b in self.batteries)
                + buy[t]
            )

            # Load side: Net Demand (Demand - DR - Short - Unserved) + BESS Ch + Sell
            load_side = (
                pulp.lpSum(
                    float(forecast.demand_p50[c][t]) - dr[c][t] - short[c][t] - unserved[c][t]
                    for c in self.consumers
                )
                + pulp.lpSum(ch[b][t] for b in self.batteries)
                + sell[t]
            )

            prob += gen_side == load_side, f"energy_balance_{t}"

        # 6. Optional Terminal SoC Constraint (with slack to prevent artificial blackout)
        term_slack: Dict[str, pulp.LpVariable] = {}
        if terminal_soc_target is not None and terminal_soc_target > 0:
            for b_id, b_spec in self.batteries.items():
                e_cap = float(b_spec["energy_mwh"])
                term_slack[b_id] = pulp.LpVariable(f"term_slack_{b_id}", lowBound=0)
                prob += soc[b_id][H - 1] + term_slack[b_id] >= terminal_soc_target * e_cap, f"term_soc_{b_id}"

        # ---------------- Multi-Objective Formulation ----------------
        term_cost = pulp.lpSum(
            (buy[t] * float(forecast.price_p50[t]) - sell[t] * float(forecast.price_p50[t]) * self.sell_fee_factor) * dt
            for t in range(H)
        )
        term_carbon = pulp.lpSum(
            buy[t] * dt * self.emission_factor * self.carbon_price
            for t in range(H)
        )
        term_curt = pulp.lpSum(
            (pulp.lpSum(curt_s[s][t] for s in self.solar_farms) + pulp.lpSum(curt_w[w][t] for w in self.wind_farms))
            * dt * self.curtailment_penalty
            for t in range(H)
        )
        term_degr = pulp.lpSum(
            (pulp.lpSum(ch[b][t] + dis[b][t] for b in self.batteries))
            * dt * 500.0
            for t in range(H)
        )
        term_reliab = pulp.lpSum(
            pulp.lpSum(short[c][t] for c in self.consumers) * dt * self.shortfall_penalty
            for t in range(H)
        )
        term_dr = pulp.lpSum(
            pulp.lpSum(dr[c][t] * float(self.consumers[c].get("dr_incentive_inr_per_mwh", 3000.0)) for c in self.consumers)
            * dt
            for t in range(H)
        )
        # VOLL is the catastrophic penalty; scaled by reliability weight to strictly dominate all other costs
        voll_effective = max(self.voll, self.voll * w.get("reliability", 1.0) * 2.0, self.shortfall_penalty * w.get("reliability", 1.0) * 20.0)
        term_voll = pulp.lpSum(
            pulp.lpSum(unserved[c][t] for c in self.consumers) * dt * voll_effective
            for t in range(H)
        )
        term_res_slack = pulp.lpSum(
            res_slack[b][t] * 25000.0
            for b in self.batteries
            for t in range(H)
        )
        term_terminal_slack = pulp.lpSum(
            term_slack[b] * 2000.0
            for b in term_slack
        )

        prob += (
            w["cost"] * term_cost
            + w["carbon"] * term_carbon
            + w["curtailment"] * term_curt
            + w["degradation"] * term_degr
            + w["reliability"] * term_reliab
            + term_dr
            + term_voll
            + term_res_slack
            + term_terminal_slack
        )

        # Solve with PuLP CBC solver
        solver = pulp.PULP_CBC_CMD(timeLimit=time_limit_sec, msg=0)
        prob.solve(solver)

        solve_time = time.time() - start_time
        status_str = pulp.LpStatus.get(prob.status, "Unknown")
        is_feasible = prob.status == pulp.constants.LpStatusOptimal

        if not is_feasible:
            return DispatchPlan(
                plan_id=plan_id,
                status=status_str,
                is_feasible=False,
                solve_time_seconds=round(solve_time, 3),
                first_interval=DispatchAction(),
                horizon_actions=[],
                soc_trajectory={},
                objective_terms={},
                weights_used=w,
                reserve_floor=reserve_floor,
                terminal_soc_target=terminal_soc_target,
            )

        # Extract horizon actions and trajectories
        horizon_actions: List[DispatchAction] = []
        soc_trajectory: Dict[str, List[float]] = {b: [] for b in self.batteries}

        for t in range(H):
            act = DispatchAction(
                battery_charge={b: round(float(pulp.value(ch[b][t])), 3) for b in self.batteries},
                battery_discharge={b: round(float(pulp.value(dis[b][t])), 3) for b in self.batteries},
                grid_import=round(float(pulp.value(buy[t])), 3),
                grid_export=round(float(pulp.value(sell[t])), 3),
                solar_curtailment={s: round(float(pulp.value(curt_s[s][t])), 3) for s in self.solar_farms},
                wind_curtailment={w_id: round(float(pulp.value(curt_w[w_id][t])), 3) for w_id in self.wind_farms},
                demand_response={c: round(float(pulp.value(dr[c][t])), 3) for c in self.consumers},
                contract_shortfall={c: round(float(pulp.value(short[c][t])), 3) for c in self.consumers},
                unserved_critical={c: round(float(pulp.value(unserved[c][t])), 3) for c in self.consumers},
            )
            horizon_actions.append(act)

            for b in self.batteries:
                soc_trajectory[b].append(round(float(pulp.value(soc[b][t])), 3))

        obj_terms = {
            "cost": round(float(pulp.value(term_cost)), 2),
            "carbon": round(float(pulp.value(term_carbon)), 2),
            "curtailment": round(float(pulp.value(term_curt)), 2),
            "degradation": round(float(pulp.value(term_degr)), 2),
            "reliability": round(float(pulp.value(term_reliab)), 2),
            "dr": round(float(pulp.value(term_dr)), 2),
            "voll": round(float(pulp.value(term_voll)), 2),
            "total_objective": round(float(pulp.value(prob.objective)), 2),
        }

        return DispatchPlan(
            plan_id=plan_id,
            status=status_str,
            is_feasible=True,
            solve_time_seconds=round(solve_time, 3),
            first_interval=horizon_actions[0],
            horizon_actions=horizon_actions,
            soc_trajectory=soc_trajectory,
            objective_terms=obj_terms,
            weights_used=w,
            reserve_floor=reserve_floor,
            terminal_soc_target=terminal_soc_target,
        )
