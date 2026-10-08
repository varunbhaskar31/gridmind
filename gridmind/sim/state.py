"""Pydantic models representing grid state, dispatch actions, events, and KPIs.

Ensures strict typing, serialization, and validation across simulator,
optimizer, guardrails, and dashboard components.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ActiveEvent(BaseModel):
    """An active or announced grid/market event."""
    event_type: str = Field(..., description="Event type identifier (e.g. cloud_cover, storm_alert)")
    description: str = Field(..., description="Human-readable explanation of the event")
    start_interval: int = Field(..., description="Interval index where event starts affecting actuals")
    duration_intervals: int = Field(..., description="Duration of event impact in 15-min intervals")
    remaining_intervals: int = Field(..., description="Intervals remaining until event expiration")
    affected_assets: List[str] = Field(default_factory=list, description="Asset IDs impacted")
    magnitude: float = Field(1.0, description="Magnitude scaling or parameter value")
    announced_at: int = Field(0, description="Interval index when event was announced")


class DispatchAction(BaseModel):
    """Dispatch actions executed in a single 15-minute interval."""
    battery_charge: Dict[str, float] = Field(
        default_factory=dict, description="Charging power requested per battery (MW)"
    )
    battery_discharge: Dict[str, float] = Field(
        default_factory=dict, description="Discharging power requested per battery (MW)"
    )
    grid_import: float = Field(0.0, description="Power imported from transmission grid (MW)")
    grid_export: float = Field(0.0, description="Power exported/sold to transmission grid (MW)")
    solar_curtailment: Dict[str, float] = Field(
        default_factory=dict, description="Curtailment per solar farm (MW)"
    )
    wind_curtailment: Dict[str, float] = Field(
        default_factory=dict, description="Curtailment per wind farm (MW)"
    )
    demand_response: Dict[str, float] = Field(
        default_factory=dict, description="Demand response invoked per consumer (MW)"
    )
    contract_shortfall: Dict[str, float] = Field(
        default_factory=dict, description="Unmet non-critical contracted load per consumer (MW)"
    )
    unserved_critical: Dict[str, float] = Field(
        default_factory=dict, description="Unserved critical load per consumer (MW, slack variable)"
    )
    balance_slack: float = Field(0.0, description="Energy balance residual slack (MW)")


class IntervalKPIs(BaseModel):
    """Financial, operational, and physical KPIs for one 15-minute interval."""
    interval_index: int
    timestamp: str
    net_cost_inr: float = 0.0
    revenue_sales_inr: float = 0.0
    purchase_cost_inr: float = 0.0
    carbon_emissions_tco2: float = 0.0
    carbon_cost_inr: float = 0.0
    renewable_utilization_pct: float = 0.0
    curtailment_mwh: float = 0.0
    battery_throughput_mwh: float = 0.0
    contract_shortfall_mwh: float = 0.0
    shortfall_penalty_inr: float = 0.0
    unserved_critical_mwh: float = 0.0
    unserved_penalty_inr: float = 0.0
    dr_cost_inr: float = 0.0
    battery_degradation_cost_inr: float = 0.0
    energy_balance_slack_mw: float = 0.0
    hard_violations: List[str] = Field(default_factory=list)


class CumulativeKPIs(BaseModel):
    """Aggregated portfolio performance metrics over the entire simulation horizon."""
    total_net_cost_inr: float = 0.0
    total_revenue_sales_inr: float = 0.0
    total_purchase_cost_inr: float = 0.0
    total_carbon_emissions_tco2: float = 0.0
    total_carbon_cost_inr: float = 0.0
    avg_renewable_utilization_pct: float = 0.0
    total_curtailment_mwh: float = 0.0
    total_battery_throughput_mwh: float = 0.0
    battery_equivalent_cycles: Dict[str, float] = Field(default_factory=dict)
    total_contract_shortfall_mwh: float = 0.0
    total_shortfall_penalty_inr: float = 0.0
    total_unserved_critical_mwh: float = 0.0
    total_unserved_penalty_inr: float = 0.0
    total_dr_cost_inr: float = 0.0
    total_battery_degradation_cost_inr: float = 0.0
    total_hard_violations: int = 0
    intervals_completed: int = 0


class GridState(BaseModel):
    """Complete snapshot of grid, market, assets, and storage at a specific 15-minute interval."""
    timestamp: str = Field(..., description="ISO timestamp of interval start")
    interval_index: int = Field(..., description="Interval counter (0-indexed)")
    
    # Asset Actual Generation (MW)
    solar_actual: Dict[str, float] = Field(default_factory=dict, description="Solar output (MW)")
    wind_actual: Dict[str, float] = Field(default_factory=dict, description="Wind output (MW)")
    
    # Consumer Actual Demand (MW)
    demand_actual: Dict[str, float] = Field(default_factory=dict, description="Load demanded (MW)")
    
    # Market Price (₹/MWh)
    price_actual: float = Field(0.0, description="Actual market clearing price (₹/MWh)")
    
    # Storage Status
    battery_soc: Dict[str, float] = Field(default_factory=dict, description="Current energy in MWh")
    battery_soc_pct: Dict[str, float] = Field(default_factory=dict, description="State of Charge fraction (0.0 - 1.0)")
    
    # Asset Availabilities
    battery_available: Dict[str, bool] = Field(default_factory=dict, description="Battery operability")
    solar_available: Dict[str, bool] = Field(default_factory=dict, description="Solar farm operability")
    wind_available: Dict[str, bool] = Field(default_factory=dict, description="Wind farm operability")
    
    # Transmission Constraints
    grid_import_limit_mw: float = Field(150.0, description="Current max import capacity (MW)")
    grid_export_limit_mw: float = Field(200.0, description="Current max export capacity (MW)")
    
    # Active & Announced Events
    active_events: List[ActiveEvent] = Field(default_factory=list, description="Currently active events")
    
    # Actions & KPIs
    last_actions: Optional[DispatchAction] = Field(None, description="Actions executed in previous interval")
    kpis: CumulativeKPIs = Field(default_factory=CumulativeKPIs, description="Cumulative portfolio KPIs")
