"""Comprehensive KPI metrics calculation engine for GridMind.

Tracks cumulative and interval operational performance:
- Financials (net cost, import expenditure, export revenues, penalties, DR incentives)
- Carbon accounting (grid import emissions, carbon cost)
- Renewable performance (curtailment MWh, renewable utilization %)
- Asset health (battery throughput MWh, equivalent full cycles)
- Reliability & Safety (shortfalls, unserved critical load, hard violations, safe-mode occurrences)
- Computational efficiency (LLM calls, mock fallbacks, solve times)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np


@dataclass
class PortfolioMetrics:
    """Cumulative operational KPIs across a simulation run."""
    # Financials
    total_net_cost_inr: float = 0.0
    purchase_cost_inr: float = 0.0
    revenue_sales_inr: float = 0.0
    dr_incentive_cost_inr: float = 0.0
    shortfall_penalty_inr: float = 0.0
    unserved_voll_penalty_inr: float = 0.0
    carbon_cost_inr: float = 0.0
    battery_degradation_cost_inr: float = 0.0

    # Carbon and Renewables
    carbon_emissions_tco2: float = 0.0
    renewable_energy_available_mwh: float = 0.0
    renewable_energy_used_mwh: float = 0.0
    renewable_utilization_pct: float = 0.0
    curtailment_mwh: float = 0.0
    curtailed_energy_lost_pct: float = 0.0

    # Battery Health
    battery_throughput_mwh: float = 0.0
    battery_equivalent_full_cycles: Dict[str, float] = field(default_factory=dict)

    # Reliability and Safety (D2 claims)
    contract_shortfall_mwh: float = 0.0
    unserved_critical_load_mwh: float = 0.0
    total_hard_violations: int = 0
    safe_mode_intervals: int = 0

    # Compute and Agent Metrics
    total_intervals: int = 0
    llm_calls: int = 0
    fallback_count: int = 0
    avg_optimizer_solve_time_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to clean JSON-serializable dictionary."""
        return {
            "total_net_cost_inr": round(self.total_net_cost_inr, 2),
            "purchase_cost_inr": round(self.purchase_cost_inr, 2),
            "revenue_sales_inr": round(self.revenue_sales_inr, 2),
            "dr_incentive_cost_inr": round(self.dr_incentive_cost_inr, 2),
            "shortfall_penalty_inr": round(self.shortfall_penalty_inr, 2),
            "unserved_voll_penalty_inr": round(self.unserved_voll_penalty_inr, 2),
            "carbon_cost_inr": round(self.carbon_cost_inr, 2),
            "carbon_emissions_tco2": round(self.carbon_emissions_tco2, 3),
            "renewable_energy_available_mwh": round(self.renewable_energy_available_mwh, 2),
            "renewable_energy_used_mwh": round(self.renewable_energy_used_mwh, 2),
            "renewable_utilization_pct": round(self.renewable_utilization_pct, 2),
            "curtailment_mwh": round(self.curtailment_mwh, 2),
            "battery_throughput_mwh": round(self.battery_throughput_mwh, 2),
            "battery_equivalent_full_cycles": {
                b: round(c, 3) for b, c in self.battery_equivalent_full_cycles.items()
            },
            "contract_shortfall_mwh": round(self.contract_shortfall_mwh, 3),
            "unserved_critical_load_mwh": round(self.unserved_critical_load_mwh, 4),
            "total_hard_violations": self.total_hard_violations,
            "safe_mode_intervals": self.safe_mode_intervals,
            "total_intervals": self.total_intervals,
            "llm_calls": self.llm_calls,
            "fallback_count": self.fallback_count,
            "avg_optimizer_solve_time_sec": round(self.avg_optimizer_solve_time_sec, 3),
        }


