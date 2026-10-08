"""Heuristic baseline dispatchers and fail-safe fallback logic.

1. rule_based_baseline:
   Myopic "how it's done today" heuristic without price or forecast awareness.
   Charges storage during surplus, discharges during deficit, trades balance with grid.

2. safe_mode_dispatch:
   High-reliability deterministic fallback activated if the MILP solver or agent fails.
   Preserves 40% battery reserve, halts speculative market exports, and guarantees critical loads.
"""

from typing import Any, Dict
from gridmind.sim.state import DispatchAction, GridState


def rule_based_baseline_dispatch(
    state: GridState,
    battery_specs: Dict[str, Dict[str, Any]],
    consumer_specs: Dict[str, Dict[str, Any]],
) -> DispatchAction:
    """Myopic rule-based baseline: charges on surplus, discharges on deficit.

    - No price awareness, no forward forecasts.
    - Used as the benchmark comparison to quantify GridMind's economic and carbon impact.
    """
    total_re = sum(state.solar_actual.values()) + sum(state.wind_actual.values())
    total_dem = sum(state.demand_actual.values())

    b_charge: Dict[str, float] = {b: 0.0 for b in battery_specs}
    b_discharge: Dict[str, float] = {b: 0.0 for b in battery_specs}
    solar_curt: Dict[str, float] = {s: 0.0 for s in state.solar_actual}
    wind_curt: Dict[str, float] = {w: 0.0 for w in state.wind_actual}
    shortfall: Dict[str, float] = {c: 0.0 for c in state.demand_actual}
    unserved: Dict[str, float] = {c: 0.0 for c in state.demand_actual}

    if total_re >= total_dem:
        surplus = total_re - total_dem
        # Charge available batteries up to power & energy headroom
        for b_id, b_spec in battery_specs.items():
            if not state.battery_available.get(b_id, True):
                continue
            e_cap = float(b_spec["energy_mwh"])
            soc_max_mwh = e_cap * float(b_spec.get("soc_max", 0.95))
            headroom = max(0.0, (soc_max_mwh - state.battery_soc[b_id]) / (0.95 * 0.25))
            ch = min(float(b_spec["power_mw"]), headroom, surplus)
            b_charge[b_id] = round(ch, 3)
            surplus -= ch

        # Export surplus to grid up to line limit
        grid_exp = round(min(state.grid_export_limit_mw, surplus), 3)
        surplus -= grid_exp

        # Curtail excess generation across solar farms
        for s_id, s_mw in state.solar_actual.items():
            if surplus <= 0:
                break
            c_val = min(s_mw, surplus)
            solar_curt[s_id] = round(c_val, 3)
            surplus -= c_val

        return DispatchAction(
            battery_charge=b_charge,
            battery_discharge=b_discharge,
            grid_import=0.0,
            grid_export=grid_exp,
            solar_curtailment=solar_curt,
            wind_curtailment=wind_curt,
        )

    else:
        deficit = total_dem - total_re
        # Discharge batteries up to power & energy minimum bounds
        for b_id, b_spec in battery_specs.items():
            if not state.battery_available.get(b_id, True):
                continue
            e_cap = float(b_spec["energy_mwh"])
            soc_min_mwh = e_cap * float(b_spec.get("soc_min", 0.10))
            available_energy = max(0.0, (state.battery_soc[b_id] - soc_min_mwh) * 0.95 / 0.25)
            dis = min(float(b_spec["power_mw"]), available_energy, deficit)
            b_discharge[b_id] = round(dis, 3)
            deficit -= dis

        # Import deficit from grid up to line limit
        grid_imp = round(min(state.grid_import_limit_mw, deficit), 3)
        deficit -= grid_imp

        # Shortfall remaining deficit across non-critical consumer loads
        for c_id, c_mw in state.demand_actual.items():
            if deficit <= 0:
                break
            crit_frac = float(consumer_specs[c_id].get("critical_fraction", 0.50))
            non_crit_cap = c_mw * (1.0 - crit_frac)
            sh = min(non_crit_cap, deficit)
            shortfall[c_id] = round(sh, 3)
            deficit -= sh

        # If still unserved, cuts critical load (slack)
        for c_id, c_mw in state.demand_actual.items():
            if deficit <= 0:
                break
            crit_frac = float(consumer_specs[c_id].get("critical_fraction", 0.50))
            crit_cap = c_mw * crit_frac
            un = min(crit_cap, deficit)
            unserved[c_id] = round(un, 3)
            deficit -= un

        return DispatchAction(
            battery_charge=b_charge,
            battery_discharge=b_discharge,
            grid_import=grid_imp,
            grid_export=0.0,
            contract_shortfall=shortfall,
            unserved_critical=unserved,
        )


