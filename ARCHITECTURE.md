# GridMind: System Architecture & Technical Specifications

> **ET AI Hackathon: Agentic Edition (Accenture × Economic Times)**  
> **Problem Statement 4: Utilities — Renewable Energy Orchestrator**  
> **Portfolio Target:** Deccan Renewables Pvt. Ltd. (Karnataka, India)  
> **Hackathon Positioning Claim:** **D2 / F3**  

---

## 1. Architectural Philosophy & Non-Negotiable Principles

GridMind is designed for mission-critical electrical utility infrastructure. In high-voltage power transmission and energy arbitrage, hallucinating non-physical megawatts or violating transformer thermal limits leads to catastrophic grid collapse.

GridMind is anchored by six non-negotiable architectural principles:

```
+---------------------------------------------------------------------------------------+
| 1. The LLM Never Computes Dispatch Numbers                                            |
|    All numeric decisions (megawatts, MWh, battery charging setpoints) originate from  |
|    a deterministic Mixed-Integer Linear Program (MILP) solver. The LLM reasons,       |
|    selects operational modes, tunes multi-objective weights, evaluates tail risk,     |
|    and explains decisions to human operators.                                         |
+---------------------------------------------------------------------------------------+
| 2. Hard Safety Rules are Code, Not AI                                                 |
|    A deterministic Python guardrail layer intercepts every candidate plan before      |
|    execution. Safety constraints are non-negotiable physical laws.                    |
+---------------------------------------------------------------------------------------+
| 3. Every Decision is Traceable                                                        |
|    Each 15-minute interval records an immutable, structured JSONL audit entry with    |
|    inputs, signals, tool calls, evaluated candidate plans, and executed setpoints.   |
+---------------------------------------------------------------------------------------+
| 4. 100% Offline Resilience (MOCK_LLM=true)                                           |
|    The system operates seamlessly without an external API. If an LLM call fails,     |
|    deterministic rule-based stand-in logic produces the exact same Pydantic shapes.   |
+---------------------------------------------------------------------------------------+
| 5. Human Oversight & Controllability                                                  |
|    High-impact actions require operator approval. Operators can pause, step, or       |
|    override any setpoint in real time.                                                |
+---------------------------------------------------------------------------------------+
| 6. Fully Config-Driven                                                                |
|    Zero magic numbers. All asset specs, tariffs, penalties, thresholds, and weights   |
|    live in config/*.yaml manifests.                                                   |
+---------------------------------------------------------------------------------------+
```

---

## 2. End-to-End Control Loop Flowchart

Every 15 minutes ($0.25 \text{ hours}$), GridMind executes an autonomous closed-loop cycle:

```mermaid
flowchart TD
    subgraph SENSING ["1. SENSING & TELEMETRY"]
        A["Karnataka Assets (740 MW Gen, 400 MWh BESS)"] --> SIM["Physical Grid Simulator (15-min Step)"]
        W["Weather Data (Open-Meteo) & Market Tariffs (IEX)"] --> FC["Multi-Quantile Forecaster (P10, P50, P90)"]
        SIM --> FC
    end

    subgraph AGENTIC ["2. AGENTIC REASONING LAYER"]
        SIM --> MON["Monitor Agent<br/>(Deterministic Signal Extraction)"]
        FC --> MON
        MON -->|Replan Required / Interval Cadence| STRAT["Strategy Agent<br/>(Tool-Calling Exploration Loop)"]
        
        STRAT -->|1. run_milp(weights, reserve_floor)| MILP["Deterministic MILP Solver (PuLP/CBC)"]
        STRAT -->|2. evaluate_risk(plan_id)| RISK["Monte Carlo Tail-Risk Evaluator"]
        STRAT -->|3. compare_plans(plan_a, plan_b)| STRAT
        MILP --> STRAT
        RISK --> STRAT
    end

    subgraph GOVERNANCE ["3. SAFETY & GOVERNANCE GATE"]
        STRAT --> GUARD{"Guardrail Validator<br/>(Deterministic Python)"}
        GUARD -->|Violated| RETRY["Strategist Error Recovery Loop<br/>(Up to 2 Attempts)"]
        RETRY --> GUARD
        GUARD -->|Persisted Failure| SAFE["Safe-Mode Heuristic Dispatch<br/>(40% Reserve Hold)"]
        GUARD -->|Approved| APPR{"Operator Approval Gate"}
        SAFE --> APPR
        APPR -->|Approved / Auto| EXEC["Dispatch Executor"]
    end

    subgraph ACTUATION ["4. ACTUATION & OPERATOR AUDIT"]
        EXEC --> SIM
        EXEC --> LOG["Structured JSONL Decision Logger"]
        STRAT --> EXP["Explainer Agent<br/>(Shift Briefing Generation)"]
        EXP --> UI["Streamlit Control Room Dashboard"]
        LOG --> UI
    end

    classDef agent fill:#ECFDF5,stroke:#10B981,stroke-width:2px;
    classDef safety fill:#FEF2F2,stroke:#EF4444,stroke-width:2px;
    classDef opt fill:#EFF6FF,stroke:#3B82F6,stroke-width:2px;
    class MON,STRAT,EXP agent;
    class GUARD,RETRY,SAFE safety;
    class MILP,RISK opt;
```

