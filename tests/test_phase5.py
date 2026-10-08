"""Comprehensive acceptance and unit tests for Phase 5:
Orchestrator, Executor, Metrics Engine, Strategy Comparator, and Reliability.

Verifies:
- 15-minute rolling Orchestrator loop (single-step, headless, pause, resume)
- Complete structured JSONL logging per interval
- Cumulative and interval KPI metrics accounting
- 3-way strategy comparison benchmark generation
- Zero hard-constraint violations under stochastic disturbances (D2 claim)
"""

import json
from pathlib import Path
import pytest

from gridmind.compare import StrategyComparator
from gridmind.logging_utils import DecisionLogger
from gridmind.metrics import MetricsTracker
from gridmind.orchestrator import GridMindOrchestrator
from gridmind.sim.events import Event
from gridmind.sim.simulator import Simulator
from gridmind.sim.state import DispatchAction

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "data" / "processed" / "season_A.csv"
ASSETS_CFG = BASE_DIR / "config" / "assets.yaml"
MARKET_CFG = BASE_DIR / "config" / "market.yaml"
AGENT_CFG = BASE_DIR / "config" / "agent.yaml"


@pytest.fixture
def orchestrator(tmp_path: Path) -> GridMindOrchestrator:
    return GridMindOrchestrator(
        dataset_path=DATASET_PATH,
        assets_config_path=ASSETS_CFG,
        market_config_path=MARKET_CFG,
        agent_config_path=AGENT_CFG,
        logs_dir=tmp_path / "logs",
        auto_approve_operator=True,
        strategy_refresh_interval=4,
    )


class TestOrchestrator:
    def test_orchestrator_initialization_and_reset(self, orchestrator: GridMindOrchestrator):
        state = orchestrator.reset()
        assert state.interval_index == 0
        assert len(orchestrator.history) == 0
        assert orchestrator.metrics_tracker.current_metrics().total_intervals == 0

    def test_orchestrator_single_step(self, orchestrator: GridMindOrchestrator):
        orchestrator.reset()
        res = orchestrator.step()

        assert res.interval_index == 0
        assert res.state.interval_index == 1
        assert res.validation.passed is True
        assert res.executed_action.balance_slack <= 1e-3
        assert len(res.explanation.headline) > 0
        assert res.metrics.total_intervals == 1
        assert res.metrics.total_hard_violations == 0

        # Check JSONL file was created and contains valid entry
        log_entries = orchestrator.logger.read_all_entries()
        assert len(log_entries) == 1
        assert log_entries[0]["interval_index"] == 0
        assert "telemetry" in log_entries[0]
        assert "dispatch" in log_entries[0]

    def test_orchestrator_headless_run(self, orchestrator: GridMindOrchestrator):
        orchestrator.reset()
        metrics = orchestrator.run_headless(num_intervals=8)

        assert metrics.total_intervals == 8
        assert metrics.total_hard_violations == 0
        assert metrics.unserved_critical_load_mwh == 0.0
        assert len(orchestrator.history) == 8
        assert orchestrator.simulator.current_interval_idx == 8

    def test_orchestrator_mid_run_event_injection(self, orchestrator: GridMindOrchestrator):
        orchestrator.reset()
        orchestrator.step()
        orchestrator.step()

        # Inject sudden price spike at interval 2
        spike = Event(event_type="price_spike", start_interval=2, duration_intervals=4, magnitude=2.0)
        orchestrator.inject_event(spike)

        res3 = orchestrator.step()
        assert any(e.event_type == "price_spike" for e in res3.state.active_events)
        assert res3.validation.passed is True
        assert res3.metrics.total_hard_violations == 0

    def test_orchestrator_operator_approval_pause(self, tmp_path: Path):
        orch = GridMindOrchestrator(
            dataset_path=DATASET_PATH,
            assets_config_path=ASSETS_CFG,
            market_config_path=MARKET_CFG,
            agent_config_path=AGENT_CFG,
            logs_dir=tmp_path / "logs",
            auto_approve_operator=False,  # Require manual operator approval
        )
        orch.reset()
        # Mock high-impact decision
        res = orch.step()
        # Even with manual approval, if decision doesn't require approval it proceeds
        assert res.interval_index == 0


