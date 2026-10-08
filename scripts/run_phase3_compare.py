"""Phase 3 benchmark comparison: Rule-based heuristic vs. Rolling-horizon MILP.

Runs a full 24-hour simulation under identical inputs and events,
comparing financial performance, shortfall penalties, critical unserved load,
and carbon emissions side-by-side.
"""

from pathlib import Path
import yaml
import pandas as pd

from gridmind.forecast.forecaster import Forecaster
from gridmind.optimize.heuristics import rule_based_baseline_dispatch
from gridmind.optimize.milp import MilpOptimizer
from gridmind.sim.simulator import Simulator

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "data" / "processed" / "season_A.csv"
ASSETS_CFG = BASE_DIR / "config" / "assets.yaml"
MARKET_CFG = BASE_DIR / "config" / "market.yaml"
SCENARIOS_CFG = BASE_DIR / "config" / "scenarios.yaml"


def run_benchmark():
    print("=" * 88)
    print("GRIDMIND PHASE 3 BENCHMARK: Rule-Based Heuristic vs. Fixed-Weight Rolling MILP")
    print("=" * 88)

    # 1. Run Rule-Based Baseline
    print("1. Executing 24-hour Rule-Based Baseline...")
    sim_baseline = Simulator(DATASET_PATH, ASSETS_CFG, MARKET_CFG)
    with open(SCENARIOS_CFG, "r", encoding="utf-8") as f:
        scenarios_data = yaml.safe_load(f)
    sim_baseline.event_manager.load_from_scenario_dict(scenarios_data["day_at_deccan"])

    for _ in range(96):
        state = sim_baseline.current_state()
        action = rule_based_baseline_dispatch(state, sim_baseline.batteries, sim_baseline.consumers)
        sim_baseline.step(action)

    kpi_base = sim_baseline.cumulative_kpis

    # 2. Run Rolling-Horizon MILP with Fixed Default Weights
    print("2. Executing 24-hour Rolling-Horizon MILP (Horizon = 32 intervals)...")
    sim_milp = Simulator(DATASET_PATH, ASSETS_CFG, MARKET_CFG)
    sim_milp.event_manager.load_from_scenario_dict(scenarios_data["day_at_deccan"])
    forecaster = Forecaster(DATASET_PATH, ASSETS_CFG, MARKET_CFG)
    optimizer = MilpOptimizer(ASSETS_CFG, MARKET_CFG)

    default_weights = {
        "cost": 1.0,
        "carbon": 1.0,
        "curtailment": 1.0,
        "degradation": 1.0,
        "reliability": 1.0,
    }

    solve_times = []
    for step in range(96):
        state = sim_milp.current_state()
        fcst = forecaster.forecast(state, event_manager=sim_milp.event_manager, num_scenarios=5, seed=42 + step)
        plan = optimizer.solve(state, fcst, weights=default_weights, reserve_floor=0.10)
        solve_times.append(plan.solve_time_seconds)
        sim_milp.step(plan.first_interval)

    kpi_milp = sim_milp.cumulative_kpis

    print("\n" + "=" * 88)
    print(f"{'Performance Metric':<35} | {'Rule-Based Baseline':<22} | {'Fixed-Weight MILP':<22}")
    print("-" * 88)

    metrics = [
        ("Total Net Cost (₹)", f"₹{kpi_base.total_net_cost_inr:,.2f}", f"₹{kpi_milp.total_net_cost_inr:,.2f}"),
        ("Power Purchase Cost (₹)", f"₹{kpi_base.total_purchase_cost_inr:,.2f}", f"₹{kpi_milp.total_purchase_cost_inr:,.2f}"),
        ("Export Revenue (₹)", f"₹{kpi_base.total_revenue_sales_inr:,.2f}", f"₹{kpi_milp.total_revenue_sales_inr:,.2f}"),
        ("Shortfall Penalty (₹)", f"₹{kpi_base.total_shortfall_penalty_inr:,.2f}", f"₹{kpi_milp.total_shortfall_penalty_inr:,.2f}"),
        ("VOLL Unserved Critical Penalty (₹)", f"₹{kpi_base.total_unserved_penalty_inr:,.2f}", f"₹{kpi_milp.total_unserved_penalty_inr:,.2f}"),
        ("Contract Shortfall Energy (MWh)", f"{kpi_base.total_contract_shortfall_mwh:.2f} MWh", f"{kpi_milp.total_contract_shortfall_mwh:.2f} MWh"),
        ("Unserved Critical Load (MWh)", f"{kpi_base.total_unserved_critical_mwh:.2f} MWh", f"{kpi_milp.total_unserved_critical_mwh:.2f} MWh"),
        ("Carbon Emissions (tCO2)", f"{kpi_base.total_carbon_emissions_tco2:.2f} tCO2", f"{kpi_milp.total_carbon_emissions_tco2:.2f} tCO2"),
        ("Renewable Utilization (%)", f"{kpi_base.avg_renewable_utilization_pct:.1f}%", f"{kpi_milp.avg_renewable_utilization_pct:.1f}%"),
        ("Battery Throughput (MWh)", f"{kpi_base.total_battery_throughput_mwh:.2f} MWh", f"{kpi_milp.total_battery_throughput_mwh:.2f} MWh"),
        ("Hard-Constraint Violations", f"{kpi_base.total_hard_violations}", f"{kpi_milp.total_hard_violations}"),
        ("Avg Solver Time per Interval (s)", "N/A (Heuristic)", f"{sum(solve_times)/len(solve_times):.3f} s"),
    ]

    for name, b_val, m_val in metrics:
        print(f"{name:<35} | {b_val:>22} | {m_val:>22}")

    cost_savings = kpi_base.total_net_cost_inr - kpi_milp.total_net_cost_inr
    pct_savings = (cost_savings / kpi_base.total_net_cost_inr) * 100.0

    print("-" * 88)
    print(f"NET COST SAVINGS FROM MILP OPTIMIZATION: ₹{cost_savings:,.2f} ({pct_savings:.1f}% cost reduction)")
    print("=" * 88)


if __name__ == "__main__":
    run_benchmark()
