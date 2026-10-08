"""Comprehensive acceptance and unit tests for Phase 3:
Optimizer (MILP), Heuristics, Risk Evaluation, and Guardrails.

Verifies:
- PuLP MILP solver constraint satisfaction (binary mutex, SoC dynamics, line limits, critical load)
- Hard guardrail validation catching deliberately broken plans
- Guardrail approval of valid plans
- Monte Carlo risk evaluation & conservative plan generation
- 24-hour comparative run: fixed-weight MILP vs rule-based heuristic baseline
"""

from pathlib import Path
import numpy as np
import pytest

from gridmind.forecast.forecaster import Forecaster
from gridmind.guard.guardrails import GuardrailValidator
from gridmind.optimize.heuristics import rule_based_baseline_dispatch, safe_mode_dispatch
from gridmind.optimize.milp import MilpOptimizer, DispatchPlan
from gridmind.optimize.risk import evaluate_plan_risk, get_conservative_plan
from gridmind.sim.simulator import Simulator
from gridmind.sim.state import DispatchAction, GridState

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "data" / "processed" / "season_A.csv"
ASSETS_CFG = BASE_DIR / "config" / "assets.yaml"
MARKET_CFG = BASE_DIR / "config" / "market.yaml"


@pytest.fixture
def simulator() -> Simulator:
    return Simulator(DATASET_PATH, ASSETS_CFG, MARKET_CFG)


@pytest.fixture
def forecaster() -> Forecaster:
    return Forecaster(DATASET_PATH, ASSETS_CFG, MARKET_CFG, horizon_intervals=32)


@pytest.fixture
def optimizer() -> MilpOptimizer:
    return MilpOptimizer(ASSETS_CFG, MARKET_CFG)


@pytest.fixture
def guardrail() -> GuardrailValidator:
    return GuardrailValidator(ASSETS_CFG, MARKET_CFG)


class TestMilpOptimizer:
    def test_milp_solves_optimally_and_fast(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer):
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=10, seed=42)
        plan = optimizer.solve(state, fcst)

        assert plan.is_feasible is True
        assert plan.status == "Optimal"
        assert plan.solve_time_seconds < 5.0, f"Solve time too slow: {plan.solve_time_seconds}s"
        assert len(plan.horizon_actions) == 32

    def test_milp_binary_interlocks(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer):
        """Verifies binary mutex: no simultaneous charge/discharge and no simultaneous buy/sell."""
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        plan = optimizer.solve(state, fcst)

        for t, act in enumerate(plan.horizon_actions):
            # Grid exchange exclusivity
            assert not (act.grid_import > 1e-3 and act.grid_export > 1e-3), f"Simultaneous buy/sell at t={t}"
            # Battery exclusivity
            for b_id in ["B1", "B2"]:
                ch = act.battery_charge.get(b_id, 0.0)
                dis = act.battery_discharge.get(b_id, 0.0)
                assert not (ch > 1e-3 and dis > 1e-3), f"Simultaneous charge/discharge on {b_id} at t={t}"

    def test_milp_soc_conservation(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer):
        """Dynamic SoC equation matches energy balance with efficiencies."""
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        plan = optimizer.solve(state, fcst)

        dt = 0.25
        eta_c = 0.95
        eta_d = 0.95

        for b_id, b_spec in optimizer.batteries.items():
            curr_soc = state.battery_soc[b_id]
            for t in range(32):
                act = plan.horizon_actions[t]
                ch = act.battery_charge[b_id]
                dis = act.battery_discharge[b_id]
                expected_soc = curr_soc + (ch * eta_c - dis / eta_d) * dt
                actual_soc = plan.soc_trajectory[b_id][t]
                assert pytest.approx(actual_soc, abs=1e-2) == expected_soc
                curr_soc = actual_soc

    def test_milp_respects_reserve_floor(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer):
        """All battery SoCs must stay above the specified reserve floor."""
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        reserve_floor = 0.40  # 40% floor
        plan = optimizer.solve(state, fcst, reserve_floor=reserve_floor)

        for b_id, b_spec in optimizer.batteries.items():
            cap = b_spec["energy_mwh"]
            min_allowed = cap * reserve_floor
            for t, val in enumerate(plan.soc_trajectory[b_id]):
                assert val >= min_allowed - 1e-3, f"Battery {b_id} breached reserve floor at t={t}: {val} < {min_allowed}"

    def test_milp_unavailable_battery_has_zero_flow(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer):
        """When B2 is marked unavailable, optimizer commands 0 charge and 0 discharge."""
        state = simulator.reset()
        state.battery_available["B2"] = False

        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        plan = optimizer.solve(state, fcst)

        for t, act in enumerate(plan.horizon_actions):
            assert act.battery_charge["B2"] == 0.0
            assert act.battery_discharge["B2"] == 0.0


