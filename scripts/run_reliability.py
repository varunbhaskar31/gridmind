"""Multi-day reliability stress-test suite for GridMind.

Fulfills D2 / F3 hackathon claims:
- D2 Claim: High demonstrable reliability -> Provably ZERO hard-constraint violations
  and zero critical load shedding across >= 30 simulated days under extreme conditions.
- F3 Claim: Multi-day rolling simulation with randomized forecast errors and injected disturbances.

Saves verified metrics to `data/processed/reliability_summary.json` for dashboard and README display.
"""

from dataclasses import asdict
import json
from pathlib import Path
import random
import time
import numpy as np

from gridmind.orchestrator import GridMindOrchestrator
from gridmind.sim.events import Event

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
SEASON_A = DATA_DIR / "season_A.csv"
SEASON_B = DATA_DIR / "season_B.csv"
ASSETS_CFG = BASE_DIR / "config" / "assets.yaml"
MARKET_CFG = BASE_DIR / "config" / "market.yaml"
AGENT_CFG = BASE_DIR / "config" / "agent.yaml"
SUMMARY_OUTPUT = DATA_DIR / "reliability_summary.json"


def generate_random_events_for_day(day_seed: int) -> list[Event]:
    """Inject stochastic disturbance events typical of Indian grid operations."""
    rng = random.Random(day_seed)
    events: list[Event] = []

    # 1. Cloud Cover Event (30% probability per day)
    if rng.random() < 0.35:
        start = rng.randint(36, 64)  # between 09:00 and 16:00
        dur = rng.randint(4, 12)     # 1 to 3 hours
        mag = rng.uniform(0.40, 0.85)
        events.append(Event(
            event_type="cloud_cover",
            start_interval=start,
            duration_intervals=dur,
            magnitude=mag,
            affected_assets=["S1", "S2"] if rng.random() < 0.5 else ["S3", "S4"],
            description="Stochastic cloud formation over Pavagada cluster",
        ))

    # 2. Exchange Price Spike (25% probability per day during peak evening)
    if rng.random() < 0.25:
        start = rng.randint(72, 84)  # 18:00 to 21:00 peak
        dur = rng.randint(2, 6)
        mag = rng.uniform(1.8, 2.5)  # price spike multiplier
        events.append(Event(
            event_type="price_spike",
            start_interval=start,
            duration_intervals=dur,
            magnitude=mag,
            description="IEX evening peak price spike",
        ))

    # 3. Transmission Line Derating (15% probability per day)
    if rng.random() < 0.15:
        start = rng.randint(20, 60)
        dur = rng.randint(8, 16)
        export_cap = rng.uniform(80.0, 120.0)
        events.append(Event(
            event_type="line_constraint",
            start_interval=start,
            duration_intervals=dur,
            magnitude=export_cap,
            extra_params={"export_limit_mw": export_cap},
            description="Corridor transmission line congestion",
        ))

    # 4. Battery Asset Outage (10% probability per day)
    if rng.random() < 0.10:
        start = rng.randint(10, 50)
        dur = rng.randint(8, 20)
        target = rng.choice(["B1", "B2"])
        events.append(Event(
            event_type="battery_outage",
            start_interval=start,
            duration_intervals=dur,
            magnitude=1.0,
            affected_assets=[target],
            description=f"Inverter trip causing forced outage on {target}",
        ))

    # 5. Severe Storm Alert (5% probability per day)
    if rng.random() < 0.05:
        start = rng.randint(16, 40)
        dur = rng.randint(8, 16)
        events.append(Event(
            event_type="storm_alert",
            start_interval=start,
            duration_intervals=dur,
            magnitude=0.75,
            extra_params={"wind_cut_out": True},
            description="Advance severe cyclone warning and storm alert",
        ))

    return events


