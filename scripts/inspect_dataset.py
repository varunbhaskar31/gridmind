"""Inspect processed GridMind datasets and print clean daily summaries.

Displays:
- Daily total and peak generation for solar (S1-S5) and wind (W1-W3)
- Daily demand statistics across consumers (C1-C4)
- Daily market price distributions (min, max, mean ₹/MWh)
- Capacity check and NaN verification
"""

import sys
from pathlib import Path
import pandas as pd


def summarize_season(csv_path: Path) -> None:
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist. Run build_dataset first.")
        return

    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.date

    solar_cols = [c for c in df.columns if c.startswith("solar_")]
    wind_cols = [c for c in df.columns if c.startswith("wind_") and not c.startswith("wind_speed")]
    demand_cols = [c for c in df.columns if c.startswith("demand_")]

    df["total_solar_mw"] = df[solar_cols].sum(axis=1)
    df["total_wind_mw"] = df[wind_cols].sum(axis=1)
    df["total_re_mw"] = df["total_solar_mw"] + df["total_wind_mw"]
    df["total_demand_mw"] = df[demand_cols].sum(axis=1)

    print("=" * 80)
    print(f"GRIDMIND DATASET SUMMARY: {csv_path.name}")
    print(f"Period: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Total 15-min intervals: {len(df)} | Missing / NaN values: {df.isna().sum().sum()}")
    print("=" * 80)

    # Group by date for daily summaries
    grouped = df.groupby("date")

    print("\n[DAILY ENERGY & LOAD TOTALS (MWh)] (1 interval = 0.25 h)")
    print(f"{'Date':<12} | {'Solar (MWh)':<12} | {'Wind (MWh)':<12} | {'Total RE (MWh)':<14} | {'Demand (MWh)':<12} | {'Avg Price (₹)':<12}")
    print("-" * 86)

    for dt, group in grouped:
        # Energy in MWh = sum(MW * 0.25)
        sol_mwh = group["total_solar_mw"].sum() * 0.25
        wnd_mwh = group["total_wind_mw"].sum() * 0.25
        re_mwh = group["total_re_mw"].sum() * 0.25
        dem_mwh = group["total_demand_mw"].sum() * 0.25
        avg_price = group["price"].mean()

        print(f"{str(dt):<12} | {sol_mwh:>12.1f} | {wnd_mwh:>12.1f} | {re_mwh:>14.1f} | {dem_mwh:>12.1f} | {avg_price:>12.1f}")

    print("\n[PEAK CAPACITIES OBSERVED (MW)]")
    print(f"Max Total Solar:  {df['total_solar_mw'].max():.1f} MW (Nameplate: 500.0 MW)")
    print(f"Max Total Wind:   {df['total_wind_mw'].max():.1f} MW (Nameplate: 240.0 MW)")
    print(f"Max Total Demand: {df['total_demand_mw'].max():.1f} MW (Base Total: ~300.0 MW)")
    print(f"Price Range:      ₹{df['price'].min():.1f} to ₹{df['price'].max():.1f} / MWh")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data" / "processed"

    seasons = ["season_A.csv", "season_B.csv"]
    for s in seasons:
        summarize_season(data_dir / s)
