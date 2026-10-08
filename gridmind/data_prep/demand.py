"""Synthetic load profile generator for industrial RTC contracted consumers.

Generates realistic 15-minute load demand curves for:
- C1: Steel Plant (120 MW base, continuous arc furnace operation, small fluctuations)
- C2: Data Centre (60 MW base, mission-critical 24/7 flat server load, minor cooling variance)
- C3: Textile Mill (50 MW base, two shifts 06:00–22:00, low night maintenance load)
- C4: Cement Plant (70 MW base, continuous kilns with deliberate afternoon grinding mill dip)
"""

from typing import Dict
import numpy as np
import pandas as pd


def generate_consumer_demands(
    target_index: pd.DatetimeIndex,
    seed: int = 202,
) -> pd.DataFrame:
    """Generate 15-minute load profiles (MW) for all portfolio industrial consumers.

    Args:
        target_index: DatetimeIndex of 15-minute timestamps.
        seed: Random seed for reproducible noise generation.

    Returns:
        DataFrame with columns: demand_C1, demand_C2, demand_C3, demand_C4.
    """
    rng = np.random.default_rng(seed)
    n = len(target_index)
    hours = target_index.hour.to_numpy() + target_index.minute.to_numpy() / 60.0

    # C1: Steel plant (120 MW base, continuous operation, minor arc furnace turbulence)
    c1_base = 120.0
    c1_noise = rng.normal(0.0, 2.8, size=n)
    # Occasional scrap batch charging spikes/dips (+/- 4 MW)
    c1_batch = 1.5 * np.sin(2.0 * np.pi * hours / 3.0)
    demand_c1 = np.clip(c1_base + c1_batch + c1_noise, 95.0, 135.0)

    # C2: Data Centre (60 MW base, ultra-reliable flat IT load, tiny cooling fluctuation)
    c2_base = 60.0
    # Ambient temperature cooling effect: slightly higher chiller load in afternoon
    c2_cooling = 1.2 * np.maximum(0.0, np.sin(np.pi * (hours - 8.0) / 12.0))
    c2_noise = rng.normal(0.0, 0.45, size=n)
    demand_c2 = np.clip(c2_base + c2_cooling + c2_noise, 55.0, 65.0)

    # C3: Textile Mill (50 MW base, two shifts 06:00-22:00, reduced baseload at night)
    demand_c3 = np.zeros(n, dtype=float)
    active_shift_mask = (hours >= 6.0) & (hours < 22.0)
    # Night shift: only spinning baseload and lighting (~15 MW)
    demand_c3[~active_shift_mask] = 14.5 + rng.normal(0.0, 0.8, size=np.sum(~active_shift_mask))
    # Day/Evening shift: full looms & spindles active (~48-51 MW) with shift changeover dip at 14:00
    shift_profile = 50.0 + rng.normal(0.0, 1.2, size=np.sum(active_shift_mask))
    changeover_mask = (hours >= 13.75) & (hours <= 14.25)
    # Local shift handoff dip
    demand_c3[active_shift_mask] = shift_profile
    demand_c3[changeover_mask] = np.minimum(demand_c3[changeover_mask], 36.0)
    demand_c3 = np.clip(demand_c3, 10.0, 55.0)

    # C4: Cement Plant (70 MW base, continuous kilns, afternoon mill shutdown 12:00-16:00)
    demand_c4 = np.full(n, 70.0)
    # Afternoon dip (grinding ball mills throttled to avoid peak tariff / heat)
    afternoon_mask = (hours >= 12.0) & (hours <= 16.0)
    dip_intensity = 24.0 * np.sin(np.pi * (hours[afternoon_mask] - 12.0) / 4.0)
    demand_c4[afternoon_mask] -= dip_intensity
    c4_noise = rng.normal(0.0, 1.8, size=n)
    demand_c4 = np.clip(demand_c4 + c4_noise, 38.0, 78.0)

    df_demand = pd.DataFrame(
        {
            "demand_C1": np.round(demand_c1, 2),
            "demand_C2": np.round(demand_c2, 2),
            "demand_C3": np.round(demand_c3, 2),
            "demand_C4": np.round(demand_c4, 2),
        },
        index=target_index,
    )

    return df_demand