---

## 3. System Components: Responsibilities & Implementation

| Component | Responsibility | Inputs | Outputs | Implementation Type |
| :--- | :--- | :--- | :--- | :---: |
| **Physical Simulator** (`sim/simulator.py`) | Advances asset states by 15 min; tracks battery SoC, line flows, curtailment, and contract settlements. | DispatchAction | GridState, IntervalKPIs | **Deterministic** |
| **Event Engine** (`sim/events.py`) | Injects clouds, price spikes, line deratings, outages, and storm alerts. | Raw baseline series, Event specs | Perturbed actuals, ActiveEvents | **Deterministic** |
| **Forecaster** (`forecast/forecaster.py`) | Rolling 32-interval forecast with P10/P50/P90 cones. | GridState, Historical dataset | ForecastResult | **Deterministic** |
| **Monitor Agent** (`agents/monitor.py`) | Calculates telemetry deltas; summarizes anomalies when severity $\ge$ medium. | GridState, ForecastResult | MonitorReport (Pydantic) | **Hybrid (Code + LLM)** |
| **Strategy Agent** (`agents/strategist.py`) | Tool-calling loop; selects mode, evaluates candidates, balances trade-offs. | MonitorReport, ForecastResult | StrategyDecision (Pydantic) | **Hybrid (Code + LLM)** |
| **MILP Optimizer** (`optimize/milp.py`) | Solves rolling 8h dispatch minimizing multi-objective cost. | GridState, Forecast, Weights, Floor | DispatchPlan (feasible setpoints)| **Deterministic (PuLP)** |
| **Risk Evaluator** (`optimize/risk.py`) | Evaluates candidate plan against $N$ Monte Carlo weather/price scenarios. | DispatchPlan, ForecastResult | PlanRiskMetrics | **Deterministic** |
| **Guardrails** (`guard/guardrails.py`) | Hard safety gatekeeper checking 7 physical interlocks before actuation. | DispatchPlan, GridState | ValidationResult (Passed/Rejected)| **Deterministic** |
| **Dispatch Executor** (`executor.py`) | Actuation bridge applying first-interval commands to physical assets. | DispatchAction | Updated GridState | **Deterministic** |
| **Explainer Agent** (`agents/explainer.py`) | Generates operator shift briefing ($\le 15$ word headline, motives, pivot triggers). | Decision, Action, GridState | Explanation (Pydantic) | **Hybrid (Code + LLM)** |
| **Decision Logger** (`logging_utils.py`) | Records immutable JSONL audit entries for compliance and replay. | Full interval state & decisions | `logs/run_<id>.jsonl` | **Deterministic** |
| **Metrics Engine** (`metrics.py`) | Accumulates financial, carbon, battery cycle, and reliability KPIs. | Interval telemetry & actions | PortfolioMetrics | **Deterministic** |

