"""Shared session state and plotting helpers for the GridMind Streamlit application.

Preserves the active orchestrator, simulation trajectory, KPI logs,
and scenario configurations across multipage navigation.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from typing import Any, Dict, List, Optional
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

from gridmind.agents.llm_client import LLMClient
from gridmind.orchestrator import GridMindOrchestrator
from gridmind.sim.events import Event

DATA_DIR = BASE_DIR / "data" / "processed"
CONFIG_DIR = BASE_DIR / "config"

ASSETS_CFG = CONFIG_DIR / "assets.yaml"
MARKET_CFG = CONFIG_DIR / "market.yaml"
AGENT_CFG = CONFIG_DIR / "agent.yaml"
SCENARIOS_CFG = CONFIG_DIR / "scenarios.yaml"

SEASON_A = DATA_DIR / "season_A.csv"
SEASON_B = DATA_DIR / "season_B.csv"

MODE_COLORS = {
    "green": "#10B981",              # Emerald green
    "economic": "#3B82F6",           # Blue
    "reliability_first": "#8B5CF6",  # Violet
    "storm_preparation": "#EF4444",  # Red
    "outage_recovery": "#F59E0B",    # Amber
    "congestion_management": "#EC4899", # Pink
    "safe_mode": "#DC2626",          # Crimson
}


def load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def init_session_state() -> None:
    """Initialize persistent Streamlit session state."""
    if "season" not in st.session_state:
        st.session_state.season = "Season A (Summer)"

    if "orchestrator" not in st.session_state:
        dataset = SEASON_A if "Summer" in st.session_state.season else SEASON_B
        st.session_state.orchestrator = GridMindOrchestrator(
            dataset_path=dataset,
            assets_config_path=ASSETS_CFG,
            market_config_path=MARKET_CFG,
            agent_config_path=AGENT_CFG,
            auto_approve_operator=True,
            strategy_refresh_interval=4,
        )
        st.session_state.orchestrator.reset()

    if "step_history" not in st.session_state:
        st.session_state.step_history = []

    if "active_scenario" not in st.session_state:
        st.session_state.active_scenario = "nominal"

    if "is_running" not in st.session_state:
        st.session_state.is_running = False


def reset_simulation(season_name: Optional[str] = None) -> None:
    """Hard reset of simulation environment and history."""
    if season_name:
        st.session_state.season = season_name
    dataset = SEASON_A if "Summer" in st.session_state.season else SEASON_B
    st.session_state.orchestrator = GridMindOrchestrator(
        dataset_path=dataset,
        assets_config_path=ASSETS_CFG,
        market_config_path=MARKET_CFG,
        agent_config_path=AGENT_CFG,
        auto_approve_operator=True,
        strategy_refresh_interval=4,
    )
    st.session_state.orchestrator.reset()
    st.session_state.step_history = []
    st.session_state.is_running = False


def load_preset_scenario(scenario_key: str) -> None:
    """Inject scenario events from scenarios.yaml into active simulator."""
    scenarios_data = load_yaml(SCENARIOS_CFG)
    reset_simulation()

    if scenario_key == "day_at_deccan":
        scen = scenarios_data.get("day_at_deccan", {})
        for ev in scen.get("events", []):
            etype = ev.get("type")
            start = int(ev.get("interval", 0))
            dur = int(ev.get("duration_intervals", 4))
            mag = float(ev.get("magnitude", 1.0))
            assets = ev.get("affected_assets")
            extra = {}
            if "wind_cut_out" in ev:
                extra["wind_cut_out"] = ev["wind_cut_out"]
            if "export_limit_mw" in ev:
                extra["export_limit_mw"] = ev["export_limit_mw"]

            event_obj = Event(
                event_type=etype,
                start_interval=start,
                duration_intervals=dur,
                magnitude=mag,
                affected_assets=assets,
                extra_params=extra,
                announced_at=max(0, start - ev.get("announced_lead_intervals", 0)),
                description=f"Preset {etype} event",
            )
            st.session_state.orchestrator.inject_event(event_obj)
        st.session_state.active_scenario = "day_at_deccan"


def build_energy_balance_chart(history: List[Any]) -> go.Figure:
    """Build stacked generation + dispatch vs demand line chart."""
    fig = go.Figure()

    if not history:
        fig.update_layout(title="No interval data available. Click Step or Run to begin.")
        return fig

    intervals = [h.interval_index for h in history]
    timestamps = [h.timestamp for h in history]

    solar_mw = [sum(h.state.solar_actual.values()) - sum(h.executed_action.solar_curtailment.values()) for h in history]
    wind_mw = [sum(h.state.wind_actual.values()) - sum(h.executed_action.wind_curtailment.values()) for h in history]
    b1_dis = [h.executed_action.battery_discharge.get("B1", 0.0) for h in history]
    b2_dis = [h.executed_action.battery_discharge.get("B2", 0.0) for h in history]
    grid_imp = [h.executed_action.grid_import for h in history]

    # Negative flows (charging & export)
    b1_ch = [-h.executed_action.battery_charge.get("B1", 0.0) for h in history]
    b2_ch = [-h.executed_action.battery_charge.get("B2", 0.0) for h in history]
    grid_exp = [-h.executed_action.grid_export for h in history]

    demand_mw = [sum(h.state.demand_actual.values()) for h in history]

    # Positive generation & discharge
    fig.add_trace(go.Scatter(x=intervals, y=solar_mw, mode="lines", stackgroup="supply", name="Solar (Net)", line=dict(color="#F59E0B", width=0.5), fillcolor="rgba(245, 158, 11, 0.7)"))
    fig.add_trace(go.Scatter(x=intervals, y=wind_mw, mode="lines", stackgroup="supply", name="Wind (Net)", line=dict(color="#10B981", width=0.5), fillcolor="rgba(16, 185, 129, 0.7)"))
    fig.add_trace(go.Scatter(x=intervals, y=b1_dis, mode="lines", stackgroup="supply", name="B1 Discharge", line=dict(color="#8B5CF6", width=0.5), fillcolor="rgba(139, 92, 246, 0.7)"))
    fig.add_trace(go.Scatter(x=intervals, y=b2_dis, mode="lines", stackgroup="supply", name="B2 Discharge", line=dict(color="#A78BFA", width=0.5), fillcolor="rgba(167, 139, 250, 0.7)"))
    fig.add_trace(go.Scatter(x=intervals, y=grid_imp, mode="lines", stackgroup="supply", name="Grid Import", line=dict(color="#6B7280", width=0.5), fillcolor="rgba(107, 114, 128, 0.6)"))

    # Negative storage absorption and grid sales
    fig.add_trace(go.Scatter(x=intervals, y=b1_ch, mode="lines", stackgroup="absorption", name="B1 Charging", line=dict(color="#8B5CF6", width=0.5), fillcolor="rgba(139, 92, 246, 0.4)"))
    fig.add_trace(go.Scatter(x=intervals, y=b2_ch, mode="lines", stackgroup="absorption", name="B2 Charging", line=dict(color="#A78BFA", width=0.5), fillcolor="rgba(167, 139, 250, 0.4)"))
    fig.add_trace(go.Scatter(x=intervals, y=grid_exp, mode="lines", stackgroup="absorption", name="Grid Export", line=dict(color="#3B82F6", width=0.5), fillcolor="rgba(59, 130, 246, 0.5)"))

    # Demand line
    fig.add_trace(go.Scatter(x=intervals, y=demand_mw, mode="lines+markers", name="Customer Demand (MW)", line=dict(color="#111827", width=2.5, dash="dot")))

    fig.update_layout(
        title="15-Minute Power Balance (Generation, Storage & Grid vs Contract Demand)",
        xaxis_title="Interval (15-min)",
        yaxis_title="Power (MW)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=60, b=40),
    )
    return fig


def build_battery_soc_chart(history: List[Any]) -> go.Figure:
    """Build battery state of charge trajectory with reserve floor."""
    fig = go.Figure()
    if not history:
        fig.update_layout(title="Battery State of Charge Trajectory (Click Step to begin)", template="plotly_white")
        return fig

    intervals = [h.interval_index for h in history]
    b1_soc_pct = [h.state.battery_soc_pct.get("B1", 0.5) * 100 for h in history]
    b2_soc_pct = [h.state.battery_soc_pct.get("B2", 0.5) * 100 for h in history]
    reserve_floor_pct = [h.decision.reserve_floor * 100 for h in history]

    fig.add_trace(go.Scatter(x=intervals, y=b1_soc_pct, mode="lines+markers", name="B1 SoC (240 MWh)", line=dict(color="#8B5CF6", width=2.5)))
    fig.add_trace(go.Scatter(x=intervals, y=b2_soc_pct, mode="lines+markers", name="B2 SoC (160 MWh)", line=dict(color="#3B82F6", width=2.5)))
    fig.add_trace(go.Scatter(x=intervals, y=reserve_floor_pct, mode="lines", name="Mandatory Reserve Floor (%)", line=dict(color="#EF4444", width=2, dash="dash")))

    fig.update_layout(
        title="Battery State of Charge Trajectory vs Dynamic Reserve Floor",
        xaxis_title="Interval (15-min)",
        yaxis_title="State of Charge (%)",
        yaxis=dict(range=[0, 100]),
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=60, b=40),
    )
    return fig


def build_market_price_chart(history: List[Any], latest_fcst: Optional[Any] = None) -> go.Figure:
    """Build IEX actual price trajectory and rolling uncertainty band."""
    fig = go.Figure()
    if not history:
        fig.update_layout(title="Electricity Tariff & Forecast (Click Step to begin)", template="plotly_white")
        return fig

    intervals = [h.interval_index for h in history]
    prices = [h.state.price_actual for h in history]

    fig.add_trace(go.Scatter(x=intervals, y=prices, mode="lines+markers", name="IEX Electricity Price (₹/MWh)", line=dict(color="#10B981", width=2.5)))

    # If forecast cone available, append rolling P10-P90 cone
    if latest_fcst and history:
        last_int = intervals[-1]
        fcst_ints = list(range(last_int + 1, last_int + 1 + len(latest_fcst.price_p50)))
        p10 = latest_fcst.price_p10
        p90 = latest_fcst.price_p90
        p50 = latest_fcst.price_p50

        fig.add_trace(go.Scatter(x=fcst_ints, y=p90, mode="lines", line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=fcst_ints, y=p10, mode="lines", fill="tonexty", fillcolor="rgba(16, 185, 129, 0.2)", name="P10–P90 Price Forecast Cone", line=dict(width=0)))
        fig.add_trace(go.Scatter(x=fcst_ints, y=p50, mode="lines", name="P50 Forecast", line=dict(color="#059669", width=1.5, dash="dash")))

    fig.update_layout(
        title="Electricity Market Price (IEX Actuals + Forecast Horizon)",
        xaxis_title="Interval (15-min)",
        yaxis_title="Price (₹/MWh)",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=60, b=40),
    )
    return fig
