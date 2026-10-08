"""Monitor Agent: 15-minute operational anomaly detection and situation reporting.

Performs:
1. Deterministic telemetry signal extraction and delta calculation (actuals vs forecast vs previous).
2. Multi-factor severity scoring (low / medium / high / critical) per agent.yaml thresholds.
3. LLM situational synthesis when severity >= medium (bypassed on low severity to conserve tokens).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from gridmind.agents.llm_client import LLMClient
from gridmind.agents.mock_logic import mock_monitor_report
from gridmind.agents.prompts import MONITOR_SYSTEM_PROMPT
from gridmind.agents.schemas import MonitorReport, Signal
from gridmind.forecast.forecaster import ForecastResult
from gridmind.sim.state import GridState


class MonitorAgent:
    """Monitors 15-minute grid telemetry, scores operational severity, and generates reports."""

    def __init__(
        self,
        agent_config_path: Path,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        with open(agent_config_path, "r", encoding="utf-8") as f:
            self.agent_cfg = yaml.safe_load(f)

        self.thresholds = self.agent_cfg.get("thresholds", {})
        self.dev_med = float(self.thresholds.get("renewable_deviation_medium", 0.15))
        self.dev_high = float(self.thresholds.get("renewable_deviation_high", 0.35))
        self.spike_ratio = float(self.thresholds.get("price_spike_ratio", 1.5))
        self.low_soc_thresh = float(self.thresholds.get("low_battery_soc", 0.25))
        self.storm_horizon_h = float(self.thresholds.get("storm_alert_horizon_hours", 6.0))

        self.llm_client = llm_client or LLMClient()

    def run(
        self,
        current_state: GridState,
        forecast: ForecastResult,
        previous_state: Optional[GridState] = None,
    ) -> MonitorReport:
        """Analyze current telemetry, extract signals, score severity, and synthesize report."""
        signals: List[Signal] = []

        # 1. Renewable Deviations: Actual generation vs. Step 0 Forecast
        tot_actual_solar = sum(current_state.solar_actual.values())
        tot_fcst_solar = sum(forecast.solar_p50[s][0] for s in forecast.solar_p50)
        if tot_fcst_solar > 5.0:
            solar_delta = (tot_actual_solar - tot_fcst_solar) / tot_fcst_solar
            if abs(solar_delta) >= self.dev_med:
                signals.append(
                    Signal(
                        category="generation",
                        metric="solar_output",
                        current_value=round(tot_actual_solar, 1),
                        reference_value=round(tot_fcst_solar, 1),
                        delta_pct=round(solar_delta * 100.0, 1),
                        description=f"Solar output deviating by {solar_delta*100.0:+.1f}% from forecast",
                    )
                )

        tot_actual_wind = sum(current_state.wind_actual.values())
        tot_fcst_wind = sum(forecast.wind_p50[w][0] for w in forecast.wind_p50)
        if tot_fcst_wind > 5.0:
            wind_delta = (tot_actual_wind - tot_fcst_wind) / tot_fcst_wind
            if abs(wind_delta) >= self.dev_med:
                signals.append(
                    Signal(
                        category="generation",
                        metric="wind_output",
                        current_value=round(tot_actual_wind, 1),
                        reference_value=round(tot_fcst_wind, 1),
                        delta_pct=round(wind_delta * 100.0, 1),
                        description=f"Wind generation deviating by {wind_delta*100.0:+.1f}% from forecast",
                    )
                )

        # 2. Asset Availabilities (Outages)
        for b_id, is_avail in current_state.battery_available.items():
            if not is_avail:
                signals.append(
                    Signal(
                        category="storage",
                        asset_id=b_id,
                        metric="availability",
                        current_value=0.0,
                        reference_value=1.0,
                        delta_pct=-100.0,
                        description=f"Battery {b_id} hardware offline/unavailable",
                    )
                )

        for w_id, is_avail in current_state.wind_available.items():
            if not is_avail:
                signals.append(
                    Signal(
                        category="generation",
                        asset_id=w_id,
                        metric="availability",
                        current_value=0.0,
                        reference_value=1.0,
                        delta_pct=-100.0,
                        description=f"Wind farm {w_id} tripped or shut down for storm survival",
                    )
                )

        # 3. Market Price Anomaly
        price_ref = float(forecast.price_p50[0])
        if price_ref > 0:
            price_delta = (current_state.price_actual - price_ref) / price_ref
            if price_delta >= (self.spike_ratio - 1.0):
                signals.append(
                    Signal(
                        category="price",
                        metric="exchange_price",
                        current_value=round(current_state.price_actual, 2),
                        reference_value=round(price_ref, 2),
                        delta_pct=round(price_delta * 100.0, 1),
                        description=f"Market price spike: ₹{current_state.price_actual:.0f}/MWh ({price_delta*100.0:+.1f}%)",
                    )
                )

        # 4. Transmission Limits
        if current_state.grid_export_limit_mw < 150.0:
            signals.append(
                Signal(
                    category="grid",
                    metric="export_limit",
                    current_value=round(current_state.grid_export_limit_mw, 1),
                    reference_value=200.0,
                    delta_pct=round((current_state.grid_export_limit_mw - 200.0) / 200.0 * 100.0, 1),
                    description=f"Export transmission capacity de-rated to {current_state.grid_export_limit_mw:.1f} MW",
                )
            )

        # 5. Low Battery SoC
        for b_id, soc_frac in current_state.battery_soc_pct.items():
            if soc_frac < self.low_soc_thresh:
                signals.append(
                    Signal(
                        category="storage",
                        asset_id=b_id,
                        metric="state_of_charge",
                        current_value=round(soc_frac * 100.0, 1),
                        reference_value=round(self.low_soc_thresh * 100.0, 1),
                        delta_pct=round((soc_frac - self.low_soc_thresh) / self.low_soc_thresh * 100.0, 1),
                        description=f"Battery {b_id} SoC low at {soc_frac*100.0:.1f}%",
                    )
                )

        # 6. Active and Announced Events
        for event in current_state.active_events:
            signals.append(
                Signal(
                    category="event",
                    metric=event.event_type,
                    current_value=event.magnitude,
                    reference_value=1.0,
                    delta_pct=0.0,
                    description=f"Active disturbance: {event.description} ({event.remaining_intervals} intervals left)",
                )
            )

        # Severity Assessment
        has_battery_outage = any(s.category == "storage" and s.metric == "availability" for s in signals)
        has_storm = any(s.category == "event" and "storm" in s.metric for s in signals)
        has_extreme_re_drop = any(s.category == "generation" and s.delta_pct <= -35.0 for s in signals)
        has_moderate_re_drop = any(s.category == "generation" and s.delta_pct <= -15.0 for s in signals)
        has_line_cut = any(s.category == "grid" for s in signals)

        if has_storm or (has_battery_outage and has_extreme_re_drop):
            severity = "critical" if has_extreme_re_drop else "high"
        elif has_battery_outage or has_extreme_re_drop or has_line_cut:
            severity = "high"
        elif has_moderate_re_drop or signals:
            severity = "medium"
        else:
            severity = "low"

        replan_required = severity in ["medium", "high", "critical"]

        # Token conservation discipline: low severity uses deterministic summary without LLM
        if severity == "low" or self.llm_client.is_mock:
            return mock_monitor_report(
                signals=signals,
                severity=severity,
                replan_required=replan_required,
                active_events=current_state.active_events,
            )

        # Invoke LLM for situation summary when severity >= medium
        prompt = (
            f"Current Interval: {current_state.interval_index} ({current_state.timestamp})\n"
            f"Assessed Severity: {severity}\n"
            f"Detected Signals:\n"
            + "\n".join(f"- [{s.category.upper()}] {s.description}" for s in signals)
            + f"\nActive Events: {[e.event_type for e in current_state.active_events]}\n\n"
            f"Please synthesize the situation briefing for the shift dispatch manager."
        )

        report, _ = self.llm_client.generate_structured(
            prompt=prompt,
            schema=MonitorReport,
            system_instruction=MONITOR_SYSTEM_PROMPT,
            fallback_fn=mock_monitor_report,
            fallback_kwargs={
                "signals": signals,
                "severity": severity,
                "replan_required": replan_required,
                "active_events": current_state.active_events,
            },
        )
        return report