---

## 4. Where and How the LLM is Used

### 4.1 Strict LLM Scope
GridMind utilizes **Google Gemini** (default: `gemini-2.5-flash`, configurable via `GEMINI_MODEL`) wrapped inside [`llm_client.py`](gridmind/agents/llm_client.py). The LLM is restricted exclusively to high-level reasoning:
1. **Telemetry Synthesis (Monitor):** Translating raw percentage divergences across 10 assets into a 2-sentence situational briefing.
2. **Strategy Formation (Strategist):** Selecting an operational mode and tuning objective weight vectors ($w \in [0, 5]$) for the MILP solver based on operational context.
3. **Candidate Plan Comparison (Strategist):** Articulating explicit trade-off statements between candidate plans evaluated by tools.
4. **Shift Briefings (Explainer):** Explaining executed dispatches, underlying rationale, accepted trade-offs, and pivot conditions to human dispatchers.

### 4.2 Why the LLM Never Computes Numbers
- **Zero Hallucination Tolerance:** Transformers cannot guarantee exact Kirchhoff power flow conservation or linear battery efficiency losses.
- **Physical Feasibility:** Only a formal mathematical solver (MILP) can guarantee that battery C-rates, transmission thermal capacities, and customer contracts are strictly satisfied simultaneously.
- **Sub-Second Determinism:** MILP solves in $\sim 40\text{ ms}$, ensuring deterministic performance without network jitter.

### 4.3 Bounded Tool-Calling Loop
The Strategy Agent operates within a strictly bounded loop (maximum 6 tool calls per cycle):
- `run_milp(weights, reserve_floor, terminal_soc_target)`: Calls the deterministic solver to generate a candidate plan.
- `evaluate_risk(plan_id)`: Simulates the candidate plan against 20 randomized Monte Carlo weather/price scenarios.
- `compare_plans(plan_id_a, plan_id_b)`: Compares expected costs, tail risk ($P_{90}$), and contract shortfall risk.

### 4.4 Schemas & Pydantic Validation
Every LLM call is validated against strict Pydantic v2 schemas defined in [`agents/schemas.py`](gridmind/agents/schemas.py). Any schema mismatch triggers an automatic single-retry correction before falling back to deterministic mock logic.

---

## 5. Optimality Criteria & Multi-Objective Formulation

### 5.1 Hard Constraints vs Weighted Objectives
```
Total Formulation:
MINIMIZE:  w_cost * Cost + w_carbon * Carbon + w_curt * Curtailment + 
           w_degr * Degradation + w_reliab * Shortfall + VOLL_penalty * Unserved_Critical

SUBJECT TO (Hard Physical Constraints):
  1. Power Balance: Generation(net) + BESS_Discharge + Import == Demand(net) + BESS_Charge + Export
  2. BESS Mutex: u[b, t] in {0, 1}; Charge <= P_max * u; Discharge <= P_max * (1 - u)
  3. Grid Mutex: y[t] in {0, 1}; Import <= Imp_limit * y; Export <= Exp_limit * (1 - y)
  4. Battery Dynamic SoC: SoC[t] == SoC[t-1] + (Charge * eta_c - Discharge / eta_d) * dt
  5. Physical SoC Bounds: SoC_min <= SoC[t] <= SoC_max
  6. Critical Load Protection: Critical_Fraction * Demand <= Served_Load (Unserved_Critical == 0)
  7. Demand Response: DR[c, t] <= DR_max[c]
```

### 5.2 Operational Modes & Weight Profiles
The Strategy Agent dynamically shifts the weight vector $w$ based on environmental stress:

