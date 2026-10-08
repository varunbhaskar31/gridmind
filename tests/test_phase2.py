"""Acceptance and unit tests for Phase 2: Simulator, Events, Forecaster.

Verifies:
- Accurate battery charge and discharge state-of-charge (SoC) physics
- Individual disturbance event injections (cloud, storm, outage, line limit, price spike, demand surge)
- Forecaster uncertainty cones, quantile monotonicity (P10 <= P50 <= P90), and Monte Carlo scenarios
- Full 24-hour simulation with "do nothing" baseline
- Full 24-hour simulation with a trivial balancing rule where energy balance holds with zero residual
"""

from pathlib import Path
import numpy as np
import pytest

from gridmind.sim.events import Event, EventManager
from gridmind.sim.simulator import Simulator
from gridmind.sim.state import DispatchAction
from gridmind.forecast.forecaster import Forecaster

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "data" / "processed" / "season_A.csv"
ASSETS_CFG = BASE_DIR / "config" / "assets.yaml"
MARKET_CFG = BASE_DIR / "config" / "market.yaml"


@pytest.fixture
def simulator() -> Simulator:
    return Simulator(
        dataset_path=DATASET_PATH,
        assets_config_path=ASSETS_CFG,
        market_config_path=MARKET_CFG,
    )


@pytest.fixture
def forecaster() -> Forecaster:
    return Forecaster(
        dataset_path=DATASET_PATH,
        assets_config_path=ASSETS_CFG,
        market_config_path=MARKET_CFG,
        horizon_intervals=32,
    )


class TestBatteryPhysics:
    def test_battery_charge_math(self, simulator: Simulator):
        """B1 charges at 40 MW for 15 min (0.25h) with η_c=0.95."""
        simulator.reset()
        initial_soc = simulator.battery_soc["B1"]  # 120 MWh
        # delta = 40 MW * 0.95 * 0.25h = 9.5 MWh
        expected_soc = initial_soc + (40.0 * 0.95 * 0.25)

        action = DispatchAction(
            battery_charge={"B1": 40.0, "B2": 0.0},
            battery_discharge={"B1": 0.0, "B2": 0.0},
            grid_import=40.0,  # Balance the charge from grid
        )
        state = simulator.step(action)

        assert pytest.approx(state.battery_soc["B1"], rel=1e-4) == expected_soc
        assert state.kpis.total_battery_throughput_mwh == pytest.approx(10.0, rel=1e-4)

    def test_battery_discharge_math(self, simulator: Simulator):
        """B1 discharges at 40 MW for 15 min (0.25h) with η_d=0.95."""
        simulator.reset()
        initial_soc = simulator.battery_soc["B1"]  # 120 MWh
        # delta = -(40 MW / 0.95) * 0.25h = -10.526315 MWh
        expected_soc = initial_soc - ((40.0 / 0.95) * 0.25)

        action = DispatchAction(
            battery_charge={"B1": 0.0, "B2": 0.0},
            battery_discharge={"B1": 40.0, "B2": 0.0},
            grid_export=40.0,  # Export discharged power
        )
        state = simulator.step(action)

        assert pytest.approx(state.battery_soc["B1"], rel=1e-4) == expected_soc


