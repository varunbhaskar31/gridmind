"""Event injector and simulation disturbance engine for GridMind.

Supports deterministic preset scenarios, runtime manual event injection,
and Poisson-distributed random perturbation for multi-day reliability validation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import yaml
from pathlib import Path

from gridmind.sim.state import ActiveEvent


@dataclass
class Event:
    """Specification of a grid disturbance, meteorological shift, or asset failure."""
    event_type: str
    start_interval: int
    duration_intervals: int
    magnitude: float = 1.0
    affected_assets: List[str] = field(default_factory=list)
    announced_at: int = 0
    description: str = ""
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def is_announced(self, current_interval: int) -> bool:
        """Check whether this event is known to forecasters at the given interval."""
        return current_interval >= self.announced_at

    def is_active(self, current_interval: int) -> bool:
        """Check whether this event is currently affecting physical reality."""
        return self.start_interval <= current_interval < (self.start_interval + self.duration_intervals)

    def remaining_intervals(self, current_interval: int) -> int:
        """Return intervals remaining in this event's active duration."""
        if not self.is_active(current_interval):
            return 0
        return (self.start_interval + self.duration_intervals) - current_interval

    def to_active_model(self, current_interval: int) -> ActiveEvent:
        return ActiveEvent(
            event_type=self.event_type,
            description=self.description or f"{self.event_type} on {self.affected_assets}",
            start_interval=self.start_interval,
            duration_intervals=self.duration_intervals,
            remaining_intervals=self.remaining_intervals(current_interval),
            affected_assets=self.affected_assets,
            magnitude=self.magnitude,
            announced_at=self.announced_at,
        )


