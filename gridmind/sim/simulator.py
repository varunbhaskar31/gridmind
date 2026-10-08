"""15-minute rolling world simulator for portfolio microgrid and market operations.

Implements:
- Strict physical energy balance with explicit residual slack recording
- High-efficiency battery storage physics (η_charge = 0.95, η_discharge = 0.95)
- Dynamic event application altering physical actuals
- Cumulative KPI accounting across financial, carbon, reliability, and asset health dimensions
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import yaml

from gridmind.sim.events import Event, EventManager
from gridmind.sim.state import (
    CumulativeKPIs,
    DispatchAction,
    GridState,
    IntervalKPIs,
)


class Simulator:
    """Simulates 15-minute intervals for Deccan Renewables portfolio."""

    def __init__(
        self,
        dataset_path: Path,
        assets_config_path: Path,
        market_config_path: Path,
    ) -> None:
        self.dataset_path = Path(dataset_path)
        self.df = pd.read_csv(self.dataset_path)
        self.df["timestamp"] = pd.to_datetime(self.df["timestamp"])
        self.total_intervals = len(self.df)

        with open(assets_config_path, "r", encoding="utf-8") as f:
            self.assets_cfg = yaml.safe_load(f)
        with open(market_config_path, "r", encoding="utf-8") as f:
            self.market_cfg = yaml.safe_load(f)

        self.event_manager = EventManager()
        self.solar_farms = {s["id"]: s for s in self.assets_cfg["solar_farms"]}
        self.wind_farms = {w["id"]: w for w in self.assets_cfg["wind_farms"]}
        self.batteries = {b["id"]: b for b in self.assets_cfg["batteries"]}
        self.consumers = {c["id"]: c for c in self.assets_cfg["consumers"]}
        self.grid_limits = self.assets_cfg.get(
            "grid_limits", {"max_import_mw": 150.0, "max_export_mw": 200.0}
        )

        self.interval_hours = float(self.market_cfg["simulation"].get("interval_hours", 0.25))
        self.carbon_emission_factor = float(
            self.market_cfg["carbon"].get("grid_emission_factor_tco2_per_mwh", 0.71)
        )
        self.carbon_price = float(self.market_cfg["carbon"].get("carbon_price_inr_per_tco2", 1500.0))
        self.sell_fee_factor = float(self.market_cfg["market"].get("sell_fee_factor", 0.97))
        self.shortfall_penalty = float(
            self.market_cfg["penalties"].get("contract_shortfall_inr_per_mwh", 15000.0)
        )
        self.voll = float(
            self.market_cfg["penalties"].get("value_of_lost_load_inr_per_mwh", 100000.0)
        )

        self.reset()

    def reset(self) -> GridState:
        """Reset the simulator to interval 0."""
        self.current_interval_idx = 0
        self.battery_soc: Dict[str, float] = {
            b_id: b["energy_mwh"] * b["initial_soc"] for b_id, b in self.batteries.items()
        }
        self.battery_throughput: Dict[str, float] = {b_id: 0.0 for b_id in self.batteries}
        self.interval_history: List[IntervalKPIs] = []
        self.cumulative_kpis = CumulativeKPIs()
        self.cumulative_kpis.battery_equivalent_cycles = {b_id: 0.0 for b_id in self.batteries}
        self.last_actions: Optional[DispatchAction] = None

        return self.current_state()

    def is_done(self) -> bool:
        """Return True if simulation has completed all available intervals."""
        return self.current_interval_idx >= self.total_intervals

    def inject_event(self, event: Event) -> None:
        """Inject an event dynamically into the simulator."""
        self.event_manager.add_event(event)

    def current_state(self) -> GridState:
        """Generate current GridState snapshot for the active interval."""
        if self.current_interval_idx >= self.total_intervals:
            row = self.df.iloc[-1]
        else:
            row = self.df.iloc[self.current_interval_idx]

        # Raw baseline outputs from dataset
        solar_raw = {s_id: float(row[f"solar_{s_id}"]) for s_id in self.solar_farms}
        wind_raw = {w_id: float(row[f"wind_{w_id}"]) for w_id in self.wind_farms}
        demand_raw = {c_id: float(row[f"demand_{c_id}"]) for c_id in self.consumers}
        price_raw = float(row["price"])

        # Apply active disturbances
        disturbed = self.event_manager.apply_events_to_actuals(
            current_interval=self.current_interval_idx,
            solar_raw=solar_raw,
            wind_raw=wind_raw,
            demand_raw=demand_raw,
            price_raw=price_raw,
            import_limit_default=self.grid_limits["max_import_mw"],
            export_limit_default=self.grid_limits["max_export_mw"],
        )

        # Battery availability and SoC percentages
        b_avail: Dict[str, bool] = {}
        soc_pct: Dict[str, float] = {}
        for b_id, b_spec in self.batteries.items():
            b_avail[b_id] = disturbed["battery_avail"].get(b_id, True)
            soc_pct[b_id] = self.battery_soc[b_id] / b_spec["energy_mwh"]

        active_events = self.event_manager.get_active_events(self.current_interval_idx)

        return GridState(
            timestamp=str(row["timestamp"]),
            interval_index=self.current_interval_idx,
            solar_actual=disturbed["solar"],
            wind_actual=disturbed["wind"],
            demand_actual=disturbed["demand"],
            price_actual=disturbed["price"],
            battery_soc=dict(self.battery_soc),
            battery_soc_pct=soc_pct,
            battery_available=b_avail,
            solar_available=disturbed["solar_avail"],
            wind_available=disturbed["wind_avail"],
            grid_import_limit_mw=disturbed["import_limit"],
            grid_export_limit_mw=disturbed["export_limit"],
            active_events=active_events,
            last_actions=self.last_actions,
            kpis=self.cumulative_kpis,
        )

    def step(self, actions: DispatchAction) -> GridState:
        """Apply dispatch actions to the current interval, update physical state, and advance time.

        Args:
            actions: DispatchAction containing battery power, grid exchange, curtailment, and DR.

        Returns:
            Updated GridState for the newly advanced interval.
        """
        if self.current_interval_idx >= self.total_intervals:
            return self.current_state()

        state = self.current_state()
        dt = self.interval_hours
        hard_violations: List[str] = []

        # 1. Update Battery SoC with physical efficiencies
        for b_id, b_spec in self.batteries.items():
            ch = float(actions.battery_charge.get(b_id, 0.0))
            dis = float(actions.battery_discharge.get(b_id, 0.0))
            is_avail = state.battery_available.get(b_id, True)

            if not is_avail and (ch > 1e-4 or dis > 1e-4):
                hard_violations.append(f"Battery {b_id} operated while unavailable (ch={ch}, dis={dis})")
                ch = 0.0
                dis = 0.0

            eta_c = float(b_spec.get("eta_charge", 0.95))
            eta_d = float(b_spec.get("eta_discharge", 0.95))
            cap_mwh = float(b_spec["energy_mwh"])
            min_soc_mwh = cap_mwh * float(b_spec.get("soc_min", 0.10))
            max_soc_mwh = cap_mwh * float(b_spec.get("soc_max", 0.95))

            # SoC update: SoC_t = SoC_{t-1} + (ch * eta_c - dis / eta_d) * dt
            delta_soc = (ch * eta_c - (dis / eta_d)) * dt
            new_soc = self.battery_soc[b_id] + delta_soc

            # Physical limit enforcement
            if new_soc < min_soc_mwh - 1e-3:
                hard_violations.append(
                    f"Battery {b_id} SoC underflow: {new_soc:.2f} MWh < min {min_soc_mwh:.2f} MWh"
                )
            if new_soc > max_soc_mwh + 1e-3:
                hard_violations.append(
                    f"Battery {b_id} SoC overflow: {new_soc:.2f} MWh > max {max_soc_mwh:.2f} MWh"
                )

            self.battery_soc[b_id] = float(np.clip(new_soc, min_soc_mwh, max_soc_mwh))
            throughput = (ch + dis) * dt
            self.battery_throughput[b_id] += throughput

        # 2. Check Interconnection and Critical Load Bounds
        if actions.grid_import > state.grid_import_limit_mw + 1e-3:
            hard_violations.append(
                f"Import limit exceeded: {actions.grid_import:.2f} MW > {state.grid_import_limit_mw:.2f} MW"
            )
        if actions.grid_export > state.grid_export_limit_mw + 1e-3:
            hard_violations.append(
                f"Export limit exceeded: {actions.grid_export:.2f} MW > {state.grid_export_limit_mw:.2f} MW"
            )

        # 3. Energy Balance Accounting
        # Generation side: Solar(net) + Wind(net) + Battery Discharge + Grid Import
        solar_net = sum(
            state.solar_actual[s] - actions.solar_curtailment.get(s, 0.0)
            for s in self.solar_farms
        )
        wind_net = sum(
            state.wind_actual[w] - actions.wind_curtailment.get(w, 0.0)
            for w in self.wind_farms
        )
        bess_discharge = sum(actions.battery_discharge.get(b, 0.0) for b in self.batteries)
        generation_side = solar_net + wind_net + bess_discharge + actions.grid_import

        # Consumption side: Net Demand (Demand - DR - Shortfall) + Battery Charge + Grid Export
        demand_net = sum(
            state.demand_actual[c]
            - actions.demand_response.get(c, 0.0)
            - actions.contract_shortfall.get(c, 0.0)
            - actions.unserved_critical.get(c, 0.0)
            for c in self.consumers
        )
        bess_charge = sum(actions.battery_charge.get(b, 0.0) for b in self.batteries)
        consumption_side = demand_net + bess_charge + actions.grid_export

        balance_residual = generation_side - consumption_side
        # If no explicit balance slack was passed, assign residual to actions.balance_slack
        if abs(actions.balance_slack) < 1e-5:
            actions.balance_slack = round(balance_residual, 4)

        # 4. Calculate Financial & Physical Interval KPIs
        curt_mwh = (
            sum(actions.solar_curtailment.values()) + sum(actions.wind_curtailment.values())
        ) * dt
        short_mwh = sum(actions.contract_shortfall.values()) * dt
        unserved_mwh = sum(actions.unserved_critical.values()) * dt
        re_avail_mw = sum(state.solar_actual.values()) + sum(state.wind_actual.values())
        re_used_mw = solar_net + wind_net
        re_util_pct = (re_used_mw / re_avail_mw * 100.0) if re_avail_mw > 1e-3 else 100.0

        p = state.price_actual
        rev_sales = actions.grid_export * p * self.sell_fee_factor * dt
        cost_purchase = actions.grid_import * p * dt
        emissions_tco2 = actions.grid_import * dt * self.carbon_emission_factor
        carbon_cost = emissions_tco2 * self.carbon_price
        shortfall_pen = short_mwh * self.shortfall_penalty
        unserved_pen = unserved_mwh * self.voll

        dr_cost = sum(
            actions.demand_response.get(c, 0.0)
            * dt
            * self.consumers[c].get("dr_incentive_inr_per_mwh", 3000.0)
            for c in self.consumers
        )
        degr_cost = sum(
            (actions.battery_charge.get(b, 0.0) + actions.battery_discharge.get(b, 0.0))
            * dt
            * self.batteries[b].get("degradation_cost_inr_per_mwh", 500.0)
            for b in self.batteries
        )

        net_cost = (
            cost_purchase - rev_sales + carbon_cost + shortfall_pen + unserved_pen + dr_cost + degr_cost
        )

        bess_thru_mwh = sum(
            (actions.battery_charge.get(b, 0.0) + actions.battery_discharge.get(b, 0.0)) * dt
            for b in self.batteries
        )

        interval_kpis = IntervalKPIs(
            interval_index=self.current_interval_idx,
            timestamp=state.timestamp,
            net_cost_inr=round(net_cost, 2),
            revenue_sales_inr=round(rev_sales, 2),
            purchase_cost_inr=round(cost_purchase, 2),
            carbon_emissions_tco2=round(emissions_tco2, 4),
            carbon_cost_inr=round(carbon_cost, 2),
            renewable_utilization_pct=round(re_util_pct, 2),
            curtailment_mwh=round(curt_mwh, 3),
            battery_throughput_mwh=round(bess_thru_mwh, 3),
            contract_shortfall_mwh=round(short_mwh, 3),
            shortfall_penalty_inr=round(shortfall_pen, 2),
            unserved_critical_mwh=round(unserved_mwh, 3),
            unserved_penalty_inr=round(unserved_pen, 2),
            dr_cost_inr=round(dr_cost, 2),
            battery_degradation_cost_inr=round(degr_cost, 2),
            energy_balance_slack_mw=round(actions.balance_slack, 4),
            hard_violations=hard_violations,
        )
        self.interval_history.append(interval_kpis)

        # 5. Accumulate KPIs
        k = self.cumulative_kpis
        k.total_net_cost_inr += net_cost
        k.total_revenue_sales_inr += rev_sales
        k.total_purchase_cost_inr += cost_purchase
        k.total_carbon_emissions_tco2 += emissions_tco2
        k.total_carbon_cost_inr += carbon_cost
        k.total_curtailment_mwh += curt_mwh
        k.total_battery_throughput_mwh += bess_thru_mwh
        k.total_contract_shortfall_mwh += short_mwh
        k.total_shortfall_penalty_inr += shortfall_pen
        k.total_unserved_critical_mwh += unserved_mwh
        k.total_unserved_penalty_inr += unserved_pen
        k.total_dr_cost_inr += dr_cost
        k.total_battery_degradation_cost_inr += degr_cost
        k.total_hard_violations += len(hard_violations)
        k.intervals_completed += 1
        k.avg_renewable_utilization_pct = (
            k.avg_renewable_utilization_pct * (k.intervals_completed - 1) + re_util_pct
        ) / k.intervals_completed

        for b_id in self.batteries:
            # 1 full cycle = 2 * energy capacity
            cap = self.batteries[b_id]["energy_mwh"]
            k.battery_equivalent_cycles[b_id] = self.battery_throughput[b_id] / (2.0 * cap)

        self.last_actions = actions
        self.current_interval_idx += 1

        return self.current_state()