| Operational Mode | Objective Focus | Cost ($w_1$) | Carbon ($w_2$) | Curtailment ($w_3$) | Degradation ($w_4$) | Reliability ($w_5$) | Reserve Floor |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`green`** | Maximize self-consumption, minimize carbon | 1.0 | **2.5** | **3.0** | 0.8 | **3.0** | 15% |
| **`economic`** | Arbitrage profits, charge low, sell high | **3.5** | 0.8 | 1.0 | 1.2 | 2.5 | 10% |
| **`reliability_first`** | Guarantee customer contract schedules | 1.0 | 0.5 | 0.5 | 0.5 | **5.0** | 35% |
| **`storm_preparation`**| Defensive holding ahead of severe front | 0.5 | 0.5 | 0.5 | 0.5 | **5.0** | **60%** |
| **`outage_recovery`** | Compensate for lost generator or BESS | 1.2 | 1.0 | 1.0 | 0.5 | **4.5** | 35% |
| **`congestion_mgmt`** | Avoid line penalties, localized dispatch | 2.0 | 1.0 | **3.0** | 0.8 | 3.5 | 20% |

### 5.3 Conflict Resolution Hierarchy
When objectives conflict, GridMind enforces a strict mathematical penalty hierarchy:
$$\text{VOLL (Lost Load)} = ₹100,000/\text{MWh} \gg \text{Reserve Floor Slack} = ₹25,000/\text{MWh} \gg \text{Contract Shortfall} = ₹15,000/\text{MWh} \gg \text{Max Market Price} = ₹10,000/\text{MWh}$$

1. **Hospital / Steel Critical Load Blackout:** Unserved critical load penalty ($\ge ₹100,000/\text{MWh}$) strictly dominates all other terms. The solver will discharge battery reserves to 0% rather than shed critical load.
2. **Contract Shortfall vs Battery Reserve:** Holding defensive storm reserve ($₹25,000/\text{MWh}$) dominates non-critical contract shortfall ($₹15,000/\text{MWh}$). The portfolio accepts industrial shortfall penalties to maintain defensive reserves when a cyclone is incoming.
3. **Arbitrage vs Battery Degradation:** BESS throughput degradation ($₹500/\text{MWh}$) ensures batteries only cycle when market price spreads exceed round-trip efficiency losses ($> ₹600/\text{MWh}$).

---

## 6. Uncertainty Handling & Rolling Model Predictive Control (MPC)

GridMind manages high renewable volatility through a 3-tier uncertainty architecture:
1. **Multi-Quantile Forecasting:** Every interval, the Forecaster projects $P_{10}$ (pessimistic), $P_{50}$ (expected), and $P_{90}$ (optimistic) timeseries cones across all 10 assets for the next 32 intervals (8 hours).
2. **Monte Carlo Scenario Evaluation:** Candidate plans are evaluated against 20 perturbed scenarios to estimate expected cost, $P_{90}$ tail risk, and shortfall probability ($P_{\text{shortfall}}$).
3. **Rolling Horizon Execution (MPC):** While the MILP optimizes an 8-hour horizon (32 intervals), **only the first interval's action ($t=0$) is executed**. At $t=1$, new telemetry and weather observations arrive, and the problem is re-solved with updated initial states. This prevents error accumulation.

---

## 7. Fault Tolerance, Safety Guardrails & Fallbacks

```
                               CANDIDATE DISPATCH PLAN
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │    Hard Safety Guardrail Layer  │
                         │         (guardrails.py)         │
                         └─────────────────────────────────┘
                                     │            │
                           Passed    │            │ Violated
                                     ▼            ▼
                         ┌───────────────┐   ┌───────────────────────────────┐
                         │   EXECUTE     │   │ Strategist Recovery Attempt   │
                         │ (Executor.py) │   │ (Reinforce w_reliab, floor)   │
                         └───────────────┘   └───────────────────────────────┘
                                                          │
                                                Failed 2x │
                                                          ▼
                                             ┌───────────────────────────────┐
                                             │      Safe-Mode Dispatch       │
                                             │ (Hold 40% Reserve, Export=0)  │
                                             └───────────────────────────────┘
```

