"""Physical conversion models for renewable energy generation.

Transforms raw meteorological inputs (solar irradiance, temperature, wind speed)
into electrical power output (MW) based on asset nameplate capacities and curves.
"""

from typing import Union
import numpy as np
import pandas as pd


def calculate_solar_mw(
    capacity_mw: float,
    shortwave_radiation: Union[float, np.ndarray, pd.Series],
    performance_ratio: float = 0.80,
    temperature_2m: Union[float, np.ndarray, pd.Series] = 25.0,
) -> Union[float, np.ndarray, pd.Series]:
    """Calculate solar farm output in MW from global shortwave irradiance (W/m²) and temperature (°C).

    Formula:
        Solar MW = capacity * (G / 1000) * PR * temp_derate
        temp_derate = 1 - 0.004 * max(0, temp - 25)
        clipped to [0, capacity]

    Args:
        capacity_mw: Nameplate DC/AC rating of the solar plant in MW.
        shortwave_radiation: Global horizontal irradiance in W/m².
        performance_ratio: System performance ratio (default 0.80 accounting for soiling, inverter loss, wiring).
        temperature_2m: Ambient air temperature at 2m height in °C.

    Returns:
        Generated electrical power in MW, bounded within [0, capacity_mw].
    """
    rad = np.asarray(shortwave_radiation, dtype=float)
    temp = np.asarray(temperature_2m, dtype=float)

    # Negative radiation is unphysical (e.g., nighttime sensor noise)
    rad_clean = np.maximum(0.0, rad)

    # Standard silicon temperature derating: -0.4% per °C above 25°C STC
    temp_derate = 1.0 - 0.004 * np.maximum(0.0, temp - 25.0)
    # Physical lower bound on derate factor to prevent negative values in extreme heat
    temp_derate = np.maximum(0.0, temp_derate)

    raw_mw = capacity_mw * (rad_clean / 1000.0) * performance_ratio * temp_derate
    clipped_mw = np.clip(raw_mw, 0.0, capacity_mw)

    if isinstance(shortwave_radiation, pd.Series):
        return pd.Series(clipped_mw, index=shortwave_radiation.index)
    if np.isscalar(shortwave_radiation):
        return float(clipped_mw.item())
    return clipped_mw


def calculate_wind_mw(
    capacity_mw: float,
    wind_speed: Union[float, np.ndarray, pd.Series],
    cut_in_speed_ms: float = 3.0,
    rated_speed_ms: float = 12.0,
    cut_out_speed_ms: float = 25.0,
) -> Union[float, np.ndarray, pd.Series]:
    """Calculate wind farm output in MW from hub-height wind speed (m/s).

    Standard cubic power curve:
        - 0 below cut-in (v < vin)
        - capacity * ((v³ - vin³) / (vr³ - vin³)) between cut-in and rated (vin <= v < vr)
        - capacity between rated and cut-out (vr <= v <= vout)
        - 0 above cut-out (v > vout) to protect turbines from mechanical damage

    Args:
        capacity_mw: Total nameplate capacity of the wind farm in MW.
        wind_speed: Wind speed at 100m hub height in m/s.
        cut_in_speed_ms: Cut-in wind speed threshold in m/s (default 3.0).
        rated_speed_ms: Wind speed where turbine reaches full rated capacity (default 12.0).
        cut_out_speed_ms: Storm cut-out speed threshold in m/s (default 25.0).

    Returns:
        Generated wind power in MW, bounded within [0, capacity_mw].
    """
    v = np.asarray(wind_speed, dtype=float)
    output = np.zeros_like(v, dtype=float)

    # Region II: between cut-in and rated
    mask_ramp = (v >= cut_in_speed_ms) & (v < rated_speed_ms)
    denom = (rated_speed_ms**3) - (cut_in_speed_ms**3)
    if denom > 0:
        ratio = (v[mask_ramp]**3 - cut_in_speed_ms**3) / denom
        output[mask_ramp] = capacity_mw * ratio

    # Region III: rated power up to cut-out
    mask_rated = (v >= rated_speed_ms) & (v <= cut_out_speed_ms)
    output[mask_rated] = capacity_mw

    # Region IV: above cut-out (0 MW) and Region I: below cut-in (0 MW) remain 0

    clipped_mw = np.clip(output, 0.0, capacity_mw)

    if isinstance(wind_speed, pd.Series):
        return pd.Series(clipped_mw, index=wind_speed.index)
    if np.isscalar(wind_speed):
        return float(clipped_mw.item())
    return clipped_mw