class EventManager:
    """Manages scheduling, activation, and physical modification of grid events."""

    def __init__(self) -> None:
        self.events: List[Event] = []

    def clear(self) -> None:
        self.events.clear()

    def add_event(self, event: Event) -> None:
        self.events.append(event)

    def load_from_scenario_dict(self, scenario_dict: Dict[str, Any]) -> None:
        """Parse events from a dictionary matching scenarios.yaml format."""
        raw_events = scenario_dict.get("events", [])
        for e in raw_events:
            event_type = e["type"]
            start_interval = e.get("interval", 0)
            duration = e.get("duration_intervals", 4)
            lead = e.get("announced_lead_intervals", 0)
            announced_at = max(0, start_interval - lead)

            # Special parameters per event type
            magnitude = float(e.get("magnitude", e.get("multiplier", 1.0)))
            assets = e.get("affected_assets", [])
            extra: Dict[str, Any] = {}

            if event_type == "storm_alert":
                target_interval = e.get("target_interval", start_interval)
                announced_at = start_interval
                start_interval = target_interval
                magnitude = float(e.get("affected_solar_reduction", 0.80))
                extra["wind_cut_out"] = e.get("wind_cut_out", True)
                extra["export_limit_mw"] = float(e.get("export_limit_mw", 80.0))

            elif event_type == "line_constraint":
                magnitude = float(e.get("export_limit_mw", 120.0))

            desc = f"{event_type.replace('_', ' ').title()}"
            if assets:
                desc += f" on {', '.join(assets)}"

            event = Event(
                event_type=event_type,
                start_interval=start_interval,
                duration_intervals=duration,
                magnitude=magnitude,
                affected_assets=assets,
                announced_at=announced_at,
                description=desc,
                extra_params=extra,
            )
            self.add_event(event)

    def get_active_events(self, current_interval: int) -> List[ActiveEvent]:
        """Return list of ActiveEvent models affecting physical reality at current interval."""
        return [
            e.to_active_model(current_interval)
            for e in self.events
            if e.is_active(current_interval)
        ]

    def get_announced_events(self, current_interval: int) -> List[Event]:
        """Return list of events announced to the portfolio at or before current interval."""
        return [e for e in self.events if e.is_announced(current_interval)]

    def apply_events_to_actuals(
        self,
        current_interval: int,
        solar_raw: Dict[str, float],
        wind_raw: Dict[str, float],
        demand_raw: Dict[str, float],
        price_raw: float,
        import_limit_default: float = 150.0,
        export_limit_default: float = 200.0,
    ) -> Dict[str, Any]:
        """Modify baseline timeseries inputs based on all currently active events.

        Returns modified copies of solar, wind, demand, price, battery availabilities, and line limits.
        """
        solar = dict(solar_raw)
        wind = dict(wind_raw)
        demand = dict(demand_raw)
        price = float(price_raw)
        battery_avail: Dict[str, bool] = {}
        solar_avail: Dict[str, bool] = {s: True for s in solar}
        wind_avail: Dict[str, bool] = {w: True for w in wind}
        import_limit = import_limit_default
        export_limit = export_limit_default

        for event in self.events:
            if not event.is_active(current_interval):
                continue

            etype = event.event_type
            mag = event.magnitude

            if etype == "cloud_cover":
                targets = event.affected_assets or list(solar.keys())
                for sid in targets:
                    if sid in solar:
                        solar[sid] = max(0.0, solar[sid] * (1.0 - mag))

            elif etype == "wind_surge":
                targets = event.affected_assets or list(wind.keys())
                for wid in targets:
                    if wid in wind:
                        wind[wid] = wind[wid] * (1.0 + mag)

            elif etype == "wind_drop":
                targets = event.affected_assets or list(wind.keys())
                for wid in targets:
                    if wid in wind:
                        wind[wid] = max(0.0, wind[wid] * (1.0 - mag))

            elif etype == "battery_outage":
                for bid in event.affected_assets:
                    battery_avail[bid] = False

            elif etype == "price_spike":
                price = min(10000.0, price * mag)

            elif etype == "storm_alert":
                # During storm impact: major solar attenuation, wind cut-out, transmission line de-rating
                for sid in solar:
                    solar[sid] = max(0.0, solar[sid] * (1.0 - mag))
                if event.extra_params.get("wind_cut_out", True):
                    for wid in wind:
                        wind[wid] = 0.0  # turbines shut down for storm survival
                        wind_avail[wid] = False
                if "export_limit_mw" in event.extra_params:
                    export_limit = min(export_limit, float(event.extra_params["export_limit_mw"]))

            elif etype == "line_constraint":
                export_limit = min(export_limit, mag)

            elif etype == "demand_surge":
                targets = event.affected_assets or list(demand.keys())
                for cid in targets:
                    if cid in demand:
                        demand[cid] = demand[cid] * (1.0 + mag)

            elif etype == "forecast_update":
                # Only alters forecaster expectations, leaves actuals intact
                pass

        return {
            "solar": solar,
            "wind": wind,
            "demand": demand,
            "price": price,
            "battery_avail": battery_avail,
            "solar_avail": solar_avail,
            "wind_avail": wind_avail,
            "import_limit": import_limit,
            "export_limit": export_limit,
        }

    def generate_poisson_events(
        self,
        total_intervals: int,
        rate_per_day: float = 2.0,
        seed: int = 42,
    ) -> None:
        """Inject randomized events following a Poisson process for multi-day reliability testing."""
        rng = np.random.default_rng(seed)
        intervals_per_day = 96
        num_days = int(np.ceil(total_intervals / intervals_per_day))

        event_catalog = [
            ("cloud_cover", ["S1", "S2"], 0.50, 6, 0),
            ("wind_drop", ["W1", "W2"], 0.40, 8, 0),
            ("battery_outage", ["B2"], 1.0, 12, 0),
            ("price_spike", [], 1.8, 4, 2),
            ("line_constraint", [], 110.0, 8, 4),
            ("demand_surge", ["C1"], 0.20, 6, 0),
        ]

        for d in range(num_days):
            day_offset = d * intervals_per_day
            n_events = rng.poisson(rate_per_day)
            for _ in range(n_events):
                start_slot = day_offset + rng.integers(12, intervals_per_day - 12)
                if start_slot >= total_intervals:
                    continue
                etype, assets, mag, dur, lead = event_catalog[rng.integers(len(event_catalog))]
                announced = max(0, start_slot - lead)
                self.add_event(
                    Event(
                        event_type=etype,
                        start_interval=start_slot,
                        duration_intervals=dur,
                        magnitude=mag,
                        affected_assets=list(assets),
                        announced_at=announced,
                        description=f"Random {etype}",
                    )
                )
