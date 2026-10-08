"""Execute and print the 3-way strategy comparison benchmark for Phase 5."""

from pathlib import Path
from gridmind.compare import StrategyComparator
from gridmind.sim.events import Event

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "data" / "processed" / "season_A.csv"
ASSETS_CFG = BASE_DIR / "config" / "assets.yaml"
MARKET_CFG = BASE_DIR / "config" / "market.yaml"
AGENT_CFG = BASE_DIR / "config" / "agent.yaml"


def main():
    print("=" * 80)
    print(" RUNNING 3-WAY STRATEGY COMPARISON BENCHMARK (24-Hour Horizon / 96 Intervals)")
    print(" Regimes: 1. Rule-Based Baseline | 2. Fixed-Weight MILP | 3. GridMind Agent")
    print("=" * 80)

    comparator = StrategyComparator(DATASET_PATH, ASSETS_CFG, MARKET_CFG, AGENT_CFG)

    # Inject realistic disturbance events
    events = [
        Event(event_type="cloud_cover", start_interval=44, duration_intervals=8, magnitude=0.6, affected_assets=["S1", "S2"]),
        Event(event_type="price_spike", start_interval=74, duration_intervals=4, magnitude=2.2),
        Event(event_type="line_constraint", start_interval=20, duration_intervals=12, magnitude=100.0, extra_params={"export_limit_mw": 100.0}),
    ]

    summary = comparator.run_comparison(num_intervals=96, events=events)
    df = summary.summary_table()

    print("\n" + df.to_string(index=False) + "\n")

    # Save artifact for dashboard
    out_csv = BASE_DIR / "data" / "processed" / "strategy_comparison_summary.csv"
    df.to_csv(out_csv, index=False)
    print(f"Saved benchmark summary table to {out_csv}")


if __name__ == "__main__":
    main()
