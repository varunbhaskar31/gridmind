# GridMind: Autonomous Renewable Energy Portfolio Orchestrator

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PuLP MILP](https://img.shields.io/badge/optimizer-PuLP%20MILP%20(CBC)-green.svg)](https://coin-or.github.io/pulp/)
[![Streamlit UI](https://img.shields.io/badge/dashboard-Streamlit-red.svg)](https://streamlit.io/)
[![Hackathon Claim](https://img.shields.io/badge/Claim-D2%20%7C%20F3-purple.svg)](#hackathon-positioning-claim-d2--f3)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **ET AI Hackathon: Agentic Edition (Accenture × Economic Times)**  
> **Problem Statement 4: Utilities — Renewable Energy Orchestrator**  
> **Fictional Client:** Deccan Renewables Pvt. Ltd. (Karnataka, India)  
> **Primary Persona:** Shift Dispatch Manager (Control Room Desk)  
> **Secondary Persona:** Head of Portfolio Operations  

---

## 1. Executive Summary

Managing a complex, utility-scale renewable portfolio every 15 minutes is an operational nightmare. Control room operators must continuously balance intermittent solar and wind outputs, transmission corridor congestion, fluctuating Indian Energy Exchange (IEX) market tariffs, battery health, and committed Round-The-Clock (RTC) delivery contracts with severe shortfall penalties.

**GridMind** is an autonomous, agentic energy orchestrator built specifically for Deccan Renewables Pvt. Ltd. in Karnataka, India. Managing **740 MW of generation** (5 solar parks, 3 wind farms), **100 MW / 400 MWh of battery energy storage**, and **300 MW of industrial offtakers** (Steel, Data Center, Textile, Cement), GridMind unites autonomous AI reasoning with deterministic mathematical optimization:
- **Autonomous Multi-Agent Layer (Google Gemini / Mock):** Monitors real-time telemetry anomalies, dynamically shifts strategic objectives, compares candidate plans with Monte Carlo tail risk, and generates natural-language briefings.
- **Deterministic MILP Optimizer (PuLP / CBC):** Solves exact, physically feasible dispatch setpoints across a 32-interval (8-hour) rolling horizon. The LLM **never** computes dispatch numbers.
- **Hard Safety Guardrail Layer:** Intercepts every candidate plan before execution, guaranteeing **zero** simultaneous buy/sell, **zero** simultaneous charge/discharge, and **zero** critical customer load shedding.

### Headline Results
Across a 24-hour comparative benchmark against traditional utility operation:
- **44.5% Net Operating Cost Reduction** (₹18.2 Million daily savings).
- **88.7% Contract Shortfall Reduction** (from 1,312.4 MWh down to 148.4 MWh).
- **100% Critical Customer Load Protection** (0.000 MWh shed vs 43.2 MWh shed in baseline).
- **Zero Hard-Constraint Violations** across a continuous **30-day reliability stress-test (2,880 intervals)** with 21 injected severe disturbances.

---

## 2. Quickstart: One-Command Local Launch

GridMind requires **no cloud dependencies, no Docker containers, and no database setup**. It runs completely locally with bundled solvers.

### 2.1 Clone and Setup Environment

```bash
# 1. Clone repository
git clone https://github.com/varunbhaskar/gridmind.git
cd gridmind

# 2. Create and activate virtual environment (Python 3.11+)
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment configuration
cp .env.example .env
```

### 2.2 Launch Interactive Dashboard

```bash
# Launch with one single command (runs locally on http://localhost:8501)
./scripts/run_demo.sh
```

Or run Streamlit directly:
```bash
streamlit run app/streamlit_app.py
```

### 2.3 Running Fully Offline (Mock Mode)
GridMind is designed to **never crash** due to missing API keys or network latency. If `GEMINI_API_KEY` is omitted or `MOCK_LLM=true` is set in `.env`, the agents automatically engage deterministic rule-based stand-in logic (`mock_logic.py`) producing identical Pydantic JSON shapes.

To enable live Google Gemini calls:
```bash
# In .env:
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
MOCK_LLM=false
```

---

## 3. Benchmark Proof & Business Impact

Under identical summer meteorological conditions (Season A) and injected disturbances (cloud cover over Pavagada, transmission line derating, and peak evening IEX tariff spikes):

| Operational Metric | 1. Rule Baseline | 2. Fixed MILP | 3. GridMind Agent | Agent vs Baseline |
| :--- | :---: | :---: | :---: | :---: |
| **Total Net Cost (₹)** | **₹40,900,584** | ₹22,770,752 | **₹22,686,441** | **-44.5% (-₹18.2M)** |
| **Grid Purchase Cost (₹)** | ₹13,908,012 | ₹13,343,759 | ₹13,190,232 | **-5.2%** |
| **Export Revenue (₹)** | ₹0 | ₹370,138 | ₹188,489 | **+₹188k** |
| **Contract Shortfall (MWh)** | 1,312.40 | 154.21 | **148.36** | **-88.7%** |
| **Shortfall Penalty (₹)** | ₹19,686,008 | ₹2,313,176 | **₹2,225,422** | **-88.7%** |
| **Unserved Critical Load (MWh)** | **43.247 MWh** | 0.000 MWh | **0.000 MWh** | **100% Protected (0 VOLL)** |
| **Carbon Emissions (tCO₂)** | 1,874.5 | 1,803.2 | **1,769.0** | **-5.6%** |
| **Renewable Utilization (%)** | 100.0% | 100.0% | **100.0%** | **0.0% Curtailment** |
| **Battery Throughput (MWh)** | 340.1 | 740.7 | 748.8 | Optimized Cycles |
| **Hard Safety Violations** | 0 | 0 | **0** | **Verified 0** |

---

## 4. Multi-Day Reliability Stress-Test (D2 Proof)

To verify the **D2 (High Demonstrable Reliability)** claim, GridMind was subjected to a continuous **30-day simulation suite (2,880 consecutive 15-minute intervals)** with 21 injected stochastic events (cloud banks, price spikes, transmission limits, inverter trips, storm alerts):

```bash
# Run the 30-day reliability stress test:
python scripts/run_reliability.py
```

### Verified Audit Outcome
- **Total Simulated Intervals:** 2,880 (30 days across Summer and Monsoon seasons)
- **Stochastic Disturbances Injected:** 21 events
- **Hard Safety Constraint Violations:** **0** (Target: 0)
- **Unserved Critical Customer Load:** **0.000000 MWh** (Target: 0)
- **Mean Daily Operating Cost:** ₹14,447,206
- **Mean Renewable Energy Utilization:** 100.0%
- **Audit Artifact:** [`data/processed/reliability_summary.json`](data/processed/reliability_summary.json)

---

## 5. Portfolio Topology & Assumptions

All asset configurations, pricing tariffs, and penalty thresholds are declared in [`config/*.yaml`](config/) with zero hardcoded magic numbers.

### 5.1 Generation Assets (Karnataka, India)
| ID | Asset Name | Location | Type | Capacity | Technical Assumptions |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **S1** | Pavagada Solar Park | 14.10°N, 77.28°E | Solar PV | 150 MW | PR: 0.80, Temp Coeff: -0.4%/°C |
| **S2** | Tumakuru Solar Farm | 13.34°N, 77.10°E | Solar PV | 120 MW | PR: 0.80, Temp Coeff: -0.4%/°C |
| **S3** | Koppal Solar Farm | 15.35°N, 76.15°E | Solar PV | 100 MW | PR: 0.80, Temp Coeff: -0.4%/°C |
| **S4** | Raichur Solar Farm | 16.20°N, 77.35°E | Solar PV | 80 MW | PR: 0.80, Temp Coeff: -0.4%/°C |
| **S5** | Kalaburagi Solar Farm | 17.33°N, 76.83°E | Solar PV | 50 MW | PR: 0.80, Temp Coeff: -0.4%/°C |
| **W1** | Chitradurga Wind Park | 14.23°N, 76.40°E | Wind Turbine | 100 MW | Cut-in: 3 m/s, Rated: 12 m/s, Cut-out: 25 m/s |
| **W2** | Gadag Wind Farm | 15.43°N, 75.63°E | Wind Turbine | 80 MW | Cut-in: 3 m/s, Rated: 12 m/s, Cut-out: 25 m/s |
| **W3** | Harapanahalli Wind Farm| 14.79°N, 75.99°E | Wind Turbine | 60 MW | Cut-in: 3 m/s, Rated: 12 m/s, Cut-out: 25 m/s |

### 5.2 Battery Energy Storage Systems (BESS)
| ID | Power Rating | Energy Capacity | Charge / Disch. Eff. | Operating SoC Range | Cell Degradation Cost |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **B1** | 60 MW | 240 MWh (4h) | 95% / 95% (90.25% round-trip) | 10% – 95% | ₹500 / MWh throughput |
| **B2** | 40 MW | 160 MWh (4h) | 95% / 95% (90.25% round-trip) | 10% – 95% | ₹500 / MWh throughput |

### 5.3 Industrial RTC Customers
| ID | Customer | Base Load | Critical Fraction (Never Shed) | Max Demand Response | DR Incentive Rate |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **C1** | Bellary Steel Plant | 120 MW | 60% (72.0 MW hard floor) | 25 MW | ₹3,000 / MWh |
| **C2** | Bengaluru Data Centre | 60 MW | 90% (54.0 MW hard floor) | 5 MW | ₹6,000 / MWh |
| **C3** | Davanagere Textile Mill | 50 MW | 40% (20.0 MW hard floor) | 15 MW | ₹2,500 / MWh |
| **C4** | Bagalkot Cement Plant | 70 MW | 50% (35.0 MW hard floor) | 20 MW | ₹2,800 / MWh |

### 5.4 Grid & Tariff Parameters
- **Grid Evacuation Limits:** Max Import 150 MW | Max Export 200 MW.
- **Contract Shortfall Penalty:** ₹15,000 / MWh.
- **Value of Lost Load (VOLL):** ₹100,000 / MWh (mathematical slack variable, guaranteed zero in planned dispatch).
- **Grid Carbon Emission Factor:** 0.71 tCO₂/MWh (*Source: Central Electricity Authority CEA CO₂ Baseline Database for Indian Grid*).
- **Carbon Shadow Price:** ₹1,500 / tCO₂.

---

## 6. How to Ingest Custom Datasets

### 6.1 Building Processed Seasons from Open-Meteo
```bash
# Rebuild Season A (Summer: April 14–20, 2025):
python -m gridmind.data_prep.build_dataset --season A

# Rebuild Season B (Monsoon: July 14–20, 2025):
python -m gridmind.data_prep.build_dataset --season B
```

### 6.2 Custom IEX Price & Customer Load CSV Upload
You can upload real market tariff CSVs directly in the dashboard on **Page 7: Data & Assumptions**, or drop CSVs into `data/raw/`. Required format:
```csv
timestamp,price_inr_per_mwh
2025-04-14 00:00:00,3450.50
2025-04-14 00:15:00,3210.00
...
```

---

## 7. Hackathon Positioning Claim: D2 / F3

GridMind explicitly and responsibly self-assesses at **D2 / F3** on the 3×3 capability grid:
- **D2 (Structured/Textual Inputs, High Demonstrable Reliability):** Telemetry, forecasts, and announcements are processed via structured Pydantic schemas. High reliability is proven mathematically by a deterministic pre-execution guardrail layer that recorded **zero hard safety violations across 2,880 simulated intervals**.
- **F3 (Rolling Uncertainty Simulation):** Simulates dynamic portfolio reality over rolling 32-interval horizons across summer and monsoon regimes under randomized Poisson disturbance arrivals and multi-quantile forecast uncertainty cones (P10, P50, P90).

*Explicit boundary: GridMind does not claim multimodal vision sensing (D3) or ungrounded generative control.*

---

## 8. Verification & Test Suite

The entire codebase is verified by 57 comprehensive unit and integration tests:

```bash
# Run full test suite:
pytest tests/ -v
```

```text
tests/test_phase1.py ............. [14 passed]  # Conversions, Solar & Wind Physics
tests/test_phase2.py .........     [ 9 passed]  # Simulator, Events, Forecaster Cones
tests/test_phase3.py .............. [14 passed]  # MILP Solver, Risk, Guardrail Gates
tests/test_phase4.py ...........   [11 passed]  # Monitor, Strategist, Explainer, Mock
tests/test_phase5.py .........     [ 9 passed]  # Orchestrator, Metrics, Comparison
============================= 57 passed in 14.78s =============================
```

---

## 9. Project Structure

```
gridmind/
├── README.md                  # Executive overview, quickstart, assumptions, benchmark proof
├── ARCHITECTURE.md            # In-depth architectural design, control flow, responsible AI
├── requirements.txt           # Pinned production dependencies
├── .env.example               # Environment template (Gemini API key & Mock toggles)
├── config/                    # All asset and market specifications
│   ├── assets.yaml            # Solar, wind, BESS, consumer specs, grid limits
│   ├── market.yaml            # Tariffs, penalties, VOLL, carbon factor
│   ├── agent.yaml             # Anomaly thresholds, operational modes, default weights
│   └── scenarios.yaml         # Preset demo event scripts
├── data/
│   ├── raw/                   # Cached weather JSON, historical price series
│   └── processed/             # 15-minute timeseries datasets (Season A, Season B)
├── gridmind/
│   ├── data_prep/             # Weather fetching, physical conversion curves, price generator
│   ├── sim/                   # Physical 15-min simulator, state models, event injector
│   ├── forecast/              # Multi-quantile forecaster (P10, P50, P90 cones)
│   ├── optimize/              # Rolling-horizon PuLP MILP solver, risk evaluation, heuristics
│   ├── guard/                 # Hard-constraint pre-execution safety guardrail gatekeeper
│   ├── agents/                # Monitor, Strategist, Explainer agents, schemas, mock logic
│   ├── orchestrator.py        # 15-minute rolling control loop
│   ├── executor.py            # Defensive actuation bridge to simulator
│   ├── metrics.py             # Comprehensive KPI calculation engine
│   ├── logging_utils.py       # Structured JSONL decision audit logger
│   └── compare.py             # 3-way strategy comparison benchmark runner
├── app/                       # 8-Page Interactive Streamlit Control Room Dashboard
│   ├── streamlit_app.py       # Main dashboard entrypoint & Control Room home
│   ├── shared.py              # Persistent session state, preset scenarios, Plotly charts
│   └── pages/                 # Subpages: Event Injector, Reasoning, Logs, Benchmark, Map...
├── scripts/
│   ├── run_demo.sh            # One-command demo launcher
│   ├── run_reliability.py     # 30-day reliability stress-test suite
│   ├── run_phase4_demo.py     # Terminal multi-agent intelligence demonstration
│   └── run_phase5_compare.py  # 3-way strategy comparison benchmark script
└── tests/                     # 57 passing unit and integration tests across 5 phases
```

---

## 10. License
Developed for the **ET AI Hackathon: Agentic Edition**. Distributed under the MIT License.