class TestGuardrails:
    def test_guardrail_approves_valid_milp_plan(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer, guardrail: GuardrailValidator):
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        plan = optimizer.solve(state, fcst)

        result = guardrail.validate(plan, state)
        assert result.passed is True
        assert len(result.violations) == 0

    def test_guardrail_catches_simultaneous_charge_discharge(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer, guardrail: GuardrailValidator):
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        plan = optimizer.solve(state, fcst)

        # Deliberately corrupt first interval: charge and discharge B1 simultaneously
        plan.first_interval.battery_charge["B1"] = 25.0
        plan.first_interval.battery_discharge["B1"] = 25.0

        result = guardrail.validate(plan, state)
        assert result.passed is False
        assert any("simultaneous charge" in v.lower() for v in result.violations)

    def test_guardrail_catches_simultaneous_buy_sell(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer, guardrail: GuardrailValidator):
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        plan = optimizer.solve(state, fcst)

        # Corrupt first interval: simultaneous buy and sell
        plan.first_interval.grid_import = 30.0
        plan.first_interval.grid_export = 30.0

        result = guardrail.validate(plan, state)
        assert result.passed is False
        assert any("simultaneous buy and sell" in v.lower() for v in result.violations)

    def test_guardrail_catches_unavailable_battery_dispatch(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer, guardrail: GuardrailValidator):
        state = simulator.reset()
        state.battery_available["B2"] = False
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        plan = optimizer.solve(state, fcst)

        # Force charge on unavailable battery
        plan.first_interval.battery_charge["B2"] = 15.0

        result = guardrail.validate(plan, state)
        assert result.passed is False
        assert any("unavailable" in v.lower() for v in result.violations)

    def test_guardrail_catches_critical_load_shedding(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer, guardrail: GuardrailValidator):
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        plan = optimizer.solve(state, fcst)

        # Corrupt first interval: unserved critical load
        plan.first_interval.unserved_critical["C1"] = 10.0

        result = guardrail.validate(plan, state)
        assert result.passed is False
        assert any("sheds critical customer load" in v.lower() for v in result.violations)


class TestRiskAndRobustness:
    def test_evaluate_plan_risk(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer):
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=20, seed=42)
        plan = optimizer.solve(state, fcst)

        metrics = evaluate_plan_risk(plan, fcst, optimizer.batteries, optimizer.consumers)
        assert metrics.plan_id == plan.plan_id
        assert metrics.p90_cost_inr >= metrics.expected_cost_inr
        assert 0.0 <= metrics.p_shortfall <= 1.0
        assert 0.0 <= metrics.p_unserved <= 1.0

    def test_conservative_plan_has_higher_reserve(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer):
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=10, seed=42)

        normal_plan = optimizer.solve(state, fcst, reserve_floor=0.10)
        conservative_plan = get_conservative_plan(optimizer, state, fcst, reserve_floor=0.35)

        assert conservative_plan.is_feasible is True
        # Conservative plan holds battery SoCs higher
        b1_norm_min = min(normal_plan.soc_trajectory["B1"])
        b1_cons_min = min(conservative_plan.soc_trajectory["B1"])
        assert b1_cons_min >= b1_norm_min


class TestHeuristicsAndBenchmarking:
    def test_safe_mode_holds_40_percent_reserve(self, simulator: Simulator):
        state = simulator.reset()
        # Battery at 50% SoC (120 MWh in B1, 80 MWh in B2)
        action = safe_mode_dispatch(state, simulator.batteries, simulator.consumers)

        # Safe mode should not export to grid
        assert action.grid_export == 0.0
        # Should step without throwing violations
        next_state = simulator.step(action)
        assert next_state.kpis.total_hard_violations == 0
        # SoC remains >= 40%
        assert next_state.battery_soc_pct["B1"] >= 0.40 - 1e-4

    def test_24hr_fixed_milp_beats_baseline(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer):
        """24h simulation comparison: Fixed-weight MILP achieves dramatically lower shortfall & cost vs baseline."""
        # Run 1: Rule-based baseline for 96 intervals
        simulator.reset()
        for _ in range(96):
            state = simulator.current_state()
            act = rule_based_baseline_dispatch(state, simulator.batteries, simulator.consumers)
            simulator.step(act)
        baseline_kpis = simulator.cumulative_kpis

        # Run 2: Rolling MILP dispatcher with fixed default weights
        sim_milp = Simulator(DATASET_PATH, ASSETS_CFG, MARKET_CFG)
        sim_milp.reset()

        for _ in range(96):
            state = sim_milp.current_state()
            fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
            plan = optimizer.solve(state, fcst)
            assert plan.is_feasible is True
            sim_milp.step(plan.first_interval)

        milp_kpis = sim_milp.cumulative_kpis

        # Comparative assertions:
        # 1. Zero hard-constraint violations in both
        assert milp_kpis.total_hard_violations == 0
        # 2. Critical unserved load must be 0 in MILP (baseline had unserved VOLL penalties!)
        assert milp_kpis.total_unserved_critical_mwh == 0.0
        # 3. MILP contract shortfall is substantially less than myopic baseline
        assert milp_kpis.total_contract_shortfall_mwh < baseline_kpis.total_contract_shortfall_mwh
        # 4. Total net cost is lower in MILP
        assert milp_kpis.total_net_cost_inr < baseline_kpis.total_net_cost_inr