1. **LLM Failure / Timeout:** Automatic catch $\rightarrow$ Instant fallback to `mock_logic.py` with zero latency hit.
2. **Invalid JSON / Schema Mismatch:** Automatic one-time prompt repair $\rightarrow$ Fallback to mock logic if uncorrected.
3. **MILP Infeasibility:** Mathematical slack variables on non-critical shortfall and VOLL guarantee the solver always finds a feasible physical point.
4. **Guardrail Violation:** Plan is rejected; specific violation feedback is fed back to the Strategist to re-solve with higher reliability weighting and adjusted reserve floors (up to 2 retries).
5. **Persistent Guardrail Failure:** If retries are exhausted, the orchestrator bypasses the optimizer and executes `safe_mode_dispatch()`: holding $\ge 40\%$ battery reserve, zero grid exports, and serving critical loads directly.

---

## 8. Responsible AI & Governance

- **Human-in-the-Loop:** High-impact dispatch decisions (e.g. voluntary demand response curtailment or emergency reserve releases) require operator approval in the dashboard when manual approval mode is engaged.
- **Operator Overrides:** Shift Dispatch Managers can override any setpoint at any interval. Overrides are timestamped and logged with user rationale.
- **Audit Compliance:** Every decision, telemetry reading, candidate plan comparison, and validation verdict is logged to structured JSONL files (`logs/run_<id>.jsonl`) for regulatory compliance.
- **No Private Data:** GridMind handles purely operational and technical parameters (MW, MWh, ₹, timestamps). No personal data (PII) is processed or transmitted.

---

## 9. Scalability & Production Roadmap

- **Linear Variable Growth:** PuLP MILP formulation grows linearly $\mathcal{O}(T \times (N_{\text{farms}} + N_{\text{bess}} + N_{\text{consumers}}))$. Managing 50 farms and 20 batteries requires $\sim 6,400$ variables, easily solved in $< 250\text{ ms}$ with open-source CBC.
- **Solver Pluggability:** Thin abstraction layer allows instant swap to commercial solvers (Gurobi, COPT, HiGHS) with a single configuration flag.
- **Modular Data Connectors:** The Forecaster interface accepts real-time SCADA/EMS telemetry (Modbus, OPC-UA, MQTT) and live IEX API feeds without altering agent logic.

---

## 10. Hackathon Positioning Self-Assessment: D2 / F3

GridMind self-assesses strictly and defensibly at **D2 / F3** on the hackathon 3×3 capability matrix:

| Axis | Claim | Requirement | Verifiable Proof in GridMind |
| :---: | :---: | :--- | :--- |
| **Data (D)** | **D2** | Structured/textual inputs, high *demonstrable* reliability. Zero tolerance for ungrounded actions. | • **0 hard safety violations** across 2,880 consecutive simulation intervals.<br/>• **0 unserved critical load** across all simulated days.<br/>• Deterministic guardrail pre-execution verification gate.<br/>• Complete JSONL audit trail for every 15-minute decision. |
| **Forecasting & Sim (F)** | **F3** | Simulate situation over time accounting for variations in inputs. Rolling horizons and multi-scenario comparison. | • Rolling 32-interval (8-hour) horizon simulation updated every 15 minutes.<br/>• Evaluation under randomized Poisson disturbance arrivals (clouds, storms, trips, tariff spikes).<br/>• Multi-season testing across Summer and Monsoon meteorological regimes.<br/>• Multi-quantile forecast cones (P10, P50, P90) driving Monte Carlo tail-risk evaluations. |

### Why We Do Not Claim D3 or F4
- **No Multimodal Sensory Data (D3):** GridMind processes structured numerical and textual telemetry (MW, MWh, ₹, wind speeds, irradiance). We do not process live satellite imagery or computer vision, and claiming D3 would be an overclaim.
- **No Fully Stochastic Autonomous World-Model (F4):** GridMind relies on deterministic physics and rolling MILP optimization rather than unconstrained neural simulation. In electric power grids, mathematical certifiability is mandatory.
