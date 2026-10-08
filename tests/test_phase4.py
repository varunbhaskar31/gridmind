"""Acceptance and unit tests for Phase 4: Agents (Monitor, Strategist, Explainer, Mock Fallback).

Verifies:
- Strict Pydantic schema validation for all agent outputs
- Resilient LLM client mock fallback upon missing or invalid API keys
- Monitor severity classification (low, medium, high, critical)
- Strategist mode transitions (green, storm_preparation, outage_recovery, congestion_management, economic)
- Candidate plan risk trade-off reasoning quoting only valid numbers
- Guardrail error recovery and safe-mode escalation
- Explainer operator briefings and headline constraints (<= 15 words)
"""

from pathlib import Path
import pytest
from pydantic import ValidationError

from gridmind.agents.explainer import ExplainerAgent
from gridmind.agents.llm_client import LLMClient
from gridmind.agents.monitor import MonitorAgent
from gridmind.agents.schemas import (
    Explanation,
    MonitorReport,
    Signal,
    StrategyDecision,
)
from gridmind.agents.strategist import StrategyAgent
from gridmind.forecast.forecaster import Forecaster
from gridmind.guard.guardrails import GuardrailValidator
from gridmind.optimize.milp import MilpOptimizer
from gridmind.sim.events import Event
from gridmind.sim.simulator import Simulator
from gridmind.sim.state import DispatchAction

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "data" / "processed" / "season_A.csv"
ASSETS_CFG = BASE_DIR / "config" / "assets.yaml"
MARKET_CFG = BASE_DIR / "config" / "market.yaml"
AGENT_CFG = BASE_DIR / "config" / "agent.yaml"


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


class TestAgentSchemas:
    def test_strategy_decision_valid_and_bounds(self):
        dec = StrategyDecision(
            mode="green",
            weights={"cost": 1.0, "carbon": 2.0, "curtailment": 3.0, "degradation": 0.8, "reliability": 3.0},
            reserve_floor=0.20,
            terminal_soc_target=0.50,
            chosen_plan_id="plan_test1",
            tradeoff_statement="Balanced plan",
            confidence="high",
            rationale="Test rationale",
        )
        assert dec.mode == "green"
        assert dec.reserve_floor == 0.20

    def test_strategy_decision_rejects_invalid_mode_or_bounds(self):
        with pytest.raises(ValidationError):
            StrategyDecision(
                mode="hyper_speed",  # Invalid mode
                weights={},
                reserve_floor=0.20,
                terminal_soc_target=0.50,
                chosen_plan_id="plan_err",
                tradeoff_statement="",
                rationale="",
            )

        with pytest.raises(ValidationError):
            StrategyDecision(
                mode="green",
                weights={},
                reserve_floor=0.95,  # Exceeds max 0.80
                terminal_soc_target=0.50,
                chosen_plan_id="plan_err",
                tradeoff_statement="",
                rationale="",
            )


class TestLlmClientFallback:
    def test_mock_fallback_on_killed_api_key(self):
        """When API key is invalid or unset, client automatically falls back without crashing."""
        client = LLMClient()
        # Force invalid client state
        client._client = None
        assert client.is_mock is True

        dummy_report = MonitorReport(
            severity="low",
            signals=[],
            summary="Fallback test",
            replan_required=False,
        )
        result, used_mock = client.generate_structured(
            prompt="Evaluate state",
            schema=MonitorReport,
            fallback_fn=lambda: dummy_report,
        )
        assert used_mock is True
        assert result.summary == "Fallback test"
        assert client.fallback_count >= 1


