"""Rolling horizon forecaster with lead-time uncertainty cones and Monte Carlo scenarios.

Features:
- P50 expected values incorporating announced events (unannounced events remain unseen)
- Expanding forecast uncertainty cones with lead time (σ_solar, σ_wind, σ_price, σ_demand)
- Monte Carlo scenario paths with correlated noise for risk evaluation (Section 7.3)
- P10 and P90 confidence quantile envelopes
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import yaml

from gridmind.sim.events import EventManager
from gridmind.sim.state import GridState


@dataclass
class ForecastScenario:
    """A single realized path across the forecast horizon."""
    scenario_id: int
    solar: Dict[str, np.ndarray]       # per solar farm (MW array of length H)
    wind: Dict[str, np.ndarray]        # per wind farm (MW array of length H)
    demand: Dict[str, np.ndarray]      # per consumer (MW array of length H)
    price: np.ndarray                  # price (₹/MWh array of length H)
    export_limit: np.ndarray           # transmission export limit (MW)
    import_limit: np.ndarray           # transmission import limit (MW)


@dataclass
class ForecastResult:
    """Comprehensive forecast object covering P10, P50, P90 and Monte Carlo sample paths."""
    horizon_intervals: int
    lead_hours: np.ndarray
    timestamps: List[str]

    # P50 Central Forecasts
    solar_p50: Dict[str, np.ndarray]
    wind_p50: Dict[str, np.ndarray]
    demand_p50: Dict[str, np.ndarray]
    price_p50: np.ndarray

    # Uncertainty Quantiles
    solar_p10: Dict[str, np.ndarray]
    solar_p90: Dict[str, np.ndarray]
    wind_p10: Dict[str, np.ndarray]
    wind_p90: Dict[str, np.ndarray]
    demand_p10: Dict[str, np.ndarray]
    demand_p90: Dict[str, np.ndarray]
    price_p10: np.ndarray
    price_p90: np.ndarray

    export_limit: np.ndarray
    import_limit: np.ndarray
    scenarios: List[ForecastScenario] = field(default_factory=list)


class Forecaster:
    """Produces rolling forecasts with uncertainty quantification for the MILP optimizer."""

    def __init__(
        self,
        dataset_path: Path,
        assets_config_path: Path,
        market_config_path: Path,
        horizon_intervals: int = 32,
    ) -> None:
        self.df = pd.read_csv(dataset_path)
        self.df["timestamp"] = pd.to_datetime(self.df["timestamp"])
        self.horizon_intervals = horizon_intervals

        with open(assets_config_path, "r", encoding="utf-8") as f:
            self.assets_cfg = yaml.safe_load(f)
        with open(market_config_path, "r", encoding="utf-8") as f:
            self.market_cfg = yaml.safe_load(f)

        self.solar_farms = [s["id"] for s in self.assets_cfg["solar_farms"]]
        self.wind_farms = [w["id"] for w in self.assets_cfg["wind_farms"]]
        self.consumers = [c["id"] for c in self.assets_cfg["consumers"]]
        self.default_import = float(self.assets_cfg.get("grid_limits", {}).get("max_import_mw", 150.0))
        self.default_export = float(self.assets_cfg.get("grid_limits", {}).get("max_export_mw", 200.0))

    def forecast(
        self,
        current_state: GridState,
        event_manager: Optional[EventManager] = None,
        num_scenarios: int = 30,
        seed: Optional[int] = None,
    ) -> ForecastResult:
        """Generate rolling P10/P50/P90 forecasts and N Monte Carlo scenarios.

        Args:
            current_state: Current snapshot of the grid.
            event_manager: Active event manager containing announced advance events.
            num_scenarios: Number of Monte Carlo scenario paths to sample.
            seed: Optional seed for scenario generation repeatability.

        Returns:
            ForecastResult populated with quantiles and sampled scenarios.
        """
        curr_idx = current_state.interval_index
        H = self.horizon_intervals
        total_rows = len(self.df)

        # Slice future horizon rows (pad with last row if near end of dataset)
        indices = [min(curr_idx + i, total_rows - 1) for i in range(H)]
        future_slice = self.df.iloc[indices].copy()
        timestamps = [str(ts) for ts in future_slice["timestamp"]]

        # Lead time in hours: interval 0 = 0.25h, interval 31 = 8.0h
        lead_hours = np.arange(1, H + 1) * 0.25

        # Base ground truth from dataset (copy to allow in-place modification by events)
        base_solar = {s: future_slice[f"solar_{s}"].to_numpy(dtype=float).copy() for s in self.solar_farms}
        base_wind = {w: future_slice[f"wind_{w}"].to_numpy(dtype=float).copy() for w in self.wind_farms}
        base_demand = {c: future_slice[f"demand_{c}"].to_numpy(dtype=float).copy() for c in self.consumers}
        base_price = future_slice["price"].to_numpy(dtype=float).copy()

        export_limit = np.full(H, self.default_export)
        import_limit = np.full(H, self.default_import)

        # Apply announced events known at curr_idx to future horizon
        if event_manager is not None:
            announced_events = event_manager.get_announced_events(curr_idx)
            for event in announced_events:
                # Determine overlap between event active window and future horizon [curr_idx, curr_idx + H)
                evt_start = event.start_interval
                evt_end = event.start_interval + event.duration_intervals
                
                for step, idx in enumerate(indices):
                    if evt_start <= idx < evt_end:
                        etype = event.event_type
                        mag = event.magnitude

                        if etype == "storm_alert":
                            for s in self.solar_farms:
                                base_solar[s][step] *= (1.0 - mag)
                            if event.extra_params.get("wind_cut_out", True):
                                for w in self.wind_farms:
                                    base_wind[w][step] = 0.0
                            if "export_limit_mw" in event.extra_params:
                                export_limit[step] = min(export_limit[step], float(event.extra_params["export_limit_mw"]))

                        elif etype == "cloud_cover":
                            targets = event.affected_assets or self.solar_farms
                            for s in targets:
                                if s in base_solar:
                                    base_solar[s][step] *= (1.0 - mag)

                        elif etype == "line_constraint":
                            export_limit[step] = min(export_limit[step], mag)

                        elif etype == "price_spike":
                            base_price[step] = min(10000.0, base_price[step] * mag)

                        elif etype == "demand_surge":
                            targets = event.affected_assets or self.consumers
                            for c in targets:
                                if c in base_demand:
                                    base_demand[c][step] *= (1.0 + mag)

        # Uncertainty standard deviations growing with lead time (Section 6.4)
        # Solar: σ = 5% + 2%/h; Wind: σ = 8% + 3%/h; Price: σ = 5% + 2%/h; Demand: σ = 2% + 0.5%/h
        sigma_solar_pct = 0.05 + 0.02 * lead_hours
        sigma_wind_pct = 0.08 + 0.03 * lead_hours
        sigma_price_pct = 0.05 + 0.02 * lead_hours
        sigma_demand_pct = 0.02 + 0.005 * lead_hours

        # Compute P10, P50, P90 quantiles (Normal approximation: z=1.28155 for 10th and 90th percentile)
        z = 1.28155

        # Solar P10/P50/P90
        solar_p50 = {s: np.maximum(0.0, base_solar[s]) for s in self.solar_farms}
        solar_p10 = {
            s: np.maximum(0.0, base_solar[s] * (1.0 - z * sigma_solar_pct))
            for s in self.solar_farms
        }
        solar_p90 = {
            s: np.maximum(0.0, base_solar[s] * (1.0 + z * sigma_solar_pct))
            for s in self.solar_farms
        }

        # Wind P10/P50/P90
        wind_p50 = {w: np.maximum(0.0, base_wind[w]) for w in self.wind_farms}
        wind_p10 = {
            w: np.maximum(0.0, base_wind[w] * (1.0 - z * sigma_wind_pct))
            for w in self.wind_farms
        }
        wind_p90 = {
            w: np.maximum(0.0, base_wind[w] * (1.0 + z * sigma_wind_pct))
            for w in self.wind_farms
        }

        # Demand P10/P50/P90
        demand_p50 = {c: np.maximum(0.0, base_demand[c]) for c in self.consumers}
        demand_p10 = {
            c: np.maximum(0.0, base_demand[c] * (1.0 - z * sigma_demand_pct))
            for c in self.consumers
        }
        demand_p90 = {
            c: np.maximum(0.0, base_demand[c] * (1.0 + z * sigma_demand_pct))
            for c in self.consumers
        }

        # Price P10/P50/P90
        price_p50 = np.clip(base_price, 0.0, 10000.0)
        price_p10 = np.clip(base_price * (1.0 - z * sigma_price_pct), 0.0, 10000.0)
        price_p90 = np.clip(base_price * (1.0 + z * sigma_price_pct), 0.0, 10000.0)

        # Generate N Monte Carlo Scenarios with temporally correlated noise
        scenarios: List[ForecastScenario] = []
        rng = np.random.default_rng(seed if seed is not None else (42 + curr_idx))

        for sc_idx in range(num_scenarios):
            # AR(1) autoregressive noise factor across horizon
            def generate_ar_path(sigma_vec: np.ndarray, corr: float = 0.75) -> np.ndarray:
                path = np.zeros(H)
                w = rng.normal(0, 1, size=H)
                val = w[0]
                path[0] = val
                for t in range(1, H):
                    val = corr * val + np.sqrt(1 - corr**2) * w[t]
                    path[t] = val
                return path * sigma_vec

            sc_solar = {
                s: np.maximum(0.0, base_solar[s] * (1.0 + generate_ar_path(sigma_solar_pct)))
                for s in self.solar_farms
            }
            sc_wind = {
                w: np.maximum(0.0, base_wind[w] * (1.0 + generate_ar_path(sigma_wind_pct)))
                for w in self.wind_farms
            }
            sc_demand = {
                c: np.maximum(0.0, base_demand[c] * (1.0 + generate_ar_path(sigma_demand_pct)))
                for c in self.consumers
            }
            sc_price = np.clip(
                base_price * (1.0 + generate_ar_path(sigma_price_pct)),
                0.0,
                10000.0,
            )

            scenarios.append(
                ForecastScenario(
                    scenario_id=sc_idx,
                    solar=sc_solar,
                    wind=sc_wind,
                    demand=sc_demand,
                    price=sc_price,
                    export_limit=export_limit.copy(),
                    import_limit=import_limit.copy(),
                )
            )

        return ForecastResult(
            horizon_intervals=H,
            lead_hours=lead_hours,
            timestamps=timestamps,
            solar_p50=solar_p50,
            wind_p50=wind_p50,
            demand_p50=demand_p50,
            price_p50=price_p50,
            solar_p10=solar_p10,
            solar_p90=solar_p90,
            wind_p10=wind_p10,
            wind_p90=wind_p90,
            demand_p10=demand_p10,
            demand_p90=demand_p90,
            price_p10=price_p10,
            price_p90=price_p90,
            export_limit=export_limit,
            import_limit=import_limit,
            scenarios=scenarios,
        )
