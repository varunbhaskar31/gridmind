"""Agent Reasoning & Decision Explainability Inspector.

Provides granular visibility into how GridMind's autonomous agents reason:
- How objective weights shift dynamically across operational modes
- Trade-off evaluations across candidate plans and Monte Carlo risk cones
- Tool-calling traces (run_milp, evaluate_risk, compare_plans)
- Safety guardrail verification logs and retry recoveries
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from app.shared import MODE_COLORS, init_session_state

st.set_page_config(page_title="Agent Reasoning — GridMind", page_icon="🧠", layout="wide")
init_session_state()

history = st.session_state.step_history

st.title("🧠 Autonomous Agent Reasoning & Trade-off Trace")
st.markdown("Inspect how the **Monitor**, **Strategist**, and **Explainer** agents explore trade-offs and select mathematical weights.")

if not history:
    st.info("No simulation intervals have been executed yet. Head to the **Control Room** and click **Step (15m)** or **Run Full Day** to observe agent reasoning.")
    st.stop()

# 1. Timeline of Modes
st.subheader("1. Strategic Mode Shifts Across Time")

timeline_data = [
    {
        "Interval": h.interval_index,
        "Timestamp": h.timestamp,
        "Mode": h.decision.mode,
        "Reserve Floor (%)": h.decision.reserve_floor * 100,
        "Confidence": getattr(h.decision, "confidence", "high"),
        "Safe Mode": h.is_safe_mode,
    }
    for h in history
]
df_timeline = pd.DataFrame(timeline_data)

fig_mode = px.scatter(
    df_timeline,
    x="Interval",
    y="Mode",
    color="Mode",
    size=[10] * len(df_timeline),
    color_discrete_map=MODE_COLORS,
    title="Operational Mode Selected by Strategy Agent Across Simulated Horizon",
)
fig_mode.update_layout(template="plotly_white", yaxis=dict(categoryorder="total ascending"))
st.plotly_chart(fig_mode, use_container_width=True, key="reasoning_fig_mode")

st.markdown("---")

# 2. Dynamic Weight Shifts
st.subheader("2. Multi-Objective Weight Adaptations")
st.caption("The agent tunes mathematical weights ($w \\in [0, 5]$) passed into the deterministic MILP optimizer depending on grid stress.")

weights_data = []
for h in history:
    w = h.decision.weights
    for k, v in w.items():
        weights_data.append({
            "Interval": h.interval_index,
            "Objective": k.title(),
            "Weight": v,
        })
df_weights = pd.DataFrame(weights_data)

fig_weights = px.line(
    df_weights,
    x="Interval",
    y="Weight",
    color="Objective",
    markers=True,
    title="Objective Weights Dynamic Evolution (Cost vs Reliability vs Carbon vs Curtailment vs Degradation)",
)
fig_weights.update_layout(template="plotly_white", yaxis=dict(range=[0, 5.5]))
st.plotly_chart(fig_weights, use_container_width=True, key="reasoning_fig_weights")

st.markdown("---")

# 3. Latest Interval Candidate Plan Comparison & Trade-off Evaluation
st.subheader("3. Latest Candidate Plan Exploration & Risk Cones")
latest = history[-1]
candidates = latest.decision.candidates_considered

if candidates:
    st.markdown(f"**Interval {latest.interval_index}** evaluated **{len(candidates)} candidate dispatch plans** before committing setpoints:")
    cand_rows = [
        {
            "Plan ID": c.plan_id,
            "Expected Cost (₹)": f"₹{c.expected_cost:,.0f}",
            "Shortfall Probability": f"{c.p_shortfall*100:.1f}%",
            "Min SoC Fraction": f"{c.min_soc*100:.1f}%",
            "Reliability Weight": c.weights.get("reliability", 1.0),
            "Cost Weight": c.weights.get("cost", 1.0),
            "Status": "✅ CHOSEN" if c.plan_id == latest.decision.chosen_plan_id else "Evaluated",
        }
        for c in candidates
    ]
    st.table(pd.DataFrame(cand_rows))
    st.markdown(f"**Trade-off Statement:** *{latest.decision.tradeoff_statement}*")
    st.markdown(f"**Agent Rationale:** *{latest.decision.rationale}*")
else:
    st.write(f"Interval {latest.interval_index} ran under active strategy with plan `{latest.decision.chosen_plan_id}`.")

st.markdown("---")

# 4. Guardrail Verification & Error Recovery Audit
st.subheader("4. Deterministic Guardrail Gatekeeper Audit")
val = latest.validation
col_g1, col_g2 = st.columns([1, 2])

with col_g1:
    if val.passed:
        st.success("✅ **GUARDRAIL APPROVED**\nZero hard physical constraints violated. Action cleared for execution.")
    else:
        st.error(f"❌ **GUARDRAIL REJECTED ({val.severity.upper()})**\nAction blocked by safety code.")

with col_g2:
    if val.violations:
        st.write("**Violations Caught & Intercepted:**")
        for v in val.violations:
            st.error(f"• {v}")
    if val.warnings:
        st.write("**Safety Warnings Recorded:**")
        for w in val.warnings:
            st.warning(f"• {w}")
    if not val.violations and not val.warnings:
        st.write("All physical interlocks verified: Mutex Grid Import/Export, BESS Charge/Discharge Exclusive, Critical Load 100% Protected, Line Limits Respected.")
