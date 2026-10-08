"""Weather data extraction and processing from Open-Meteo Historical Archive API.

Features:
- Caching of raw JSON responses to avoid redundant network calls.
- High-fidelity 15-minute interpolation of hourly meteorological records.
- Deterministic synthetic weather generator fallback when network or API is unavailable.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_weather_for_asset(
    asset_id: str,
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    raw_dir: Path,
    use_cache: bool = True,
    seed: int = 42,
) -> pd.DataFrame:
    """Fetch hourly weather for a specific asset location, with caching and synthetic fallback.

    Args:
        asset_id: Farm identifier (e.g., 'S1', 'W1').
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        start_date: Start date string 'YYYY-MM-DD'.
        end_date: End date string 'YYYY-MM-DD'.
        raw_dir: Directory to cache raw JSON responses.
        use_cache: If True, reads from disk if cache file exists.
        seed: Random seed for synthetic fallback generation.

    Returns:
        DataFrame with 15-minute intervals indexed by timestamp with columns:
        - shortwave_radiation (W/m²)
        - wind_speed_100m (m/s)
        - cloud_cover (%)
        - temperature_2m (°C)
    """
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache_file = raw_dir / f"weather_{asset_id}_{start_date}_{end_date}.json"

    raw_data: Optional[Dict[str, Any]] = None

    if use_cache and cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            logger.info("Loaded cached weather for %s from %s", asset_id, cache_file)
        except Exception as e:
            logger.warning("Failed to read cache %s: %s. Fetching from API.", cache_file, e)

    if raw_data is None:
        try:
            # Request 1 extra day at the end to ensure smooth boundary interpolation to 23:45
            end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1)
            query_end = end_dt.strftime("%Y-%m-%d")

            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": start_date,
                "end_date": query_end,
                "hourly": "shortwave_radiation,wind_speed_100m,cloud_cover,temperature_2m",
                "wind_speed_unit": "ms",
                "timezone": "Asia/Kolkata",
            }
            logger.info("Requesting Open-Meteo archive for %s (%s to %s)...", asset_id, start_date, query_end)
            resp = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=12)
            resp.raise_for_status()
            raw_data = resp.json()

            # Cache the successful response
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(raw_data, f, indent=2)
            logger.info("Cached weather response to %s", cache_file)

        except Exception as e:
            logger.warning(
                "Open-Meteo API call failed for %s (%s). Falling back to synthetic weather generator.",
                asset_id,
                e,
            )
            raw_data = generate_synthetic_weather_raw(
                asset_id=asset_id,
                lat=lat,
                start_date=start_date,
                end_date=end_date,
                seed=seed,
            )
            # Cache synthetic data as well so runs remain fast and stable
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(raw_data, f, indent=2)

    return process_raw_weather_to_15min(raw_data, start_date, end_date)


def generate_synthetic_weather_raw(
    asset_id: str,
    lat: float,
    start_date: str,
    end_date: str,
    seed: int = 42,
) -> Dict[str, Any]:
    """Generate realistic synthetic hourly weather mimicking Karnataka meteorological conditions.

    - April (Summer): High solar (~950 W/m² peak), warm (24-38°C), moderate wind (4-7 m/s).
    - July (Monsoon): Dense cloud cover, intermittent solar, high gusty wind (8-16 m/s).
    """
    rng = np.random.default_rng(seed + sum(ord(c) for c in asset_id))

    # Extended date range to cover boundary interpolation
    end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1)
    hourly_dates = pd.date_range(start_date, end_dt.strftime("%Y-%m-%d 23:00:00"), freq="1h")
    n = len(hourly_dates)

    is_monsoon = any(d.month in [6, 7, 8, 9] for d in hourly_dates)

    hours = hourly_dates.hour.to_numpy()
    day_fraction = (hours - 6.0) / 12.0  # 0 at 06:00, 1 at 18:00

    # Solar: clear-sky half-sine curve between 06:00 and 18:00 IST
    sun_up = (hours >= 6) & (hours <= 18)
    base_solar = np.zeros(n, dtype=float)
    peak_solar = 750.0 if is_monsoon else 980.0
    base_solar[sun_up] = peak_solar * np.sin(np.pi * day_fraction[sun_up])

    # Cloud cover: Monsoon has heavy overcast, summer has mostly clear skies with afternoon puffs
    if is_monsoon:
        cloud_cover = rng.uniform(50.0, 95.0, size=n)
    else:
        cloud_cover = rng.uniform(5.0, 35.0, size=n)

    # Cloud attenuation factor on solar radiation
    cloud_attenuation = 1.0 - 0.75 * (cloud_cover / 100.0)
    solar_radiation = np.maximum(0.0, base_solar * cloud_attenuation)

    # Ambient Temperature (°C): diurnal cycle peaking at ~15:00 IST
    temp_peak_hour = 15.0
    temp_phase = 2.0 * np.pi * (hours - temp_peak_hour) / 24.0
    if is_monsoon:
        t_mean, t_amp = 26.0, 4.0
    else:
        t_mean, t_amp = 31.0, 7.0
    temperature = t_mean + t_amp * np.cos(temp_phase) + rng.normal(0, 0.8, size=n)

    # Wind speed (m/s): Weibull shape with afternoon thermal surge
    if is_monsoon:
        scale = 11.5
    else:
        scale = 6.2
    # Diurnal modulation (higher late afternoon/evening)
    wind_diurnal = 1.0 + 0.25 * np.sin(2.0 * np.pi * (hours - 12.0) / 24.0)
    wind_speed = rng.weibull(2.1, size=n) * scale * wind_diurnal
    wind_speed = np.clip(wind_speed, 0.5, 24.0)

    return {
        "hourly": {
            "time": [d.strftime("%Y-%m-%dT%H:00") for d in hourly_dates],
            "shortwave_radiation": solar_radiation.tolist(),
            "wind_speed_100m": wind_speed.tolist(),
            "cloud_cover": cloud_cover.tolist(),
            "temperature_2m": temperature.tolist(),
        }
    }


def process_raw_weather_to_15min(
    raw_data: Dict[str, Any],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Interpolate raw hourly weather into clean 15-minute timeseries."""
    hourly_dict = raw_data["hourly"]
    times = pd.to_datetime(hourly_dict["time"])

    df_hourly = pd.DataFrame(
        {
            "shortwave_radiation": hourly_dict["shortwave_radiation"],
            "wind_speed_100m": hourly_dict["wind_speed_100m"],
            "cloud_cover": hourly_dict["cloud_cover"],
            "temperature_2m": hourly_dict["temperature_2m"],
        },
        index=times,
    )

    # Ensure monotonic index without duplicates
    df_hourly = df_hourly[~df_hourly.index.duplicated(keep="first")].sort_index()

    # Target 15-min index spanning exactly start_date 00:00 to end_date 23:45
    target_start = pd.to_datetime(f"{start_date} 00:00:00")
    target_end = pd.to_datetime(f"{end_date} 23:45:00")
    target_index = pd.date_range(target_start, target_end, freq="15min")

    # Union index to preserve exact hourly sample points during interpolation
    full_index = df_hourly.index.union(target_index).sort_values()
    df_reindexed = df_hourly.reindex(full_index)

    # Linear interpolation across time
    df_interp = df_reindexed.interpolate(method="time")

    # Slicing precisely to target 15-minute grid
    df_15min = df_interp.loc[target_index].copy()

    # Physical bounds enforcement
    df_15min["shortwave_radiation"] = np.maximum(0.0, df_15min["shortwave_radiation"])
    df_15min["wind_speed_100m"] = np.maximum(0.0, df_15min["wind_speed_100m"])
    df_15min["cloud_cover"] = np.clip(df_15min["cloud_cover"], 0.0, 100.0)

    # Strict nighttime radiation zeroing (between 19:00 and 05:30 IST)
    hours = df_15min.index.hour + df_15min.index.minute / 60.0
    night_mask = (hours >= 19.0) | (hours < 5.5)
    df_15min.loc[night_mask, "shortwave_radiation"] = 0.0

    return df_15min
