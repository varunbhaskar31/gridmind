"""System Architecture & Hackathon Positioning Documentation.

Details GridMind's architectural principles, control flow,
Mermaid diagram, and D2 / F3 hackathon positioning claim.
"""

import streamlit as st

st.set_page_config(page_title="Architecture — GridMind", page_icon="🏗️", layout="wide")

st.title("🏗️ System Architecture & Hackathon Positioning")
st.markdown("Deccan Renewables Pvt. Ltd. — ET AI Hackathon: Agentic Edition (Accenture × Economic Times).")

# 1. Non-Negotiable Design Principles
st.subheader("1. Non-Negotiable Architectural Principles")

c1, c2 = st.columns(2)
with c1:
    st.markdown(
        """
        - **1. The LLM Never Computes Dispatch Numbers:**  
          All numeric flows, state-of-charge trajectories, and megawatts are solved by a deterministic Mixed-Integer Linear Program (MILP) solver. The LLM reasons about situations, selects operational modes, tunes multi-objective weights, evaluates tail risks, and briefs operators.
        - **2. Hard Safety Rules are Code, Not AI:**  
          A deterministic Python guardrail layer (`guardrails.py`) validates every candidate plan before execution. Zero simultaneous charge/discharge, zero simultaneous import/export, zero line limit exceedances, zero critical load shedding.
        - **3. Every Decision is Traceable:**  
          Every 15 minutes, a structured audit entry is appended to an immutable JSONL log, containing telemetry, anomaly signals, candidate plans, trade-off statements, guardrail checks, and executed setpoints.
        """
    )

with c2:
    st.markdown(
        """
        - **4. 100% Offline Resilience (MOCK_LLM=true):**  
          The system never crashes due to API keys, rate limits, or connectivity loss. If the LLM is unavailable, rule-table stand-ins (`mock_logic.py`) produce the exact same Pydantic shapes seamlessly.
        - **5. Human Oversight & Controllability:**  
          Shift dispatch managers can review briefings, approve high-impact actions, or provide direct manual setpoint overrides at any interval.
        - **6. Config-Driven Design:**  
          Zero magic numbers in code. All farm coordinates, efficiencies, battery C-rates, penalty tariffs, carbon prices, and agent thresholds are declared in clean YAML manifests (`config/*.yaml`).
        """
    )

st.markdown("---")

# 2. End-to-End Architectural Flow Diagram (Mermaid)
st.subheader("2. End-to-End Control Flow Architecture")

mermaid_code = """
flowchart TD
    subgraph SENSING ["1. SENSING & TELEMETRY"]
        A["Karnataka Solar & Wind Farms (740 MW)"] --> S["Physical Grid Simulator (15-min)"]
        B["BESS Storage Assets (100 MW / 400 MWh)"] --> S
        C["Industrial Consumers (Steel, Data Center)"] --> S
        D["Open-Meteo Weather & IEX Tariffs"] --> F["Multi-Quantile Forecaster (P10, P50, P90)"]
        S --> F
    end

    subgraph AGENTIC ["2. AGENTIC REASONING LAYER"]
        S --> M["Monitor Agent<br/>(Telemetry Anomaly Scoring)"]
        F --> M
        M --> ST["Strategy Agent<br/>(Operational Mode & Tool Loops)"]
        ST -->|run_milp| O["Deterministic MILP Solver (PuLP)"]
        ST -->|evaluate_risk| R["Monte Carlo Risk Evaluator"]
        O --> ST
        R --> ST
    end

    subgraph GOVERNANCE ["3. SAFETY & GOVERNANCE GATE"]
        ST --> G{"Hard-Constraint Guardrail<br/>(Deterministic Code)"}
        G -->|Violated| REC["Strategist Recovery / Safe Mode"]
        REC --> G
        G -->|Approved| AP{"Operator Approval Gate"}
        AP -->|Approved / Auto| EX["Dispatch Executor"]
    end

    subgraph ACTUATION ["4. ACTUATION & OPERATOR AUDIT"]
        EX --> S
        EX --> L["Immutable JSONL Decision Logger"]
        ST --> EXP["Explainer Agent<br/>(Operator Briefing)"]
        EXP --> UI["Streamlit Control Room"]
        L --> UI
    end

    classDef agent fill:#ECFDF5,stroke:#10B981,stroke-width:2px;
    classDef safety fill:#FEF2F2,stroke:#EF4444,stroke-width:2px;
    classDef opt fill:#EFF6FF,stroke:#3B82F6,stroke-width:2px;
    class M,ST,EXP agent;
    class G,REC safety;
    class O,R opt;
"""

st.markdown(f"```mermaid\n{mermaid_code}\n```")

st.markdown("---")

# 3. Hackathon 3x3 Grid Positioning Claim
st.subheader("3. Hackathon 3×3 Grid Positioning: D2 / F3")

c_claim1, c_claim2 = st.columns(2)

with c_claim1:
    st.info(
        """
        ### 🎯 D2: High Demonstrable Reliability
        - **Strict Scope:** Structured/textual telemetry, price forecasts, and event announcements.
        - **Verifiable Proof:**
          - 0 hard safety violations across 30 simulated days (2,880 consecutive intervals).
          - 0 unserved critical customer load (100% protection of hospitals and heavy industry).
          - Guardrail layer mathematically proves feasibility before any actuator command is transmitted.
        """
    )

with c_claim2:
    st.info(
        """
        ### 🌪️ F3: Rolling Uncertainty Simulation
        - **Strict Scope:** Simulates physical situation over rolling horizons accounting for stochastic variations in inputs.
        - **Verifiable Proof:**
          - Rolling 32-interval forecast horizon updated every 15 minutes with P10/P50/P90 cones.
          - Multi-day simulation across summer and monsoon seasons under randomized Poisson disturbance arrivals (cloud cover, severe storms, forced asset outages, tariff spikes, transmission derating).
        """
    )

st.warning("⚠️ **Explicit Boundary:** GridMind strictly claims **D2 / F3**. We deliberately do not claim multimodal sensing (D3/F4) or uncontrolled end-to-end neural actuation. Reliability in critical utility infrastructure requires deterministic mathematical guarantees.")