def run_reliability_suite(total_days: int = 30) -> dict:
    print("=" * 80)
    print(f" STARTING GRIDMIND RELIABILITY SUITE: {total_days} SIMULATED DAYS (2,880 INTERVALS)")
    print(" Position Claim: D2 (Zero Hard Violations) / F3 (Rolling Uncertainty Simulation)")
    print("=" * 80)

    start_time = time.time()
    daily_records = []
    total_intervals = 0
    total_hard_violations = 0
    total_unserved_critical_mwh = 0.0
    total_events_injected = 0
    safe_mode_total = 0

    intervals_per_day = 96
    seasons = [SEASON_A, SEASON_B]

    for day in range(1, total_days + 1):
        day_seed = 1000 + day
        dataset_path = seasons[(day - 1) % len(seasons)]
        events = generate_random_events_for_day(day_seed)
        total_events_injected += len(events)

        orchestrator = GridMindOrchestrator(
            dataset_path=dataset_path,
            assets_config_path=ASSETS_CFG,
            market_config_path=MARKET_CFG,
            agent_config_path=AGENT_CFG,
            auto_approve_operator=True,
            strategy_refresh_interval=4,
        )
        orchestrator.reset()
        for e in events:
            orchestrator.inject_event(e)

        # Execute 96 intervals for this day
        day_net_cost = 0.0
        day_shortfall = 0.0
        day_curtailment = 0.0
        day_carbon = 0.0
        day_violations = 0

        for _ in range(intervals_per_day):
            step_res = orchestrator.step()
            total_intervals += 1
            if step_res.is_safe_mode:
                safe_mode_total += 1
            if not step_res.validation.passed:
                total_hard_violations += len(step_res.validation.violations)
                day_violations += len(step_res.validation.violations)

            u_crit = sum(step_res.executed_action.unserved_critical.values()) * 0.25
            total_unserved_critical_mwh += u_crit

        day_kpis = orchestrator.metrics_tracker.current_metrics()
        daily_records.append({
            "day": day,
            "season": "Season A (Summer)" if dataset_path == SEASON_A else "Season B (Monsoon)",
            "events_count": len(events),
            "net_cost_inr": round(day_kpis.total_net_cost_inr, 2),
            "carbon_tco2": round(day_kpis.carbon_emissions_tco2, 2),
            "shortfall_mwh": round(day_kpis.contract_shortfall_mwh, 2),
            "curtailment_mwh": round(day_kpis.curtailment_mwh, 2),
            "renewable_util_pct": round(day_kpis.renewable_utilization_pct, 2),
            "violations": day_violations,
        })

        if day % 5 == 0 or day == total_days:
            elapsed = time.time() - start_time
            print(
                f"  * Completed Day {day:02d}/{total_days:02d} | Total Intervals: {total_intervals} | "
                f"Violations: {total_hard_violations} | Unserved Critical: {total_unserved_critical_mwh:.4f} MWh | "
                f"Elapsed: {elapsed:.1f}s"
            )

    elapsed_total = time.time() - start_time

    # Summary Statistics
    net_costs = [r["net_cost_inr"] for r in daily_records]
    shortfalls = [r["shortfall_mwh"] for r in daily_records]
    curtailments = [r["curtailment_mwh"] for r in daily_records]
    emissions = [r["carbon_tco2"] for r in daily_records]
    utilizations = [r["renewable_util_pct"] for r in daily_records]

    summary = {
        "status": "PASSED" if total_hard_violations == 0 and total_unserved_critical_mwh < 1e-4 else "FAILED",
        "position_claim": "D2 (Zero Hard Violations) / F3 (Rolling Uncertainty Simulation)",
        "total_simulated_days": total_days,
        "total_intervals_executed": total_intervals,
        "total_events_injected": total_events_injected,
        "total_hard_violations": total_hard_violations,
        "total_unserved_critical_mwh": round(total_unserved_critical_mwh, 6),
        "safe_mode_intervals": safe_mode_total,
        "elapsed_seconds": round(elapsed_total, 2),
        "mean_daily_net_cost_inr": round(float(np.mean(net_costs)), 2),
        "p90_daily_net_cost_inr": round(float(np.percentile(net_costs, 90)), 2),
        "mean_daily_shortfall_mwh": round(float(np.mean(shortfalls)), 2),
        "mean_daily_curtailment_mwh": round(float(np.mean(curtailments)), 2),
        "mean_daily_emissions_tco2": round(float(np.mean(emissions)), 2),
        "mean_renewable_utilization_pct": round(float(np.mean(utilizations)), 2),
        "daily_breakdown": daily_records,
    }

    SUMMARY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 80)
    print(f" RELIABILITY TEST VERDICT: {summary['status']}")
    print(f" - Hard Safety Violations:       {total_hard_violations}  (Target: 0)")
    print(f" - Unserved Critical Load:       {total_unserved_critical_mwh:.6f} MWh (Target: 0)")
    print(f" - Total Simulated Days:         {total_days} (2,880 intervals)")
    print(f" - Total Disturbances Handled:   {total_events_injected} events")
    print(f" - Mean Daily Net Cost:          ₹{summary['mean_daily_net_cost_inr']:,.2f}")
    print(f" - Mean Renewable Utilization:   {summary['mean_renewable_utilization_pct']:.1f}%")
    print(f" Saved artifact: {SUMMARY_OUTPUT}")
    print("=" * 80 + "\n")

    assert total_hard_violations == 0, f"D2 violation: observed {total_hard_violations} safety violations!"
    assert total_unserved_critical_mwh < 1e-4, f"D2 violation: observed {total_unserved_critical_mwh} unserved critical load!"
    return summary


if __name__ == "__main__":
    run_reliability_suite(total_days=30)