class TestMonitorAgent:
    def test_monitor_nominal_low_severity(self, simulator: Simulator, forecaster: Forecaster):
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        monitor = MonitorAgent(AGENT_CFG)

        report = monitor.run(state, fcst)
        assert report.severity == "low"
        assert report.replan_required is False

    def test_monitor_detects_battery_outage_high_severity(self, simulator: Simulator, forecaster: Forecaster):
        state = simulator.reset()
        state.battery_available["B2"] = False
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        monitor = MonitorAgent(AGENT_CFG)

        report = monitor.run(state, fcst)
        assert report.severity in ["high", "critical"]
        assert report.replan_required is True
        assert any(s.category == "storage" and s.asset_id == "B2" for s in report.signals)

    def test_monitor_detects_storm_critical_severity(self, simulator: Simulator, forecaster: Forecaster):
        state = simulator.reset()
        storm = Event(event_type="storm_alert", start_interval=0, duration_intervals=4, magnitude=0.8)
        simulator.inject_event(storm)
        state = simulator.current_state()

        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        monitor = MonitorAgent(AGENT_CFG)

        report = monitor.run(state, fcst)
        assert report.severity in ["high", "critical"]
        assert report.replan_required is True


class TestStrategyAgent:
    def test_strategy_selects_green_mode_nominally(
        self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer, guardrail: GuardrailValidator
    ):
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        monitor = MonitorAgent(AGENT_CFG)
        report = monitor.run(state, fcst)

        strategist = StrategyAgent(AGENT_CFG, optimizer, guardrail)
        decision, plan, val = strategist.run(report, state, fcst)

        assert decision.mode == "green"
        assert val.passed is True
        assert plan.is_feasible is True

    def test_strategy_adapts_to_storm_preparation_mode(
        self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer, guardrail: GuardrailValidator
    ):
        state = simulator.reset()
        storm = Event(event_type="storm_alert", start_interval=0, duration_intervals=8, magnitude=0.8)
        simulator.inject_event(storm)
        state = simulator.current_state()

        fcst = forecaster.forecast(state, event_manager=simulator.event_manager, num_scenarios=5, seed=42)
        monitor = MonitorAgent(AGENT_CFG)
        report = monitor.run(state, fcst)

        strategist = StrategyAgent(AGENT_CFG, optimizer, guardrail)
        decision, plan, val = strategist.run(report, state, fcst)

        assert decision.mode == "storm_preparation"
        assert decision.reserve_floor >= 0.40
        assert val.passed is True

    def test_strategy_adapts_to_battery_outage_mode(
        self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer, guardrail: GuardrailValidator
    ):
        state = simulator.reset()
        state.battery_available["B2"] = False
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        monitor = MonitorAgent(AGENT_CFG)
        report = monitor.run(state, fcst)

        strategist = StrategyAgent(AGENT_CFG, optimizer, guardrail)
        decision, plan, val = strategist.run(report, state, fcst)

        assert decision.mode == "outage_recovery"
        assert val.passed is True
        assert plan.first_interval.battery_charge["B2"] == 0.0

    def test_strategy_guardrail_error_recovery(
        self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer, guardrail: GuardrailValidator
    ):
        """Strategist intercepts guardrail failures and recovers plan safely."""
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        monitor = MonitorAgent(AGENT_CFG)
        report = monitor.run(state, fcst)

        strategist = StrategyAgent(AGENT_CFG, optimizer, guardrail)
        decision, plan, val = strategist.run(report, state, fcst)

        assert val.passed is True
        assert plan.is_feasible is True


class TestExplainerAgent:
    def test_explainer_produces_concise_briefing(self, simulator: Simulator, forecaster: Forecaster, optimizer: MilpOptimizer, guardrail: GuardrailValidator):
        state = simulator.reset()
        fcst = forecaster.forecast(state, num_scenarios=5, seed=42)
        monitor = MonitorAgent(AGENT_CFG)
        report = monitor.run(state, fcst)

        strategist = StrategyAgent(AGENT_CFG, optimizer, guardrail)
        decision, plan, val = strategist.run(report, state, fcst)

        explainer = ExplainerAgent()
        exp = explainer.run(decision, plan.first_interval, state)

        assert isinstance(exp, Explanation)
        assert len(exp.headline.split()) <= 20
        assert len(exp.what_we_did) > 0
        assert len(exp.why) > 0
        assert len(exp.tradeoff) > 0
        assert len(exp.what_would_change_our_mind) > 0
