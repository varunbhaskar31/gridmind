"""Unit tests for Phase 1 Data Pipeline.

Verifies:
- Solar conversion with temperature derating and night zeroing
- Wind power cubic curve, rated plateaus, and storm cut-out behavior
- Market price generation and CSV loading
- Industrial load profile generation
- Dataset completeness, column integrity, capacity clipping, and absence of NaNs
"""

import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from gridmind.data_prep.conversion import calculate_solar_mw, calculate_wind_mw
from gridmind.data_prep.demand import generate_consumer_demands
from gridmind.data_prep.prices import generate_synthetic_iex_prices, load_or_generate_prices
from gridmind.data_prep.weather import process_raw_weather_to_15min, generate_synthetic_weather_raw


class TestSolarConversion:
    def test_solar_zero_at_night(self):
        """Solar generation must be zero when solar radiation is zero or negative."""
        assert calculate_solar_mw(capacity_mw=100.0, shortwave_radiation=0.0) == 0.0
        assert calculate_solar_mw(capacity_mw=100.0, shortwave_radiation=-5.0) == 0.0

    def test_solar_standard_test_conditions(self):
        """At 1000 W/m², 25°C, PR 0.80, solar output should equal capacity * 0.80."""
        output = calculate_solar_mw(
            capacity_mw=150.0,
            shortwave_radiation=1000.0,
            performance_ratio=0.80,
            temperature_2m=25.0,
        )
        assert pytest.approx(output, rel=1e-4) == 120.0

    def test_solar_temperature_derating(self):
        """At 35°C (+10°C over 25°C), output should derate by 4%."""
        # temp_derate = 1 - 0.004 * 10 = 0.96
        # Expected: 100 * 1.0 * 0.80 * 0.96 = 76.8 MW
        output = calculate_solar_mw(
            capacity_mw=100.0,
            shortwave_radiation=1000.0,
            performance_ratio=0.80,
            temperature_2m=35.0,
        )
        assert pytest.approx(output, rel=1e-4) == 76.8

    def test_solar_cold_temperature_no_overrating(self):
        """Below 25°C, temperature derate does not inflate beyond STC."""
        output = calculate_solar_mw(
            capacity_mw=100.0,
            shortwave_radiation=1000.0,
            performance_ratio=0.80,
            temperature_2m=15.0,
        )
        assert pytest.approx(output, rel=1e-4) == 80.0

    def test_solar_clipped_to_nameplate_capacity(self):
        """Extreme irradiance must not exceed plant nameplate rating."""
        output = calculate_solar_mw(
            capacity_mw=100.0,
            shortwave_radiation=1800.0,
            performance_ratio=0.90,
            temperature_2m=25.0,
        )
        assert output <= 100.0


class TestWindConversion:
    def test_wind_below_cut_in(self):
        """Turbine does not rotate below cut-in speed (3 m/s)."""
        assert calculate_wind_mw(capacity_mw=80.0, wind_speed=0.0) == 0.0
        assert calculate_wind_mw(capacity_mw=80.0, wind_speed=2.5) == 0.0
        assert calculate_wind_mw(capacity_mw=80.0, wind_speed=3.0) == 0.0

    def test_wind_cubic_power_curve(self):
        """Between cut-in (3 m/s) and rated (12 m/s), power follows cubic progression."""
        # vin=3, vr=12 -> denom = 12^3 - 3^3 = 1728 - 27 = 1701
        # at v=8 m/s -> (512 - 27) / 1701 = 485 / 1701 = 0.285126...
        cap = 100.0
        v = 8.0
        expected = cap * ((v**3 - 3.0**3) / (12.0**3 - 3.0**3))
        actual = calculate_wind_mw(capacity_mw=cap, wind_speed=v)
        assert pytest.approx(actual, rel=1e-4) == expected
        assert 0.0 < actual < cap

    def test_wind_at_rated_and_plateau(self):
        """At and above rated speed (12 m/s) up to cut-out (25 m/s), turbine produces nameplate capacity."""
        assert calculate_wind_mw(capacity_mw=100.0, wind_speed=12.0) == 100.0
        assert calculate_wind_mw(capacity_mw=100.0, wind_speed=18.5) == 100.0
        assert calculate_wind_mw(capacity_mw=100.0, wind_speed=25.0) == 100.0

    def test_wind_above_cut_out_storm_protection(self):
        """Above cut-out speed (25 m/s), turbine feathers blades and shuts down (0 MW)."""
        assert calculate_wind_mw(capacity_mw=100.0, wind_speed=25.1) == 0.0
        assert calculate_wind_mw(capacity_mw=100.0, wind_speed=32.0) == 0.0