class MetricsTracker:
    """Accumulates and updates portfolio KPIs interval by interval."""

    def __init__(
        self,
        batteries_config: Dict[str, Any],
        consumers_config: Dict[str, Any],
        emission_factor_tco2_per_mwh: float = 0.71,
        carbon_price_inr_per_tco2: float = 1500.0,
        shortfall_penalty_inr: float = 15000.0,
        voll_inr: float = 100000.0,
        dt_hours: float = 0.25,
    ) -> None:
        self.batteries_cfg = batteries_config
        self.consumers_cfg = consumers_config
        self.emission_factor = emission_factor_tco2_per_mwh
        self.carbon_price = carbon_price_inr_per_tco2
        self.shortfall_penalty = shortfall_penalty_inr
        self.voll = voll_inr
        self.dt = dt_hours

        self.reset()

    def reset(self) -> None:
        """Reset all accumulators for a new simulation run."""
        self.metrics = PortfolioMetrics()
        self.solve_times: List[float] = []
        self.throughput_by_battery: Dict[str, float] = {b: 0.0 for b in self.batteries_cfg}
        self.metrics.battery_equivalent_full_cycles = {b: 0.0 for b in self.batteries_cfg}

    def record_interval(
        self,
        grid_import_mw: float,
        grid_export_mw: float,
        price_actual: float,
        solar_actual_mw: float,
        wind_actual_mw: float,
        curtailment_mw: float,
        battery_charge: Dict[str, float],
        battery_discharge: Dict[str, float],
        demand_response: Dict[str, float],
        contract_shortfall: Dict[str, float],
        unserved_critical: Dict[str, float],
        hard_violations: int = 0,
        is_safe_mode: bool = False,
        solve_time_sec: Optional[float] = None,
        llm_called: bool = False,
        fallback_used: bool = False,
    ) -> PortfolioMetrics:
        """Accumulate single interval outcomes into running portfolio KPIs."""
        self.metrics.total_intervals += 1

        # 1. Financials
        buy_cost = grid_import_mw * self.dt * price_actual
        sell_rev = grid_export_mw * self.dt * (price_actual * 0.97)
        self.metrics.purchase_cost_inr += buy_cost
        self.metrics.revenue_sales_inr += sell_rev

        dr_cost = sum(
            dr_mw * self.dt * float(self.consumers_cfg.get(c, {}).get("dr_incentive_inr_per_mwh", 3000.0))
            for c, dr_mw in demand_response.items()
        )
        self.metrics.dr_incentive_cost_inr += dr_cost

        short_mwh = sum(contract_shortfall.values()) * self.dt
        self.metrics.contract_shortfall_mwh += short_mwh
        self.metrics.shortfall_penalty_inr += short_mwh * self.shortfall_penalty

        unserved_mwh = sum(unserved_critical.values()) * self.dt
        self.metrics.unserved_critical_load_mwh += unserved_mwh
        self.metrics.unserved_voll_penalty_inr += unserved_mwh * self.voll

        # Carbon
        emissions = grid_import_mw * self.dt * self.emission_factor
        self.metrics.carbon_emissions_tco2 += emissions
        carbon_cost = emissions * self.carbon_price
        self.metrics.carbon_cost_inr += carbon_cost

        # Battery degradation & throughput
        int_throughput = 0.0
        for b_id in self.batteries_cfg:
            ch = battery_charge.get(b_id, 0.0)
            dis = battery_discharge.get(b_id, 0.0)
            flow_mwh = (ch + dis) * self.dt
            self.throughput_by_battery[b_id] += flow_mwh
            int_throughput += flow_mwh

            cap_mwh = float(self.batteries_cfg[b_id].get("energy_mwh", 1.0))
            # 1 full cycle = 2 * capacity throughput (one full charge + one full discharge)
            self.metrics.battery_equivalent_full_cycles[b_id] = self.throughput_by_battery[b_id] / (2.0 * cap_mwh)

        self.metrics.battery_throughput_mwh += int_throughput
        self.metrics.battery_degradation_cost_inr += int_throughput * 500.0

        # Total Net Cost = purchase + DR + penalties + carbon + degradation - revenue
        self.metrics.total_net_cost_inr = (
            self.metrics.purchase_cost_inr
            + self.metrics.dr_incentive_cost_inr
            + self.metrics.shortfall_penalty_inr
            + self.metrics.unserved_voll_penalty_inr
            + self.metrics.carbon_cost_inr
            + self.metrics.battery_degradation_cost_inr
            - self.metrics.revenue_sales_inr
        )

        # 2. Renewables Accounting
        avail_mwh = (solar_actual_mw + wind_actual_mw) * self.dt
        curt_mwh = curtailment_mw * self.dt
        used_mwh = max(0.0, avail_mwh - curt_mwh)

        self.metrics.renewable_energy_available_mwh += avail_mwh
        self.metrics.curtailment_mwh += curt_mwh
        self.metrics.renewable_energy_used_mwh += used_mwh

        if self.metrics.renewable_energy_available_mwh > 1e-4:
            self.metrics.renewable_utilization_pct = (
                self.metrics.renewable_energy_used_mwh / self.metrics.renewable_energy_available_mwh
            ) * 100.0
            self.metrics.curtailed_energy_lost_pct = (
                self.metrics.curtailment_mwh / self.metrics.renewable_energy_available_mwh
            ) * 100.0
        else:
            self.metrics.renewable_utilization_pct = 100.0
            self.metrics.curtailed_energy_lost_pct = 0.0

        # 3. Reliability & Safety
        self.metrics.total_hard_violations += hard_violations
        if is_safe_mode:
            self.metrics.safe_mode_intervals += 1

        # 4. Computational Performance
        if llm_called:
            self.metrics.llm_calls += 1
        if fallback_used:
            self.metrics.fallback_count += 1
        if solve_time_sec is not None:
            self.solve_times.append(solve_time_sec)
            self.metrics.avg_optimizer_solve_time_sec = float(np.mean(self.solve_times))

        return self.metrics

    def current_metrics(self) -> PortfolioMetrics:
        """Return current cumulative metrics snapshot."""
        return self.metrics
