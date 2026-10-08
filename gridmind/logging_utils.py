"""Structured JSONL decision audit logger for GridMind.

Every 15-minute simulation interval records a comprehensive audit entry:
- Environmental conditions and actuals
- Monitor report and detected anomaly signals
- Strategist decision, candidate plan risk comparisons, and chosen trade-offs
- Guardrail validation verdict
- Executed first-interval physical dispatch actions
- Cumulative and interval KPIs
"""

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

from gridmind.agents.schemas import Explanation, MonitorReport, StrategyDecision
from gridmind.guard.guardrails import ValidationResult
from gridmind.sim.state import DispatchAction, GridState


class DecisionLogger:
    """Manages appending interval-by-interval decision records to JSONL files."""

    def __init__(self, logs_dir: Optional[Path] = None, run_id: Optional[str] = None) -> None:
        self.logs_dir = logs_dir or Path("logs")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.log_path = self.logs_dir / f"{self.run_id}.jsonl"

    def log_interval(
        self,
        interval_index: int,
        timestamp: str,
        state: GridState,
        monitor_report: Optional[MonitorReport],
        strategy_decision: Optional[StrategyDecision],
        guardrail_result: Optional[ValidationResult],
        action: DispatchAction,
        explanation: Optional[Explanation],
        metrics_snapshot: Dict[str, Any],
        is_safe_mode: bool = False,
        strategy_refreshed: bool = True,
    ) -> Dict[str, Any]:
        """Record an interval entry to JSONL and return the serialized dictionary."""
        entry: Dict[str, Any] = {
            "run_id": self.run_id,
            "interval_index": interval_index,
            "timestamp": timestamp,
            "is_safe_mode": is_safe_mode,
            "strategy_refreshed": strategy_refreshed,
            "telemetry": {
                "solar_actual_mw": round(sum(state.solar_actual.values()), 2),
                "wind_actual_mw": round(sum(state.wind_actual.values()), 2),
                "demand_actual_mw": round(sum(state.demand_actual.values()), 2),
                "price_actual_inr_per_mwh": round(state.price_actual, 2),
                "battery_soc_mwh": {b: round(soc, 2) for b, soc in state.battery_soc.items()},
                "battery_soc_pct": {b: round(pct, 3) for b, pct in state.battery_soc_pct.items()},
                "import_limit_mw": state.grid_import_limit_mw,
                "export_limit_mw": state.grid_export_limit_mw,
                "active_events": [e.event_type for e in state.active_events],
            },
            "monitor": monitor_report.model_dump() if monitor_report else None,
            "strategy": strategy_decision.model_dump() if strategy_decision else None,
            "guardrail": {
                "passed": guardrail_result.passed if guardrail_result else True,
                "violations": guardrail_result.violations if guardrail_result else [],
                "warnings": guardrail_result.warnings if guardrail_result else [],
            }
            if guardrail_result
            else None,
            "dispatch": {
                "grid_import_mw": round(action.grid_import, 2),
                "grid_export_mw": round(action.grid_export, 2),
                "battery_charge_mw": {b: round(v, 2) for b, v in action.battery_charge.items()},
                "battery_discharge_mw": {b: round(v, 2) for b, v in action.battery_discharge.items()},
                "curtailment_mw": round(
                    sum(action.solar_curtailment.values()) + sum(action.wind_curtailment.values()), 2
                ),
                "demand_response_mw": round(sum(action.demand_response.values()), 2),
                "shortfall_mw": round(sum(action.contract_shortfall.values()), 2),
                "unserved_critical_mw": round(sum(action.unserved_critical.values()), 2),
            },
            "explanation": explanation.model_dump() if explanation else None,
            "metrics": metrics_snapshot,
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        return entry

    def read_all_entries(self) -> list[Dict[str, Any]]:
        """Read back all JSONL entries from disk."""
        if not self.log_path.exists():
            return []
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries
