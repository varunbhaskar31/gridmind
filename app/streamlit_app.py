"""GridMind: Agentic Renewable Energy Orchestrator — Control Room.

Main Dashboard Entry Point for Deccan Renewables Pvt. Ltd. (Karnataka, India).
Provides shift dispatch managers with real-time situational awareness,
autonomous multi-agent reasoning traces, physical safety verification, and operational controls.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import time

from app.shared import (
    ASSETS_CFG,
    MARKET_CFG,
    MODE_COLORS,
    SEASON_A,
    SEASON_B,
    build_battery_soc_chart,
    build_energy_balance_chart,
    build_market_price_chart,
    init_session_state,
    load_preset_scenario,
    reset_simulation,
)
from gridmind.sim.events import Event

st.set_page_config(
    page_title="GridMind Control Room — Deccan Renewables",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom light styling for crisp professional presentation
st.markdown(
    """
    <style>
    .kpi-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .kpi-title { font-size: 0.85rem; color: #64748B; font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }
    .kpi-value { font-size: 1.5rem; font-weight: 700; color: #0F172A; }
    .mode-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        color: white;
        font-weight: 600;
        font-size: 0.9rem;
    }
    .briefing-box {
        background-color: #F0FDF4;
        border-left: 4px solid #10B981;
        padding: 14px 18px;
        border-radius: 4px;
        margin-bottom: 12px;
    }
    .warning-box {
        background-color: #FEF2F2;
        border-left: 4px solid #EF4444;
        padding: 14px 18px;
        border-radius: 4px;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

init_session_state()
orch = st.session_state.orchestrator
history = st.session_state.step_history

# ==================== SIDEBAR CONTROLS ====================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/electricity.png", width=64)
    st.title("GridMind Orchestrator")
    st.caption("ET AI Hackathon | PS4: Renewable Orchestrator")
    st.markdown("---")

    st.subheader("Simulation Controls")

    scenario_choice = st.selectbox(
        "Active Scenario",
        ["A Day at Deccan (Disturbance Demo)", "Nominal Summer Operation", "Monsoon Strong Wind"],
        index=0,
    )

    if st.button("Load & Reset Scenario", use_container_width=True):
        if "Deccan" in scenario_choice:
            load_preset_scenario("day_at_deccan")
        elif "Monsoon" in scenario_choice:
            reset_simulation("Season B (Monsoon)")
        else:
            reset_simulation("Season A (Summer)")
        st.rerun()

    st.markdown("---")
    st.subheader("Step Controls")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        step_clicked = st.button("▶ Step (15m)", use_container_width=True)
    with col_btn2:
        step10_clicked = st.button("⏩ Run 10 Int", use_container_width=True)

    col_btn3, col_btn4 = st.columns(2)
    with col_btn3:
        run_day_clicked = st.button("⚡ Run Full Day", use_container_width=True)
    with col_btn4:
        reset_clicked = st.button("🔄 Reset", use_container_width=True)

    if reset_clicked:
        reset_simulation()
        st.rerun()

    st.markdown("---")
    st.subheader("Operational Persona")
    st.info("**Shift Dispatch Manager**\nControl Room Desk, Bengaluru HQ\nDeccan Renewables Pvt. Ltd.")

# Execute Step Logic
if step_clicked:
    if not orch.simulator.is_done():
        res = orch.step()
        st.session_state.step_history.append(res)
    st.rerun()

if step10_clicked:
    for _ in range(10):
        if orch.simulator.is_done():
            break
        res = orch.step()
        st.session_state.step_history.append(res)
    st.rerun()

if run_day_clicked:
    progress_bar = st.progress(0.0)
    for i in range(96):
        if orch.simulator.is_done():
            break
        res = orch.step()
        st.session_state.step_history.append(res)
        progress_bar.progress((i + 1) / 96.0)
    st.rerun()


# ==================== MAIN CONTROL ROOM UI ====================

# Top Header Bar
latest_step = history[-1] if history else None
current_state = orch.simulator.current_state()

col_h1, col_h2, col_h3 = st.columns([2, 1, 1])

with col_h1:
    st.title("⚡ Portfolio Control Room")
    st.caption(f"Asset Base: 5 Solar Farms (500 MW) | 3 Wind Farms (240 MW) | 2 BESS (100 MW / 400 MWh) | 4 Industrial Consumers (300 MW)")

with col_h2:
    mode_name = latest_step.decision.mode if latest_step else "green"
    badge_color = MODE_COLORS.get(mode_name, "#10B981")
    st.markdown(
        f"<div style='text-align: right; margin-top: 10px;'>"
        f"<div style='font-size: 0.8rem; color: #64748B;'>DISPATCH MODE</div>"
        f"<span class='mode-badge' style='background-color: {badge_color};'>{mode_name.upper()}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

with col_h3:
    is_safe = latest_step.is_safe_mode if latest_step else False
    safe_text = "NORMAL (MILP)" if not is_safe else "SAFE-MODE ENGAGED"
    safe_color = "#10B981" if not is_safe else "#EF4444"
    st.markdown(
        f"<div style='text-align: right; margin-top: 10px;'>"
        f"<div style='font-size: 0.8rem; color: #64748B;'>GOVERNANCE GATE</div>"
        f"<span style='color: {safe_color}; font-weight: 700; font-size: 0.95rem;'>🛡️ {safe_text}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

# Current Timestamp and Progress
curr_time_str = current_state.timestamp
curr_int_idx = current_state.interval_index
st.markdown(f"**Simulated Interval:** `{curr_int_idx} / 96` | **Timestamp:** `{curr_time_str}` | **Active Season:** `{st.session_state.season}`")

# Active Events Alert Banner
active_evs = current_state.active_events
if active_evs:
    ev_badges = " ".join([f"`[{e.event_type.upper()}]`" for e in active_evs])
    st.warning(f"⚠️ **ACTIVE DISTURBANCES DETECTED:** {ev_badges} — Autonomous dispatch adaptation in progress.")


# KPI Scorecards
kpis = orch.metrics_tracker.current_metrics()

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.metric("Net Cost Today", f"₹{kpis.total_net_cost_inr:,.0f}")
with c2:
    st.metric("Carbon Emissions", f"{kpis.carbon_emissions_tco2:.1f} tCO₂")
with c3:
    st.metric("Renewable Util.", f"{kpis.renewable_utilization_pct:.1f}%")
with c4:
    st.metric("Curtailment", f"{kpis.curtailment_mwh:.1f} MWh")
with c5:
    st.metric("Shortfall Penalty", f"₹{kpis.shortfall_penalty_inr:,.0f}")
with c6:
    b1_pct = current_state.battery_soc_pct.get("B1", 0.5) * 100
    b2_pct = current_state.battery_soc_pct.get("B2", 0.5) * 100
    st.metric("Battery SoCs", f"{b1_pct:.0f}% | {b2_pct:.0f}%")

st.markdown("---")

# Operator Shift Briefing Card
if latest_step and latest_step.explanation:
    exp = latest_step.explanation
    st.markdown(
        f"""
        <div class="briefing-box">
            <h4 style="margin: 0 0 6px 0; color: #065F46;">📢 Shift Briefing: "{exp.headline}"</h4>
            <div style="font-size: 0.95rem; color: #1E293B; margin-bottom: 6px;">
                <b>Actions:</b> {exp.what_we_did}
            </div>
            <div style="font-size: 0.9rem; color: #334155; margin-bottom: 4px;">
                <b>Why:</b> {exp.why}
            </div>
            <div style="font-size: 0.9rem; color: #334155; margin-bottom: 4px;">
                <b>Accepted Trade-off:</b> {exp.tradeoff}
            </div>
            <div style="font-size: 0.85rem; color: #047857;">
                <b>Pivot Trigger:</b> {exp.what_would_change_our_mind}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.info("💡 Simulation initialized at interval 0. Click **Step (15m)** or **Run 10 Int** on the sidebar to begin autonomous dispatch.")


# Live Charts Grid
tab_power, tab_battery, tab_price = st.tabs(["⚡ 15-Min Power Balance", "🔋 Battery State of Charge", "📈 Electricity Tariff & Forecast"])

with tab_power:
    fig_power = build_energy_balance_chart(history)
    st.plotly_chart(fig_power, use_container_width=True, key="chart_power_balance")

with tab_battery:
    fig_battery = build_battery_soc_chart(history)
    st.plotly_chart(fig_battery, use_container_width=True, key="chart_battery_soc")

with tab_price:
    latest_fcst = orch.forecaster.forecast(current_state) if history else None
    fig_price = build_market_price_chart(history, latest_fcst)
    st.plotly_chart(fig_price, use_container_width=True, key="chart_market_price")