def safe_mode_dispatch(
    state: GridState,
    battery_specs: Dict[str, Dict[str, Any]],
    consumer_specs: Dict[str, Dict[str, Any]],
) -> DispatchAction:
    """Safe-mode conservative dispatch executed when the MILP solver fails or guardrails fail.

    Safety principles:
    - Zero speculative exports (grid_export = 0).
    - Preserves battery reserve above 40% unless required to protect critical loads.
    - Fully imports from grid up to maximum line capacity before any contract shortfall.
    - Guaranteed zero critical load shedding if grid import capacity permits.
    """
    total_re = sum(state.solar_actual.values()) + sum(state.wind_actual.values())
    total_dem = sum(state.demand_actual.values())

    b_charge: Dict[str, float] = {b: 0.0 for b in battery_specs}
    b_discharge: Dict[str, float] = {b: 0.0 for b in battery_specs}
    solar_curt: Dict[str, float] = {s: 0.0 for s in state.solar_actual}
    wind_curt: Dict[str, float] = {w: 0.0 for w in state.wind_actual}
    shortfall: Dict[str, float] = {c: 0.0 for c in state.demand_actual}
    unserved: Dict[str, float] = {c: 0.0 for c in state.demand_actual}

    if total_re >= total_dem:
        surplus = total_re - total_dem
        # Charge batteries up to 95% SoC
        for b_id, b_spec in battery_specs.items():
            if not state.battery_available.get(b_id, True):
                continue
            e_cap = float(b_spec["energy_mwh"])
            soc_max_mwh = e_cap * float(b_spec.get("soc_max", 0.95))
            headroom = max(0.0, (soc_max_mwh - state.battery_soc[b_id]) / (0.95 * 0.25))
            ch = min(float(b_spec["power_mw"]), headroom, surplus)
            b_charge[b_id] = round(ch, 3)
            surplus -= ch

        # In safe mode, excess is curtailed cleanly rather than exported if grid risk exists
        for s_id, s_mw in state.solar_actual.items():
            if surplus <= 0:
                break
            c_val = min(s_mw, surplus)
            solar_curt[s_id] = round(c_val, 3)
            surplus -= c_val

        return DispatchAction(
            battery_charge=b_charge,
            battery_discharge=b_discharge,
            grid_import=0.0,
            grid_export=0.0,
            solar_curtailment=solar_curt,
            wind_curtailment=wind_curt,
        )

    else:
        deficit = total_dem - total_re
        # Safe mode discharge: hold battery at 40% reserve floor unless needed for critical load
        safe_floor = 0.40
        for b_id, b_spec in battery_specs.items():
            if not state.battery_available.get(b_id, True):
                continue
            e_cap = float(b_spec["energy_mwh"])
            floor_mwh = e_cap * safe_floor
            dis_avail = max(0.0, (state.battery_soc[b_id] - floor_mwh) * 0.95 / 0.25)
            dis = min(float(b_spec["power_mw"]), dis_avail, deficit)
            b_discharge[b_id] = round(dis, 3)
            deficit -= dis

        # Maximize grid imports to avoid customer shortfall
        grid_imp = round(min(state.grid_import_limit_mw, deficit), 3)
        deficit -= grid_imp

        # If deficit remains and critical loads are threatened, tap into the remaining 40% battery reserve
        crit_load_total = sum(
            state.demand_actual[c] * float(consumer_specs[c].get("critical_fraction", 0.50))
            for c in consumer_specs
        )
        if deficit > 0:
            for b_id, b_spec in battery_specs.items():
                if not state.battery_available.get(b_id, True):
                    continue
                e_cap = float(b_spec["energy_mwh"])
                hard_min_mwh = e_cap * float(b_spec.get("soc_min", 0.10))
                deep_dis_avail = max(0.0, (state.battery_soc[b_id] - hard_min_mwh) * 0.95 / 0.25)
                deep_dis = min(float(b_spec["power_mw"]) - b_discharge[b_id], deep_dis_avail, deficit)
                b_discharge[b_id] = round(b_discharge[b_id] + deep_dis, 3)
                deficit -= deep_dis

        # Shed non-critical load next
        for c_id, c_mw in state.demand_actual.items():
            if deficit <= 0:
                break
            crit_frac = float(consumer_specs[c_id].get("critical_fraction", 0.50))
            non_crit_cap = c_mw * (1.0 - crit_frac)
            sh = min(non_crit_cap, deficit)
            shortfall[c_id] = round(sh, 3)
            deficit -= sh

        # Last resort: unserved critical load
        for c_id, c_mw in state.demand_actual.items():
            if deficit <= 0:
                break
            crit_frac = float(consumer_specs[c_id].get("critical_fraction", 0.50))
            crit_cap = c_mw * crit_frac
            un = min(crit_cap, deficit)
            unserved[c_id] = round(un, 3)
            deficit -= un

        return DispatchAction(
            battery_charge=b_charge,
            battery_discharge=b_discharge,
            grid_import=grid_imp,
            grid_export=0.0,
            contract_shortfall=shortfall,
            unserved_critical=unserved,
        )
