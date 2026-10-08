"""CLI to build processed 15-minute simulation datasets for GridMind.

Reads assets and market configuration, downloads or synthesizes weather for Karnataka sites,
performs physical solar and wind power conversion, compiles market prices and consumer demands,
and outputs data/processed/season_A.csv or season_B.csv.
"""

import argparse
import logging
from pathlib import Path
from typing import Dict, Any
import pandas as pd
import yaml

from gridmind.data_prep.conversion import calculate_solar_mw, calculate_wind_mw
from gridmind.data_prep.demand import generate_consumer_demands
from gridmind.data_prep.prices import load_or_generate_prices
from gridmind.data_prep.weather import fetch_weather_for_asset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("build_dataset")


def get_project_root() -> Path:
    """Resolve repository root directory."""
    return Path(__file__).resolve().parent.parent.parent


def load_yaml(filepath: Path) -> Dict[str, Any]:
    """Safely load YAML configuration file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_season_dataset(
    season_code: str,
    root_dir: Path,
    use_cache: bool = True,
) -> Path:
    """Build and write the 15-minute dataset for the given season ('A' or 'B')."""
    season_code = season_code.upper()
    assets_cfg = load_yaml(root_dir / "config" / "assets.yaml")
    market_cfg = load_yaml(root_dir / "config" / "market.yaml")

    seasons = market_cfg["simulation"]["seasons"]
    if season_code not in seasons:
        raise ValueError(f"Unknown season '{season_code}'. Available: {list(seasons.keys())}")

    season_info = seasons[season_code]
    start_date = season_info["start_date"]
    end_date = season_info["end_date"]
    logger.info("Building dataset for Season %s (%s to %s)...", season_code, start_date, end_date)

    raw_dir = root_dir / "data" / "raw"
    processed_dir = root_dir / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    iex_dir = raw_dir / "iex"

    target_start = pd.to_datetime(f"{start_date} 00:00:00")
    target_end = pd.to_datetime(f"{end_date} 23:45:00")
    target_index = pd.date_range(target_start, target_end, freq="15min")

    df_out = pd.DataFrame(index=target_index)
    df_out.index.name = "timestamp"

    # 1. Process Solar Farms (S1 - S5)
    solar_farms = assets_cfg["solar_farms"]
    for s in solar_farms:
        s_id = s["id"]
        lat, lon = s["lat"], s["lon"]
        capacity = s["capacity_mw"]
        pr = s.get("performance_ratio", 0.80)

        logger.info("Processing Solar %s (%s, %.1f MW)...", s_id, s["name"], capacity)
        w_df = fetch_weather_for_asset(
            asset_id=s_id,
            lat=lat,
            lon=lon,
            start_date=start_date,
            end_date=end_date,
            raw_dir=raw_dir,
            use_cache=use_cache,
        )

        solar_mw = calculate_solar_mw(
            capacity_mw=capacity,
            shortwave_radiation=w_df["shortwave_radiation"],
            performance_ratio=pr,
            temperature_2m=w_df["temperature_2m"],
        )

        df_out[f"solar_{s_id}"] = np.round(solar_mw, 2)
        df_out[f"cloud_{s_id}"] = np.round(w_df["cloud_cover"], 2)

    # 2. Process Wind Farms (W1 - W3)
    wind_farms = assets_cfg["wind_farms"]
    for w in wind_farms:
        w_id = w["id"]
        lat, lon = w["lat"], w["lon"]
        capacity = w["capacity_mw"]
        cut_in = w.get("cut_in_speed_ms", 3.0)
        rated = w.get("rated_speed_ms", 12.0)
        cut_out = w.get("cut_out_speed_ms", 25.0)

        logger.info("Processing Wind %s (%s, %.1f MW)...", w_id, w["name"], capacity)
        w_df = fetch_weather_for_asset(
            asset_id=w_id,
            lat=lat,
            lon=lon,
            start_date=start_date,
            end_date=end_date,
            raw_dir=raw_dir,
            use_cache=use_cache,
        )

        wind_mw = calculate_wind_mw(
            capacity_mw=capacity,
            wind_speed=w_df["wind_speed_100m"],
            cut_in_speed_ms=cut_in,
            rated_speed_ms=rated,
            cut_out_speed_ms=cut_out,
        )

        df_out[f"wind_{w_id}"] = np.round(wind_mw, 2)
        df_out[f"wind_speed_{w_id}"] = np.round(w_df["wind_speed_100m"], 2)

    # 3. Market Prices
    logger.info("Loading / Generating electricity market prices...")
    price_series = load_or_generate_prices(
        start_date=start_date,
        end_date=end_date,
        iex_dir=iex_dir,
        seed=100 + ord(season_code),
    )
    df_out["price"] = price_series

    # 4. Consumer Demand Profiles (C1 - C4)
    logger.info("Generating industrial consumer demand profiles...")
    demand_df = generate_consumer_demands(
        target_index=target_index,
        seed=200 + ord(season_code),
    )
    for col in demand_df.columns:
        df_out[col] = demand_df[col]

    # Reorder columns exactly as expected in specification 5.5:
    # timestamp, solar_S1..S5, wind_W1..W3, price, demand_C1..C4, cloud_S1..S5, wind_speed_W1..W3
    ordered_cols = (
        [f"solar_{s['id']}" for s in solar_farms]
        + [f"wind_{w['id']}" for w in wind_farms]
        + ["price"]
        + [f"demand_{c['id']}" for c in assets_cfg["consumers"]]
        + [f"cloud_{s['id']}" for s in solar_farms]
        + [f"wind_speed_{w['id']}" for w in wind_farms]
    )

    df_out = df_out[ordered_cols].reset_index()

    out_csv = processed_dir / f"season_{season_code}.csv"
    df_out.to_csv(out_csv, index=False)
    logger.info("Successfully generated %s (rows: %d, cols: %d)", out_csv, len(df_out), len(df_out.columns))

    return out_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="GridMind Dataset Builder")
    parser.add_argument(
        "--season",
        type=str,
        default="A",
        choices=["A", "B", "ALL", "all"],
        help="Season code to build ('A', 'B', or 'ALL')",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force re-fetching from Open-Meteo ignoring cached raw files",
    )
    args = parser.parse_args()

    root_dir = get_project_root()
    seasons_to_build = ["A", "B"] if args.season.upper() == "ALL" else [args.season.upper()]

    for s in seasons_to_build:
        csv_path = build_season_dataset(s, root_dir, use_cache=not args.no_cache)
        print(f"Dataset generated at: {csv_path}")


if __name__ == "__main__":
    import numpy as np  # Ensure imported in script scope
    main()