class TestEventEngine:
    def test_cloud_cover_event(self, simulator: Simulator):
        """Cloud cover attenuates target solar farms by specified percentage."""
        simulator.reset()
        # Step to midday interval 44 where solar is actively producing
        for _ in range(44):
            simulator.step(DispatchAction())

        state_before = simulator.current_state()
        s1_raw = state_before.solar_actual["S1"]
        assert s1_raw > 10.0, "S1 should be producing in midday"

        # Inject 60% cloud cover on S1 starting next interval
        event = Event(
            event_type="cloud_cover",
            start_interval=45,
            duration_intervals=4,
            magnitude=0.60,
            affected_assets=["S1"],
        )
        simulator.inject_event(event)
        simulator.step(DispatchAction())
        state_cloud = simulator.current_state()

        # Solar S1 should be reduced by 60% (output = 40% of baseline)
        assert pytest.approx(state_cloud.solar_actual["S1"], rel=0.1) == s1_raw * 0.40

    def test_battery_outage_event(self, simulator: Simulator):
        """Battery outage disables charge/discharge and records violations if commanded."""
        simulator.reset()
        event = Event(
            event_type="battery_outage",
            start_interval=1,
            duration_intervals=4,
            affected_assets=["B2"],
        )
        simulator.inject_event(event)
        simulator.step(DispatchAction())

        state = simulator.current_state()
        assert state.battery_available["B2"] is False
        assert state.battery_available["B1"] is True

        # Attempt to charge disabled B2
        action = DispatchAction(battery_charge={"B2": 20.0})
        simulator.step(action)
        assert simulator.cumulative_kpis.total_hard_violations >= 1

    def test_storm_alert_advance_and_impact(self, simulator: Simulator, forecaster: Forecaster):
        """Storm alert announced in advance changes forecast, then hits physical actuals."""
        simulator.reset()
        # Storm announced at interval 10, hits at interval 25
        storm = Event(
            event_type="storm_alert",
            start_interval=25,
            duration_intervals=8,
            magnitude=0.80,
            announced_at=10,
            extra_params={"wind_cut_out": True, "export_limit_mw": 80.0},
        )
        simulator.inject_event(storm)

        # Fast forward to interval 10 (announcement time)
        for _ in range(10):
            simulator.step(DispatchAction())

        state_10 = simulator.current_state()
        # Check forecaster sees the storm at future step 25 (step 15 in forecast horizon)
        fcst = forecaster.forecast(state_10, event_manager=simulator.event_manager)
        step_25_horizon_idx = 25 - 10
        # Wind cut-out in forecast
        assert fcst.wind_p50["W1"][step_25_horizon_idx] == 0.0
        # Export limit reduced in forecast
        assert fcst.export_limit[step_25_horizon_idx] == 80.0

        # Fast forward to interval 25 when storm physically hits
        for _ in range(15):
            simulator.step(DispatchAction())

        state_25 = simulator.current_state()
        assert state_25.grid_export_limit_mw == 80.0
        assert state_25.wind_actual["W1"] == 0.0
        assert state_25.wind_available["W1"] is False

    def test_price_spike_and_line_constraint(self, simulator: Simulator):
        simulator.reset()
        simulator.inject_event(
            Event(event_type="price_spike", start_interval=5, duration_intervals=2, magnitude=2.0)
        )
        simulator.inject_event(
            Event(event_type="line_constraint", start_interval=5, duration_intervals=2, magnitude=110.0)
        )

        for _ in range(5):
            simulator.step(DispatchAction())

        state = simulator.current_state()
        assert state.grid_export_limit_mw == 110.0
        # Base price around ₹4500 doubled to ~₹9000
        assert state.price_actual > 6000.0


class TestForecaster:
    def test_forecast_quantiles_and_cones(self, simulator: Simulator, forecaster: Forecaster):
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=30, seed=42)

        assert fcst.horizon_intervals == 32
        assert len(fcst.lead_hours) == 32
        assert len(fcst.scenarios) == 30

        # Quantile monotonicity: P10 <= P50 <= P90 everywhere
        for s in fcst.solar_p50:
            assert (fcst.solar_p10[s] <= fcst.solar_p50[s] + 1e-4).all()
            assert (fcst.solar_p50[s] <= fcst.solar_p90[s] + 1e-4).all()

        for w in fcst.wind_p50:
            assert (fcst.wind_p10[w] <= fcst.wind_p50[w] + 1e-4).all()
            assert (fcst.wind_p50[w] <= fcst.wind_p90[w] + 1e-4).all()

        assert (fcst.price_p10 <= fcst.price_p50 + 1e-4).all()
        assert (fcst.price_p50 <= fcst.price_p90 + 1e-4).all()

        # Expanding uncertainty cone: spread at lead 8h > spread at lead 0.25h
        spread_near = fcst.price_p90[0] - fcst.price_p10[0]
        spread_far = fcst.price_p90[-1] - fcst.price_p10[-1]
        assert spread_far > spread_near


