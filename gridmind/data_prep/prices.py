"""Electricity market price loader and synthetic generator mimicking Indian Energy Exchange (IEX).

Supports:
- Automatic detection and loading of user-provided IEX Day-Ahead (DAM) or Real-Time Market (RTM) CSVs.
- High-fidelity synthetic price generation matching Indian power market dynamics:
  * Midday solar glut (₹2,500 - ₹3,500 / MWh)
  * Evening peak demand (₹7,000 - ₹10,000 / MWh)
  * Night / morning moderate baseline
  * Seeded stochastic price spikes and noise
"""

import logging
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def load_or_generate_prices(
    start_date: str,
    end_date: str,
    iex_dir: Optional[Path] = None,
    seed: int = 101,
) -> pd.Series:
    """Load market prices from an IEX CSV file or fall back to realistic synthetic generator.

    Args:
        start_date: 'YYYY-MM-DD'
        end_date: 'YYYY-MM-DD'
        iex_dir: Directory where user may deposit IEX CSV exports.
        seed: Random seed for synthetic price generator.

    Returns:
        Series of prices in ₹/MWh indexed by 15-minute timestamps.
    """
    target_start = pd.to_datetime(f"{start_date} 00:00:00")
    target_end = pd.to_datetime(f"{end_date} 23:45:00")
    target_index = pd.date_range(target_start, target_end, freq="15min")

    if iex_dir is not None:
        iex_path = Path(iex_dir)
        csv_files = list(iex_path.glob("*.csv"))
        # Only load genuine user CSV files (exclude sample templates)
        real_files = [
            f for f in csv_files
            if "sample" not in f.name.lower() and "template" not in f.name.lower()
        ]

        for csv_file in real_files:
            try:
                price_series = _parse_iex_csv(csv_file, target_index)
                if price_series is not None:
                    logger.info("Successfully loaded market prices from %s", csv_file)
                    return price_series
            except Exception as e:
                logger.warning("Could not parse IEX file %s: %s", csv_file, e)

    logger.info("Generating synthetic IEX market prices for %s to %s (seed=%d)", start_date, end_date, seed)
    return generate_synthetic_iex_prices(target_index, seed=seed)


def _parse_iex_csv(csv_path: Path, target_index: pd.DatetimeIndex) -> Optional[pd.Series]:
    """Parse user CSV with tolerant column name matching."""
    df = pd.read_csv(csv_path)

    # Normalize column names
    col_map = {c.strip().lower().replace(" ", "_"): c for c in df.columns}

    # Find timestamp column
    time_col = None
    for candidate in ["timestamp", "datetime", "date_time", "time", "date"]:
        if candidate in col_map:
            time_col = col_map[candidate]
            break

    # Find price column
    price_col = None
    for candidate in [
        "mcp",
        "market_clearing_price",
        "price",
        "price_inr_mwh",
        "rate",
        "price_rs_mwh",
    ]:
        if candidate in col_map:
            price_col = col_map[candidate]
            break

    if time_col is None or price_col is None:
        return None

    df["dt"] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=["dt", price_col])
    df = df.set_index("dt").sort_index()

    series = df[price_col].astype(float)
    # Remove duplicates
    series = series[~series.index.duplicated(keep="first")]

    # Reindex & interpolate to match target 15-min index
    aligned = series.reindex(target_index).interpolate(method="time").bfill().ffill()
    # Clip to regulatory cap [0, 10,000] ₹/MWh
    return aligned.clip(0.0, 10000.0)


def generate_synthetic_iex_prices(
    target_index: pd.DatetimeIndex,
    seed: int = 101,
) -> pd.Series:
    """Synthesize 15-minute Indian market prices (₹/MWh) capturing diurnal patterns and spikes.

    Shape characteristics:
    - 00:00 - 06:00: Night baseload (~₹3,500 - ₹4,500)
    - 06:00 - 09:30: Morning ramp (~₹4,500 - ₹6,000)
    - 10:00 - 15:30: Midday solar glut drop (~₹2,600 - ₹3,400)
    - 18:00 - 22:30: Evening non-solar demand peak (~₹7,500 - ₹9,800)
    - Stochastic short-lived price spikes (e.g., thermal trips, transmission constraints)
    """
    rng = np.random.default_rng(seed)
    n = len(target_index)

    hours = target_index.hour.to_numpy() + target_index.minute.to_numpy() / 60.0

    # Diurnal baseline components
    base_price = np.full(n, 4200.0)

    # Midday depression (solar duck curve depression)
    midday_mask = (hours >= 10.0) & (hours <= 16.0)
    midday_factor = np.sin(np.pi * (hours[midday_mask] - 10.0) / 6.0)
    base_price[midday_mask] -= 1500.0 * midday_factor

    # Evening peak (17:30 to 23:00)
    evening_mask = (hours >= 17.5) & (hours <= 23.0)
    evening_factor = np.sin(np.pi * (hours[evening_mask] - 17.5) / 5.5)
    base_price[evening_mask] += 4200.0 * evening_factor

    # Morning ramp (06:00 to 09:30)
    morning_mask = (hours >= 6.0) & (hours <= 9.5)
    morning_factor = np.sin(np.pi * (hours[morning_mask] - 6.0) / 3.5)
    base_price[morning_mask] += 900.0 * morning_factor

    # Autoregressive AR(1) noise for realistic market turbulence
    ar_noise = np.zeros(n)
    white_noise = rng.normal(0, 180.0, size=n)
    for i in range(1, n):
        ar_noise[i] = 0.85 * ar_noise[i - 1] + white_noise[i]

    price = base_price + ar_noise

    # Rare market price spikes (approx 1.5% probability per interval)
    spike_mask = rng.uniform(0, 1, size=n) < 0.015
    spike_magnitude = rng.uniform(2000.0, 4500.0, size=n)
    price[spike_mask] += spike_magnitude[spike_mask]

    # Enforce CERC regulatory price cap (₹10,000/MWh) and floor (₹0/MWh)
    price = np.clip(price, 0.0, 10000.0)

    return pd.Series(np.round(price, 2), index=target_index, name="price")
