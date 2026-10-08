"""Demo script showcasing Phase 4: Multi-Agent Intelligence Layer.

Demonstrates:
1. Nominal conditions -> Monitor report, Strategist plan comparison, Explainer briefing
2. Storm alert disturbance -> Monitor critical detection, Strategist defensive adaptation, Guardrails validation, Explainer briefing with pivot triggers
3. Battery outage -> Monitor detection, Strategist outage recovery plan, Guardrail verification
4. Offline LLM resilience -> Seamless fallback to deterministic mock logic without crashing
"""

from pathlib import Path

from gridmind.sim.simulator import Simulator
from gridmind.sim.events import Event
from gridmind.forecast.forecaster import Forecaster
from gridmind.optimize.milp import MilpOptimizer
from gridmind.guard.guardrails import GuardrailValidator
from gridmind.agents.monitor import MonitorAgent
from gridmind.agents.strategist import StrategyAgent
from gridmind.agents.explainer import ExplainerAgent

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "data" / "processed" / "season_A.csv"
ASSETS_CFG = BASE_DIR / "config" / "assets.yaml"
MARKET_CFG = BASE_DIR / "config" / "market.yaml"
AGENT_CFG = BASE_DIR / "config" / "agent.yaml"


def run_cycle(scenario_name: str, state, fcst, monitor, strategist, explainer):
    print("=" * 80)
    print(f" SCENARIO: {scenario_name}")
    print("=" * 80)

    # 1. Monitor Agent
    report = monitor.run(state, fcst)
    print(f"\n[1. MONITOR AGENT] Severity: {report.severity.upper()} | Replan Required: {report.replan_required}")
    print(f"Summary: {report.summary}")
    print(f"Key Signals ({len(report.signals)}):")
    for s in report.signals[:3]:
        print(f"  - [{s.category.upper()}] {s.asset_id or 'System'}: {s.metric} (Ref: {s.reference_value:.1f}, Cur: {s.current_value:.1f}, Delta: {s.delta_pct:+.1f}%)")

    # 2. Strategy Agent (Tool-calling loop & Plan comparison)
    decision, plan, val = strategist.run(report, state, fcst)
    print(f"\n[2. STRATEGY AGENT] Mode Selected: {decision.mode.upper()}")
    print(f"Reserve Floor: {decision.reserve_floor:.2f} | Chosen Plan ID: {decision.chosen_plan_id}")
    print(f"Candidate Plans Evaluated: {len(decision.candidates_considered)}")
    for cand in decision.candidates_considered:
        print(f"  * Plan {cand.plan_id}: Exp Cost = ₹{cand.expected_cost:,.0f}, P(Shortfall) = {cand.p_shortfall*100:.1f}%, Min SoC = {cand.min_soc:.2f}")
    print(f"Trade-off Statement: {decision.tradeoff_statement}")
    print(f"Decision Rationale: {decision.rationale}")

    # 3. Guardrail Validation Gate
    print(f"\n[3. GUARDRAIL LAYER] Passed: {val.passed} | Severity: {val.severity}")
    if val.violations:
        print(f"Violations: {val.violations}")
    if val.warnings:
        print(f"Safety Warnings: {val.warnings}")
    act = plan.first_interval
    print(f"First-Interval Dispatch Actions: Buy = {act.grid_import:.1f} MW, Sell = {act.grid_export:.1f} MW, B1 Ch/Dis = {act.battery_charge.get('B1', 0):.1f}/{act.battery_discharge.get('B1', 0):.1f} MW, B2 Ch/Dis = {act.battery_charge.get('B2', 0):.1f}/{act.battery_discharge.get('B2', 0):.1f} MW")

    # 4. Explainer Agent (Operator Briefing)
    explanation = explainer.run(decision, plan.first_interval, state)
    print(f"\n[4. EXPLAINER AGENT] Control-Room Shift Briefing:")
    print(f"HEADLINE: \"{explanation.headline}\"")
    print(f"What We Did: {explanation.what_we_did}")
    print(f"Why: {explanation.why}")
    print(f"Accepted Trade-off: {explanation.tradeoff}")
    print(f"Pivot Triggers: {explanation.what_would_change_our_mind}")
    print("\n")


def main():
    sim = Simulator(DATASET_PATH, ASSETS_CFG, MARKET_CFG)
    fcst_tool = Forecaster(DATASET_PATH, ASSETS_CFG, MARKET_CFG, horizon_intervals=32)
    optimizer = MilpOptimizer(ASSETS_CFG, MARKET_CFG)
    guardrail = GuardrailValidator(ASSETS_CFG, MARKET_CFG)

    monitor = MonitorAgent(AGENT_CFG)
    strategist = StrategyAgent(AGENT_CFG, optimizer, guardrail)
    explainer = ExplainerAgent()

    # 1. Nominal Conditions
    state_nom = sim.reset()
    fcst_nom = fcst_tool.forecast(state_nom, num_scenarios=5, seed=42)
    run_cycle("Nominal Afternoon Operation", state_nom, fcst_nom, monitor, strategist, explainer)

    # 2. Storm Alert Disturbance
    sim_storm = Simulator(DATASET_PATH, ASSETS_CFG, MARKET_CFG)
    sim_storm.reset()
    storm_event = Event(event_type="storm_alert", start_interval=0, duration_intervals=8, magnitude=0.8)
    sim_storm.inject_event(storm_event)
    state_storm = sim_storm.current_state()
    fcst_storm = fcst_tool.forecast(state_storm, event_manager=sim_storm.event_manager, num_scenarios=5, seed=42)
    run_cycle("Severe Weather / Storm Alert Injected", state_storm, fcst_storm, monitor, strategist, explainer)

    # 3. Battery Outage Event
    sim_outage = Simulator(DATASET_PATH, ASSETS_CFG, MARKET_CFG)
    sim_outage.reset()
    outage_event = Event(event_type="battery_outage", start_interval=0, duration_intervals=12, magnitude=1.0, affected_assets=["B2"])
    sim_outage.inject_event(outage_event)
    state_outage = sim_outage.current_state()
    fcst_outage = fcst_tool.forecast(state_outage, event_manager=sim_outage.event_manager, num_scenarios=5, seed=42)
    run_cycle("Asset Failure: Battery B2 Forced Outage", state_outage, fcst_outage, monitor, strategist, explainer)


if __name__ == "__main__":
    main()