class TestPricesAndDemand:
    def test_synthetic_prices_bounds_and_shape(self):
        index = pd.date_range("2025-04-14 00:00:00", "2025-04-14 23:45:00", freq="15min")
        prices = generate_synthetic_iex_prices(index, seed=42)

        assert len(prices) == 96
        assert (prices >= 0.0).all()
        assert (prices <= 10000.0).all()
        # Midday prices (12:00) should be lower than evening peak (20:00)
        p_midday = prices.loc["2025-04-14 12:00:00"]
        p_evening = prices.loc["2025-04-14 20:00:00"]
        assert p_evening > p_midday

    def test_consumer_demands_profiles(self):
        index = pd.date_range("2025-04-14 00:00:00", "2025-04-14 23:45:00", freq="15min")
        df_dem = generate_consumer_demands(index, seed=42)

        assert len(df_dem) == 96
        assert set(df_dem.columns) == {"demand_C1", "demand_C2", "demand_C3", "demand_C4"}
        # Steel plant C1 ~120 MW
        assert 100.0 <= df_dem["demand_C1"].mean() <= 130.0
        # Data center C2 very flat ~60 MW
        assert df_dem["demand_C2"].std() < 1.0
        # Textile C3 night load must be lower than daytime shift load
        night_load = df_dem.loc["2025-04-14 02:00:00", "demand_C3"]
        day_load = df_dem.loc["2025-04-14 11:00:00", "demand_C3"]
        assert day_load > night_load * 2.0


class TestWeatherInterpolation:
    def test_weather_interpolation_shape_and_bounds(self):
        raw = generate_synthetic_weather_raw("S1", 14.10, "2025-04-14", "2025-04-15", seed=42)
        df_15 = process_raw_weather_to_15min(raw, "2025-04-14", "2025-04-15")

        # 2 days = 192 intervals
        assert len(df_15) == 192
        assert not df_15.isna().any().any()
        assert (df_15["shortwave_radiation"] >= 0.0).all()
        assert (df_15["wind_speed_100m"] >= 0.0).all()
        assert (df_15["cloud_cover"] >= 0.0).all() and (df_15["cloud_cover"] <= 100.0).all()


class TestProcessedDatasets:
    @pytest.mark.parametrize("season", ["season_A.csv", "season_B.csv"])
    def test_dataset_file_structure_and_constraints(self, season):
        csv_path = Path(__file__).resolve().parent.parent / "data" / "processed" / season
        assert csv_path.exists(), f"Processed dataset {season} does not exist"

        df = pd.read_csv(csv_path)
        assert len(df) == 672  # 7 days * 96 intervals/day
        assert not df.isna().any().any(), "Dataset contains NaN or null values"

        # Check required columns
        expected_cols = [
            "timestamp",
            "solar_S1", "solar_S2", "solar_S3", "solar_S4", "solar_S5",
            "wind_W1", "wind_W2", "wind_W3",
            "price",
            "demand_C1", "demand_C2", "demand_C3", "demand_C4",
            "cloud_S1", "cloud_S2", "cloud_S3", "cloud_S4", "cloud_S5",
            "wind_speed_W1", "wind_speed_W2", "wind_speed_W3",
        ]
        assert list(df.columns) == expected_cols

        # Plant capacities
        capacities = {
            "solar_S1": 150.0, "solar_S2": 120.0, "solar_S3": 100.0, "solar_S4": 80.0, "solar_S5": 50.0,
            "wind_W1": 100.0, "wind_W2": 80.0, "wind_W3": 60.0,
        }
        for col, cap in capacities.items():
            assert (df[col] >= 0.0).all(), f"{col} has negative values"
            assert (df[col] <= cap + 1e-4).all(), f"{col} exceeds nameplate rating {cap} MW"

        # Solar output at midnight (00:00 - 04:00) must be exactly 0
        df["dt"] = pd.to_datetime(df["timestamp"])
        night_hours = df["dt"].dt.hour.isin([0, 1, 2, 3, 22, 23])
        for s_col in ["solar_S1", "solar_S2", "solar_S3", "solar_S4", "solar_S5"]:
            assert (df.loc[night_hours, s_col] == 0.0).all(), f"{s_col} is non-zero at night"

