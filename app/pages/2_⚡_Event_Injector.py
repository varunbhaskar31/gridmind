"""Interactive Disturbance & Weather Front Event Injector.

Allows shift operators and hackathon judges to inject live disturbances
into the running simulation to test GridMind's autonomous reasoning and recovery.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.shared import init_session_state
from gridmind.sim.events import Event

st.set_page_config(page_title="Event Injector — GridMind", page_icon="⚡", layout="wide")
init_session_state()

orch = st.session_state.orchestrator
current_state = orch.simulator.current_state()
curr_int = current_state.interval_index

st.title("⚡ Dynamic Disturbance & Weather Front Injector")
st.markdown("Inject operational events into the live simulation to test the autonomous Monitor, Strategist, and Guardrail layers.")

# Active & Upcoming Events Section
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("🔴 Currently Active Events")
    active_events = current_state.active_events
    if active_events:
        for ev in active_events:
            st.error(f"**{ev.event_type.upper()}** (Remaining: {ev.remaining_intervals} intervals) — {ev.description}")
    else:
        st.success("No active disturbances affecting the portfolio. Nominal operating conditions.")

with col_right:
    st.subheader("📢 Announced Upcoming Events")
    announced_events = orch.simulator.event_manager.get_announced_events(curr_int)
    upcoming = [e for e in announced_events if e.start_interval > curr_int]
    if upcoming:
        for ev in upcoming:
            st.info(f"**{ev.event_type.upper()}** arrives at interval `{ev.start_interval}` (in {ev.start_interval - curr_int} intervals) — {ev.description}")
    else:
        st.write("No forward weather or curtailment warnings pending.")

st.markdown("---")
st.subheader("Inject New Event")

tab_cloud, tab_storm, tab_outage, tab_price, tab_line = st.tabs([
    "☁️ Cloud Cover", "🌪️ Severe Storm Alert", "🔋 Battery Trip", "📈 Tariff Price Spike", "⚡ Transmission Congestion"
])

# 1. Cloud Cover
with tab_cloud:
    st.markdown("Simulate sudden cloud cover over solar parks in Pavagada / Tumakuru.")
    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        c_assets = st.multiselect("Affected Solar Farms", ["S1", "S2", "S3", "S4", "S5"], default=["S1", "S2"])
    with col_c2:
        c_mag = st.slider("Solar Output Reduction (%)", 10, 90, 60) / 100.0
    with col_c3:
        c_dur = st.number_input("Duration (15-min intervals)", min_value=1, max_value=24, value=8)

    if st.button("Inject Cloud Cover Event", type="primary"):
        ev = Event(
            event_type="cloud_cover",
            start_interval=curr_int,
            duration_intervals=c_dur,
            magnitude=c_mag,
            affected_assets=c_assets,
            description=f"Cloud cover reducing {', '.join(c_assets)} solar generation by {int(c_mag*100)}%",
        )
        orch.inject_event(ev)
        st.success(f"Injected cloud cover event starting at interval {curr_int}!")
        st.rerun()

# 2. Storm Alert
with tab_storm:
    st.markdown("Issue advance warning of severe cyclone / storm front with wind turbine survival shut-downs.")
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        lead_time = st.slider("Announcement Advance Notice (Hours)", 0.0, 6.0, 2.0)
    with col_s2:
        s_dur = st.number_input("Storm Duration (Intervals)", 4, 32, 12)
    with col_s3:
        wind_trip = st.checkbox("Force Wind Turbine Cut-out Shutdown", value=True)

    if st.button("Issue Storm Alert", type="primary"):
        lead_intervals = int(lead_time * 4)
        target_int = curr_int + lead_intervals
        ev = Event(
            event_type="storm_alert",
            start_interval=target_int,
            duration_intervals=s_dur,
            magnitude=0.80,
            announced_at=curr_int,
            extra_params={"wind_cut_out": wind_trip, "export_limit_mw": 80.0},
            description=f"Severe storm alert arriving at interval {target_int} (in {lead_time} hrs)",
        )
        orch.inject_event(ev)
        st.success(f"Announced storm alert arriving at interval {target_int}!")
        st.rerun()

# 3. Battery Outage
with tab_outage:
    st.markdown("Trigger unexpected inverter failure or cell thermal shutdown on battery storage assets.")
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        b_target = st.selectbox("Battery Asset", ["B1 (60 MW / 240 MWh)", "B2 (40 MW / 160 MWh)"])
        b_id = "B1" if "B1" in b_target else "B2"
    with col_b2:
        b_dur = st.number_input("Outage Duration (Intervals)", 4, 48, 16)

    if st.button("Trigger Battery Forced Outage", type="primary"):
        ev = Event(
            event_type="battery_outage",
            start_interval=curr_int,
            duration_intervals=b_dur,
            magnitude=1.0,
            affected_assets=[b_id],
            description=f"Inverter trip causing forced outage on {b_id}",
        )
        orch.inject_event(ev)
        st.success(f"Triggered forced outage on {b_id} for {b_dur} intervals!")
        st.rerun()

# 4. Price Spike
with tab_price:
    st.markdown("Simulate an unexpected tariff spike on the Indian Energy Exchange (IEX).")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        p_mult = st.slider("Price Spike Multiplier", 1.5, 3.5, 2.2)
    with col_p2:
        p_dur = st.number_input("Price Spike Duration (Intervals)", 1, 12, 4)

    if st.button("Inject Electricity Price Spike", type="primary"):
        ev = Event(
            event_type="price_spike",
            start_interval=curr_int,
            duration_intervals=p_dur,
            magnitude=p_mult,
            description=f"IEX price spike ({p_mult}x tariff)",
        )
        orch.inject_event(ev)
        st.success(f"Injected price spike ({p_mult}x) for {p_dur} intervals!")
        st.rerun()

# 5. Line Congestion
with tab_line:
    st.markdown("Simulate evacuation corridor limit derating due to state transmission line maintenance.")
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        l_cap = st.slider("Derated Export Limit (MW)", 40.0, 160.0, 100.0)
    with col_l2:
        l_dur = st.number_input("Congestion Duration (Intervals)", 2, 24, 8)

    if st.button("Derate Transmission Corridor", type="primary"):
        ev = Event(
            event_type="line_constraint",
            start_interval=curr_int,
            duration_intervals=l_dur,
            magnitude=l_cap,
            extra_params={"export_limit_mw": l_cap},
            description=f"Corridor congestion de-rating export limit to {l_cap} MW",
        )
        orch.inject_event(ev)
        st.success(f"De-rated transmission export corridor to {l_cap} MW for {l_dur} intervals!")
        st.rerun()
