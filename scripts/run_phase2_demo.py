"""CLI demo running Phase 2 simulator with event injection and 24-hour dispatch.

Demonstrates:
- 24-hour (96 intervals) simulation execution
- Application of disturbances from scenarios.yaml (cloud bank, storm alert, battery outage, line constraint, price spike)
- Strict physical energy balance verification (generation == consumption)
- Cumulative KPI reporting
"""

from pathlib import Path
import yaml
import pandas as pd

from gridmind.sim.events import EventManager
from gridmind.sim.simulator import Simulator
from gridmind.sim.state import DispatchAction
from gridmind.forecast.forecaster import Forecaster

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "data" / "processed" / "season_A.csv"
ASSETS_CFG = BASE_DIR / "config" / "assets.yaml"
MARKET_CFG = BASE_DIR / "config" / "market.yaml"
SCENARIOS_CFG = BASE_DIR / "config" / "scenarios.yaml"


def run_phase2_demo() -> None:
    print("=" * 85)
    print("GRIDMIND PHASE 2 SIMULATION DEMO: 'A Day at Deccan Renewables'")
    print("=" * 85)

    simulator = Simulator(
        dataset_path=DATASET_PATH,
        assets_config_path=ASSETS_CFG,
        market_config_path=MARKET_CFG,
    )
    forecaster = Forecaster(
        dataset_path=DATASET_PATH,
        assets_config_path=ASSETS_CFG,
        market_config_path=MARKET_CFG,
    )

    # Load preset scenario events
    with open(SCENARIOS_CFG, "r", encoding="utf-8") as f:
        scenarios_data = yaml.safe_load(f)
    preset = scenarios_data["day_at_deccan"]
    simulator.event_manager.load_from_scenario_dict(preset)
    print(f"Loaded scenario: {preset['name']}")
    print(f"Total scheduled disturbances: {len(simulator.event_manager.events)}")

    print("\nSimulating 96 intervals (24 hours @ 15 min / interval)...")
    print("-" * 85)
    print(f"{'Int':<4} | {'Time':<8} | {'Solar':<7} | {'Wind':<6} | {'Demand':<7} | {'BESS':<7} | {'Grid':<7} | {'Price':<6} | {'Active Event'}")
    print("-" * 85)

    for step in range(96):
        state = simulator.current_state()
        ts_str = str(state.timestamp)[11:16]  # HH:MM

        tot_re = sum(state.solar_actual.values()) + sum(state.wind_actual.values())
        tot_dem = sum(state.demand_actual.values())

        # Simple baseline balancing rule
        b1_spec = simulator.batteries["B1"]
        b2_spec = simulator.batteries["B2"]

        if tot_re >= tot_dem:
            surplus = tot_re - tot_dem
            b1_room = max(0.0, (b1_spec["energy_mwh"] * b1_spec["soc_max"] - state.battery_soc["B1"]) / (0.95 * 0.25))
            b1_ch = min(b1_spec["power_mw"], b1_room, surplus) if state.battery_available["B1"] else 0.0
            surplus -= b1_ch

            b2_room = max(0.0, (b2_spec["energy_mwh"] * b2_spec["soc_max"] - state.battery_soc["B2"]) / (0.95 * 0.25))
            b2_ch = min(b2_spec["power_mw"], b2_room, surplus) if state.battery_available["B2"] else 0.0
            surplus -= b2_ch

            grid_exp = min(state.grid_export_limit_mw, surplus)
            surplus -= grid_exp

            solar_curt = {}
            for s_id, s_mw in state.solar_actual.items():
                c_val = min(s_mw, surplus)
                solar_curt[s_id] = c_val
                surplus -= c_val

            action = DispatchAction(
                battery_charge={"B1": b1_ch, "B2": b2_ch},
                grid_export=grid_exp,
                solar_curtailment=solar_curt,
            )
            net_bess = -(b1_ch + b2_ch)  # negative means charging
            net_grid = -grid_exp        # negative means exporting
        else:
            deficit = tot_dem - tot_re
            b1_avail = max(0.0, (state.battery_soc["B1"] - b1_spec["energy_mwh"] * b1_spec["soc_min"]) * 0.95 / 0.25)
            b1_dis = min(b1_spec["power_mw"], b1_avail, deficit) if state.battery_available["B1"] else 0.0
            deficit -= b1_dis

            b2_avail = max(0.0, (state.battery_soc["B2"] - b2_spec["energy_mwh"] * b2_spec["soc_min"]) * 0.95 / 0.25)
            b2_dis = min(b2_spec["power_mw"], b2_avail, deficit) if state.battery_available["B2"] else 0.0
            deficit -= b2_dis

            grid_imp = min(state.grid_import_limit_mw, deficit)
            deficit -= grid_imp

            shortfall = {}
            for c_id, c_mw in state.demand_actual.items():
                non_crit = c_mw * (1.0 - simulator.consumers[c_id]["critical_fraction"])
                sh = min(non_crit, deficit)
                shortfall[c_id] = sh
                deficit -= sh

            unserved = {}
            for c_id in state.demand_actual:
                if deficit > 0:
                    un = min(state.demand_actual[c_id] * simulator.consumers[c_id]["critical_fraction"], deficit)
                    unserved[c_id] = un
                    deficit -= un

            action = DispatchAction(
                battery_discharge={"B1": b1_dis, "B2": b2_dis},
                grid_import=grid_imp,
                contract_shortfall=shortfall,
                unserved_critical=unserved,
            )
            net_bess = (b1_dis + b2_dis)
            net_grid = grid_imp

        event_str = ", ".join(e.event_type for e in state.active_events) or "Nominal"

        # Print periodic samples (every 8 intervals = every 2 hours) or when events occur
        if step % 8 == 0 or state.active_events:
            print(
                f"{step:<4} | {ts_str:<8} | {tot_re - sum(state.wind_actual.values()):>6.1f}M | {sum(state.wind_actual.values()):>5.1f}M | "
                f"{tot_dem:>6.1f}M | {net_bess:>6.1f}M | {net_grid:>6.1f}M | {state.price_actual:>6.0f} | {event_str}"
            )

        simulator.step(action)

    print("-" * 85)
    kpis = simulator.cumulative_kpis
    print("\n[PHASE 2 24-HOUR CUMULATIVE KPIS]")
    print(f"Intervals Completed:            {kpis.intervals_completed} (24.0 hours)")
    print(f"Total Net Cost:                 ₹{kpis.total_net_cost_inr:,.2f}")
    print(f"Power Purchase Cost:            ₹{kpis.total_purchase_cost_inr:,.2f}")
    print(f"Export Revenue:                 ₹{kpis.total_revenue_sales_inr:,.2f}")
    print(f"Carbon Emissions:               {kpis.total_carbon_emissions_tco2:,.2f} tCO2 (Cost: ₹{kpis.total_carbon_cost_inr:,.2f})")
    print(f"Average Renewable Utilization:  {kpis.avg_renewable_utilization_pct:.1f}%")
    print(f"Total Curtailment:              {kpis.total_curtailment_mwh:,.2f} MWh")
    print(f"Battery Throughput:             {kpis.total_battery_throughput_mwh:,.2f} MWh")
    print(f"Battery Equivalent Cycles:      B1: {kpis.battery_equivalent_cycles['B1']:.2f}, B2: {kpis.battery_equivalent_cycles['B2']:.2f}")
    print(f"Total Contract Shortfall:       {kpis.total_contract_shortfall_mwh:,.2f} MWh (Penalty: ₹{kpis.total_shortfall_penalty_inr:,.2f})")
    print(f"Total Unserved Critical Load:   {kpis.total_unserved_critical_mwh:,.2f} MWh (Penalty: ₹{kpis.total_unserved_penalty_inr:,.2f})")
    print(f"Total Hard Violations:          {kpis.total_hard_violations}")
    print("=" * 85)


if __name__ == "__main__":
    run_phase2_demo()