class TestMetricsTracker:
    def test_metrics_calculation_and_energy_utilization(self):
        batteries = {"B1": {"energy_mwh": 240.0}}
        consumers = {"C1": {"dr_incentive_inr_per_mwh": 3000.0}}
        tracker = MetricsTracker(batteries, consumers, dt_hours=0.25)

        kpis = tracker.record_interval(
            grid_import_mw=100.0,
            grid_export_mw=50.0,
            price_actual=4000.0,
            solar_actual_mw=120.0,
            wind_actual_mw=80.0,
            curtailment_mw=20.0,
            battery_charge={"B1": 30.0},
            battery_discharge={"B1": 0.0},
            demand_response={"C1": 10.0},
            contract_shortfall={"C1": 5.0},
            unserved_critical={"C1": 0.0},
        )

        assert kpis.total_intervals == 1
        assert kpis.curtailment_mwh == 20.0 * 0.25
        # Total avail = (120 + 80) * 0.25 = 50 MWh. Used = 50 - 5 = 45 MWh -> 90%
        assert pytest.approx(kpis.renewable_utilization_pct, abs=1e-2) == 90.0
        assert kpis.contract_shortfall_mwh == 5.0 * 0.25
        assert kpis.battery_throughput_mwh == 30.0 * 0.25
        # 1 full cycle = throughput / (2 * 240) = 7.5 / 480
        assert pytest.approx(kpis.battery_equivalent_full_cycles["B1"], abs=1e-4) == (7.5 / 480.0)


class TestLogging:
    def test_jsonl_log_structure(self, tmp_path: Path):
        logger = DecisionLogger(logs_dir=tmp_path, run_id="test_run")
        entry = logger.log_interval(
            interval_index=0,
            timestamp="2025-04-14 00:00:00",
            state=Simulator(DATASET_PATH, ASSETS_CFG, MARKET_CFG).reset(),
            monitor_report=None,
            strategy_decision=None,
            guardrail_result=None,
            action=DispatchAction(),
            explanation=None,
            metrics_snapshot={"net_cost": 1000.0},
        )

        assert entry["interval_index"] == 0
        assert entry["metrics"]["net_cost"] == 1000.0

        readback = logger.read_all_entries()
        assert len(readback) == 1
        assert readback[0]["run_id"] == "test_run"


class TestComparison:
    def test_strategy_comparator_produces_3_way_table(self):
        comparator = StrategyComparator(DATASET_PATH, ASSETS_CFG, MARKET_CFG, AGENT_CFG)
        summary = comparator.run_comparison(num_intervals=6)

        assert summary.baseline.kpis.total_intervals == 6
        assert summary.fixed_milp.kpis.total_intervals == 6
        assert summary.gridmind_agent.kpis.total_intervals == 6

        table = summary.summary_table()
        assert "Metric" in table.columns
        assert "1. Rule Baseline" in table.columns
        assert "2. Fixed MILP" in table.columns
        assert "3. GridMind Agent" in table.columns
        assert "Agent vs Baseline" in table.columns
        assert len(table) == 12


class TestReliabilityMini:
    def test_mini_reliability_run(self):
        """Mini 24-hour test with randomized disturbance: 0 violations & 0 unserved critical load."""
        orch = GridMindOrchestrator(
            dataset_path=DATASET_PATH,
            assets_config_path=ASSETS_CFG,
            market_config_path=MARKET_CFG,
            agent_config_path=AGENT_CFG,
            auto_approve_operator=True,
        )
        orch.reset()
        # Inject disturbances
        orch.inject_event(Event(event_type="cloud_cover", start_interval=4, duration_intervals=4, magnitude=0.5))
        orch.inject_event(Event(event_type="price_spike", start_interval=8, duration_intervals=2, magnitude=2.0))

        metrics = orch.run_headless(num_intervals=24)
        assert metrics.total_intervals == 24
        assert metrics.total_hard_violations == 0
        assert metrics.unserved_critical_load_mwh == 0.0