class TestFullDaySimulations:
    def test_full_day_do_nothing(self, simulator: Simulator):
        """Run 96 intervals (24h) with do-nothing action; verify stability and metrics."""
        simulator.reset()
        for _ in range(96):
            simulator.step(DispatchAction())

        kpis = simulator.cumulative_kpis
        assert kpis.intervals_completed == 96
        assert len(simulator.interval_history) == 96
        # In do-nothing, all demand shows up as energy balance slack residual
        assert all(h.energy_balance_slack_mw != 0.0 for h in simulator.interval_history)

    def test_full_day_trivial_balancing_rule_zero_slack(self, simulator: Simulator):
        """Run 96 intervals with a trivial balancing rule where energy balance holds with 0 residual."""
        simulator.reset()

        for _ in range(96):
            state = simulator.current_state()
            total_re = sum(state.solar_actual.values()) + sum(state.wind_actual.values())
            total_dem = sum(state.demand_actual.values())

            b1_spec = simulator.batteries["B1"]
            b2_spec = simulator.batteries["B2"]

            if total_re >= total_dem:
                surplus = total_re - total_dem
                # Charge batteries up to available power headroom
                b1_room = (b1_spec["energy_mwh"] * b1_spec["soc_max"] - state.battery_soc["B1"]) / (0.95 * 0.25)
                b1_ch = min(b1_spec["power_mw"], max(0.0, b1_room), surplus)
                rem_surplus = surplus - b1_ch

                b2_room = (b2_spec["energy_mwh"] * b2_spec["soc_max"] - state.battery_soc["B2"]) / (0.95 * 0.25)
                b2_ch = min(b2_spec["power_mw"], max(0.0, b2_room), rem_surplus)
                rem_surplus -= b2_ch

                # Export remainder up to grid export limit
                grid_exp = min(state.grid_export_limit_mw, rem_surplus)
                rem_surplus -= grid_exp

                # Curtail any leftover surplus
                curt = rem_surplus
                # Distribute curtailment across solar farms
                solar_curt = {}
                solar_left = curt
                for s_id, s_mw in state.solar_actual.items():
                    c_val = min(s_mw, solar_left)
                    solar_curt[s_id] = c_val
                    solar_left -= c_val

                action = DispatchAction(
                    battery_charge={"B1": b1_ch, "B2": b2_ch},
                    grid_export=grid_exp,
                    solar_curtailment=solar_curt,
                )
            else:
                deficit = total_dem - total_re
                # Discharge batteries up to available energy
                b1_avail = (state.battery_soc["B1"] - b1_spec["energy_mwh"] * b1_spec["soc_min"]) * 0.95 / 0.25
                b1_dis = min(b1_spec["power_mw"], max(0.0, b1_avail), deficit)
                rem_deficit = deficit - b1_dis

                b2_avail = (state.battery_soc["B2"] - b2_spec["energy_mwh"] * b2_spec["soc_min"]) * 0.95 / 0.25
                b2_dis = min(b2_spec["power_mw"], max(0.0, b2_avail), rem_deficit)
                rem_deficit -= b2_dis

                # Import remainder up to grid import limit
                grid_imp = min(state.grid_import_limit_mw, rem_deficit)
                rem_deficit -= grid_imp

                # Shortfall any remaining deficit across consumers
                shortfall = {}
                dem_left = rem_deficit
                for c_id, c_mw in state.demand_actual.items():
                    crit = simulator.consumers[c_id]["critical_fraction"]
                    non_crit_capacity = c_mw * (1.0 - crit)
                    sh = min(non_crit_capacity, dem_left)
                    shortfall[c_id] = sh
                    dem_left -= sh

                # If still remaining, unserved critical load
                unserved = {}
                for c_id in state.demand_actual:
                    if dem_left > 0:
                        un = min(state.demand_actual[c_id] * simulator.consumers[c_id]["critical_fraction"], dem_left)
                        unserved[c_id] = un
                        dem_left -= un

                action = DispatchAction(
                    battery_discharge={"B1": b1_dis, "B2": b2_dis},
                    grid_import=grid_imp,
                    contract_shortfall=shortfall,
                    unserved_critical=unserved,
                )

            simulator.step(action)

        # Confirm energy balance held for all 96 intervals with zero slack residual
        residuals = [abs(h.energy_balance_slack_mw) for h in simulator.interval_history]
        max_residual = max(residuals)
        assert max_residual < 1e-3, f"Energy balance residual violated: max {max_residual} MW"
        assert simulator.cumulative_kpis.total_hard_violations == 0
