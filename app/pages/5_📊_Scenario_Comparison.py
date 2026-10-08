"""3-Way Strategy Comparison Benchmark Explorer.

Presents verified business impact comparing:
1. Rule-Based Heuristic Baseline
2. Fixed-Weight MILP (No Agent)
3. GridMind Autonomous Agent
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.shared import (
    AGENT_CFG,
    ASSETS_CFG,
    BASE_DIR,
    MARKET_CFG,
    SEASON_A,
    init_session_state,
)
from gridmind.compare import StrategyComparator
from gridmind.sim.events import Event

st.set_page_config(page_title="Scenario Comparison — GridMind", page_icon="📊", layout="wide")
init_session_state()

st.title("📊 3-Way Strategy Comparison & Business Impact")
st.markdown("Verifiable proof of economic and operational value comparing GridMind against traditional dispatch regimes under identical physical conditions.")

summary_csv = BASE_DIR / "data" / "processed" / "strategy_comparison_summary.csv"

col_run1, col_run2 = st.columns([3, 1])
with col_run2:
    rerun_benchmark = st.button("🔄 Re-Run 24h Benchmark (96 Intervals)", use_container_width=True)

if rerun_benchmark or not summary_csv.exists():
    with st.spinner("Executing 24h comparative simulation across Baseline, Fixed MILP, and GridMind Agent..."):
        comparator = StrategyComparator(SEASON_A, ASSETS_CFG, MARKET_CFG, AGENT_CFG)
        events = [
            Event(event_type="cloud_cover", start_interval=44, duration_intervals=8, magnitude=0.6, affected_assets=["S1", "S2"]),
            Event(event_type="price_spike", start_interval=74, duration_intervals=4, magnitude=2.2),
            Event(event_type="line_constraint", start_interval=20, duration_intervals=12, magnitude=100.0, extra_params={"export_limit_mw": 100.0}),
        ]
        summary = comparator.run_comparison(num_intervals=96, events=events)
        df_summary = summary.summary_table()
        df_summary.to_csv(summary_csv, index=False)
        st.success("24-Hour Benchmark Completed and Verified!")
else:
    df_summary = pd.read_csv(summary_csv)

# 1. Primary KPI Comparison Table
st.subheader("1. Executive Performance Scorecard")
st.dataframe(df_summary, use_container_width=True, hide_index=True)

st.markdown("---")

# 2. Key Business Impact Visualizations
st.subheader("2. Visual Impact Breakdown")

c_g1, c_g2 = st.columns(2)

with c_g1:
    # Net Cost Comparison Bar
    # Extract values from df_summary
    cost_row = df_summary[df_summary["Metric"] == "Net Cost (₹)"]
    if not cost_row.empty:
        costs = [
            float(cost_row["1. Rule Baseline"].values[0].replace("₹", "").replace(",", "")),
            float(cost_row["2. Fixed MILP"].values[0].replace("₹", "").replace(",", "")),
            float(cost_row["3. GridMind Agent"].values[0].replace("₹", "").replace(",", "")),
        ]
        fig_cost = go.Figure(data=[
            go.Bar(
                x=["1. Rule Baseline", "2. Fixed MILP", "3. GridMind Agent"],
                y=[c / 1e6 for c in costs],
                marker_color=["#EF4444", "#3B82F6", "#10B981"],
                text=[f"₹{c/1e6:.2f}M" for c in costs],
                textposition="auto",
            )
        ])
        fig_cost.update_layout(
            title="Total Daily Net Cost (₹ Millions) — Lower is Better",
            yaxis_title="Net Cost (₹M)",
            template="plotly_white",
        )
        st.plotly_chart(fig_cost, use_container_width=True, key="compare_fig_cost")

with c_g2:
    # Contract Shortfall Comparison Bar
    short_row = df_summary[df_summary["Metric"] == "Contract Shortfall (MWh)"]
    if not short_row.empty:
        shorts = [
            float(short_row["1. Rule Baseline"].values[0]),
            float(short_row["2. Fixed MILP"].values[0]),
            float(short_row["3. GridMind Agent"].values[0]),
        ]
        fig_short = go.Figure(data=[
            go.Bar(
                x=["1. Rule Baseline", "2. Fixed MILP", "3. GridMind Agent"],
                y=shorts,
                marker_color=["#EF4444", "#3B82F6", "#10B981"],
                text=[f"{s:.1f} MWh" for s in shorts],
                textposition="auto",
            )
        ])
        fig_short.update_layout(
            title="Contract Shortfall Energy (MWh) — Lower is Better",
            yaxis_title="Shortfall (MWh)",
            template="plotly_white",
        )
        st.plotly_chart(fig_short, use_container_width=True, key="compare_fig_short")

c_g3, c_g4 = st.columns(2)

with c_g3:
    # Carbon Emissions Bar
    carb_row = df_summary[df_summary["Metric"] == "Carbon Emissions (tCO₂)"]
    if not carb_row.empty:
        carbs = [
            float(carb_row["1. Rule Baseline"].values[0]),
            float(carb_row["2. Fixed MILP"].values[0]),
            float(carb_row["3. GridMind Agent"].values[0]),
        ]
        fig_carb = go.Figure(data=[
            go.Bar(
                x=["1. Rule Baseline", "2. Fixed MILP", "3. GridMind Agent"],
                y=carbs,
                marker_color=["#6B7280", "#3B82F6", "#10B981"],
                text=[f"{c:.1f} t" for c in carbs],
                textposition="auto",
            )
        ])
        fig_carb.update_layout(
            title="Carbon Footprint from Grid Purchases (tCO₂)",
            yaxis_title="Emissions (tCO₂)",
            template="plotly_white",
        )
        st.plotly_chart(fig_carb, use_container_width=True, key="compare_fig_carb")

with c_g4:
    # Unserved Critical Load Bar (VOLL)
    crit_row = df_summary[df_summary["Metric"] == "Unserved Critical Load (MWh)"]
    if not crit_row.empty:
        crits = [
            float(crit_row["1. Rule Baseline"].values[0]),
            float(crit_row["2. Fixed MILP"].values[0]),
            float(crit_row["3. GridMind Agent"].values[0]),
        ]
        fig_crit = go.Figure(data=[
            go.Bar(
                x=["1. Rule Baseline", "2. Fixed MILP", "3. GridMind Agent"],
                y=crits,
                marker_color=["#DC2626", "#10B981", "#10B981"],
                text=[f"{c:.2f} MWh" for c in crits],
                textposition="auto",
            )
        ])
        fig_crit.update_layout(
            title="Unserved Critical Customer Load (Hospital/Steel) — Target: 0",
            yaxis_title="Unserved Load (MWh)",
            template="plotly_white",
        )
        st.plotly_chart(fig_crit, use_container_width=True, key="compare_fig_crit")
