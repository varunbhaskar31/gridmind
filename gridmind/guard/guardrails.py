"""Hard-constraint safety validation guardrail layer for GridMind.

Principles:
- Hard safety rules are deterministic code, not AI.
- Validates the first-interval action before execution in the real or simulated environment.
- Rejects plans with violations (SoC violation, simultaneous charge/discharge, simultaneous buy/sell,
  unserved critical load, line limit exceedance, energy balance error, storm reserve infringement).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from gridmind.optimize.milp import DispatchPlan
from gridmind.sim.state import DispatchAction, GridState


@dataclass
class ValidationResult:
    """Outcome of hard safety guardrail verification."""
    passed: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    severity: str = "ok"  # "ok", "warning", "rejected"


class GuardrailValidator:
    """Pre-execution safety gatekeeper ensuring zero hard-constraint violations."""

    def __init__(
        self,
        assets_config_path: Path,
        market_config_path: Path,
    ) -> None:
        with open(assets_config_path, "r", encoding="utf-8") as f:
            self.assets_cfg = yaml.safe_load(f)
        with open(market_config_path, "r", encoding="utf-8") as f:
            self.market_cfg = yaml.safe_load(f)

        self.solar_farms = {s["id"]: s for s in self.assets_cfg["solar_farms"]}
        self.wind_farms = {w["id"]: w for w in self.assets_cfg["wind_farms"]}
        self.batteries = {b["id"]: b for b in self.assets_cfg["batteries"]}
        self.consumers = {c["id"]: c for c in self.assets_cfg["consumers"]}

    def validate(
        self,
        plan: DispatchPlan,
        current_state: GridState,
        storm_reserve_floor: float = 0.40,
    ) -> ValidationResult:
        """Validate candidate plan first-interval action against hard physical constraints.

        Args:
            plan: The candidate DispatchPlan proposed by the optimizer.
            current_state: Current physical state of the portfolio.
            storm_reserve_floor: Mandatory minimum battery SoC floor during active storm alerts.

        Returns:
            ValidationResult with passed boolean and descriptive failure violations.
        """
        violations: List[str] = []
        warnings: List[str] = []

        if not plan.is_feasible:
            violations.append(f"Optimizer status is not optimal: {plan.status}")
            return ValidationResult(passed=False, violations=violations, severity="rejected")

        act: DispatchAction = plan.first_interval
        dt = 0.25

        # 1. Grid Import / Export Mutex & Bounds
        if act.grid_import > 1e-3 and act.grid_export > 1e-3:
            violations.append(
                f"Simultaneous buy and sell commanded: buy={act.grid_import} MW, sell={act.grid_export} MW"
            )

        if act.grid_import > current_state.grid_import_limit_mw + 1e-3:
            violations.append(
                f"Import limit exceeded: commanded {act.grid_import} MW > limit {current_state.grid_import_limit_mw} MW"
            )

        if act.grid_export > current_state.grid_export_limit_mw + 1e-3:
            violations.append(
                f"Export limit exceeded: commanded {act.grid_export} MW > limit {current_state.grid_export_limit_mw} MW"
            )

        # 2. Battery Storage Constraints
        storm_active = any(
            e.event_type == "storm_alert" for e in current_state.active_events
        )

        for b_id, b_spec in self.batteries.items():
            ch = act.battery_charge.get(b_id, 0.0)
            dis = act.battery_discharge.get(b_id, 0.0)
            is_avail = current_state.battery_available.get(b_id, True)

            # Mutex check: no simultaneous charge & discharge
            if ch > 1e-3 and dis > 1e-3:
                violations.append(f"Battery {b_id} simultaneous charge ({ch} MW) and discharge ({dis} MW)")

            # Availability check: unavailable battery cannot be commanded
            if not is_avail and (ch > 1e-3 or dis > 1e-3):
                violations.append(f"Battery {b_id} commanded while unavailable (ch={ch}, dis={dis})")

            # Power rating checks
            p_max = float(b_spec["power_mw"])
            if ch > p_max + 1e-3:
                violations.append(f"Battery {b_id} charge {ch} MW exceeds max power {p_max} MW")
            if dis > p_max + 1e-3:
                violations.append(f"Battery {b_id} discharge {dis} MW exceeds max power {p_max} MW")

            # State of Charge bounds projection
            eta_c = float(b_spec.get("eta_charge", 0.95))
            eta_d = float(b_spec.get("eta_discharge", 0.95))
            cap = float(b_spec["energy_mwh"])
            min_soc = cap * float(b_spec.get("soc_min", 0.10))
            max_soc = cap * float(b_spec.get("soc_max", 0.95))

            current_soc = current_state.battery_soc[b_id]
            projected_soc = current_soc + (ch * eta_c - dis / eta_d) * dt

            if projected_soc < min_soc - 1e-3:
                violations.append(
                    f"Battery {b_id} projected SoC {projected_soc:.2f} MWh violates minimum {min_soc:.2f} MWh"
                )
            if projected_soc > max_soc + 1e-3:
                violations.append(
                    f"Battery {b_id} projected SoC {projected_soc:.2f} MWh violates maximum {max_soc:.2f} MWh"
                )

            # Storm alert reserve floor check
            if storm_active:
                storm_floor_mwh = cap * storm_reserve_floor
                if projected_soc < storm_floor_mwh - 1e-3:
                    # Permitted if needed to serve critical load without shedding (Section 7.2)
                    total_crit = sum(
                        current_state.demand_actual[c] * float(self.consumers[c].get("critical_fraction", 0.5))
                        for c in self.consumers
                    )
                    gen_avail = (
                        sum(current_state.solar_actual.values())
                        + sum(current_state.wind_actual.values())
                        + current_state.grid_import_limit_mw
                    )
                    if gen_avail < total_crit:
                        warnings.append(
                            f"Battery {b_id} projected SoC {projected_soc:.2f} MWh discharged below storm floor to prevent critical load shedding."
                        )
                    else:
                        violations.append(
                            f"Battery {b_id} projected SoC {projected_soc:.2f} MWh below mandatory storm reserve floor {storm_floor_mwh:.2f} MWh"
                        )

        # 3. Critical Load Protection: Critical load must never be unserved in planned dispatch
        unserved_tot = sum(act.unserved_critical.values())
        if unserved_tot > 1e-3:
            violations.append(f"Planned dispatch sheds critical customer load: {unserved_tot:.2f} MW")

        # Demand response checks
        for c_id, c_spec in self.consumers.items():
            dr_val = act.demand_response.get(c_id, 0.0)
            dr_max = float(c_spec.get("dr_max_mw", 0.0))
            if dr_val > dr_max + 1e-3:
                violations.append(f"DR called on {c_id} ({dr_val:.2f} MW) exceeds contract max ({dr_max:.2f} MW)")

        # 4. Energy Balance Verification
        gen_side = (
            sum(current_state.solar_actual[s] - act.solar_curtailment.get(s, 0.0) for s in self.solar_farms)
            + sum(current_state.wind_actual[w] - act.wind_curtailment.get(w, 0.0) for w in self.wind_farms)
            + sum(act.battery_discharge.get(b, 0.0) for b in self.batteries)
            + act.grid_import
        )
        load_side = (
            sum(
                current_state.demand_actual[c]
                - act.demand_response.get(c, 0.0)
                - act.contract_shortfall.get(c, 0.0)
                - act.unserved_critical.get(c, 0.0)
                for c in self.consumers
            )
            + sum(act.battery_charge.get(b, 0.0) for b in self.batteries)
            + act.grid_export
        )

        residual = abs(gen_side - load_side)
        if residual > 0.05:  # Tolerance: 50 kW
            violations.append(f"Energy balance violated: generation={gen_side:.2f} MW != load={load_side:.2f} MW (diff={residual:.3f} MW)")

        passed = len(violations) == 0
        severity = "ok" if passed else "rejected"

        return ValidationResult(
            passed=passed,
            violations=violations,
            warnings=warnings,
            severity=severity,
        )
