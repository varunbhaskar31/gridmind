# GridMind — Tester Guide & Evaluation Checklist

**Live Testing Link:** [https://arm-affiliate-connecting-clip.trycloudflare.com](https://arm-affiliate-connecting-clip.trycloudflare.com)  
**System Under Test:** Autonomous Renewable Energy Portfolio Orchestrator (Deccan Renewables Pvt. Ltd., Karnataka, India)  
**Assets Managed:** 5 Solar Farms (500 MW), 3 Wind Farms (240 MW), 2 Battery Systems (400 MWh), 4 Industrial RTC Consumers, Grid Interconnection & IEX Market.

---

### Test Scenario 1: Basic Autonomous Dispatch (Control Room)
> **Goal:** Verify that the system executes rolling 15-minute autonomous dispatch without manual intervention.

1. **Open the Link:** Navigate to the dashboard. You will land on the **🎮 Control Room** (Interval `0`).
2. **Observe Initial State:** Note the top metrics: *Net Demand*, *Renewable Generation*, *Battery SoC*, and *Cumulative Cost*.
3. **Step Forward:** Click the **`Step (15m)`** button in the left sidebar.
   * **What to observe:**
     * The simulation advances to the next 15-minute interval.
     * The **Operational Mode** indicator updates (e.g., `COST_MIN` or `NORMAL`).
     * The **Decision Explanation** card explains in plain English why the agent chose its storage, grid, and curtailment actions.
4. **Advance Multiple Intervals:** Click **`Run 10 Int`** to simulate 2.5 hours of operations automatically.
5. **Inspect the 3 Main Visualizations:**
   * **Tab 1 (⚡ 15-Min Power Balance):** Check that Solar + Wind + Battery Discharge + Grid Import precisely matches total customer demand.
   * **Tab 2 (🔋 Battery State of Charge):** Verify that battery levels (B1 & B2) stay safely above the red dashed line (**Mandatory Reserve Floor**).
   * **Tab 3 (📈 Electricity Tariff & Forecast):** View actual IEX spot prices alongside the rolling P10–P90 uncertainty forecast cone.

---

### Test Scenario 2: Injecting Disruptions & Watching the AI Adapt
> **Goal:** Test how the agent responds dynamically when severe disturbances hit the grid.

1. In the left sidebar, click on **`2 ⚡ Event Injector`**.
2. Under **"Preset Event Scenarios"**, choose one of the following:
   * **Cloud Cover at Pavagada:** Sudden 60% loss of solar generation.
   * **Transmission Line Limit:** Grid export capacity reduced from 200 MW to 80 MW due to substation line maintenance.
   * **IEX Price Spike:** Market buy price spikes to ₹9,800/MWh.
3. Click the red button: **`Inject Event into Simulator`**. A confirmation badge will confirm the event is queued.
4. Return to the **`🎮 Control Room`** (via sidebar navigation) and click **`Step (15m)`** repeatedly.
   * **What to observe:**
     * The **Detected Disturbances** panel highlights the active disruption.
     * The agent automatically switches operational mode (e.g. from `COST_MIN` to `RELIABILITY_FIRST` or `STORAGE_CONSERVE`).
     * Watch the battery discharge and demand response ramp up to protect critical customer loads without violating line limits.

---

### Test Scenario 3: Agent Reasoning & Objective Weight Tuning
> **Goal:** Confirm that the agent tunes mathematical weights and explores candidate plans rather than hallucinating numbers.

1. In the sidebar, navigate to **`3 🧠 Agent Reasoning`**.
2. **Mode Timeline Chart:** Review how the agent transitioned between operational modes across the day.
3. **Multi-Objective Weight Evolution:** Observe how the mathematical weights ($w_{\text{cost}}, w_{\text{rel}}, w_{\text{deg}}, w_{\text{curt}}$) were dynamically adjusted based on market volatility and grid stress.
4. **Candidate Plan Explorer:** Scroll down to view the multiple candidate dispatch plans evaluated by the strategy agent before committing the setpoints.

---

### Test Scenario 4: Audit Trail & Hard Safety Guardrails
> **Goal:** Verify that every decision is traceable and validated by deterministic safety rules.

1. In the sidebar, navigate to **`4 📜 Decision Log`**.
2. Expand any recorded interval (e.g., *Interval 5*).
3. **Review the JSON audit trail:**
   * Inputs observed (weather, actual solar/wind, market price).
   * Agent reasoning and chosen objective weights.
   * PuLP MILP solver status (`Optimal`).
   * **Guardrail Validation Results:** Confirm that all 8 safety checks passed (**Power balance = 0 MW mismatch**, **Battery SoC within bounds**, **Ramp limits respected**, **Transmission export cap satisfied**, and **Critical load loss = 0**).

---

### Test Scenario 5: Business Impact & Strategy Benchmark
> **Goal:** Verify the business impact of GridMind versus industry standard baselines.

1. In the sidebar, navigate to **`5 📊 Scenario Comparison`**.
2. Review the 3-Way 24-hour head-to-head benchmark:
   * **1. Rule-Based Baseline** (Simple heuristic dispatch)
   * **2. Fixed MILP Optimizer** (Deterministic solver with static weights)
   * **3. GridMind Agent** (Adaptive agentic weight tuning + rolling MILP)
3. **Verify Key Metrics:**
   * **Net Cost:** Agent achieves **~44.5% cost reduction** (over ₹18M daily savings).
   * **Contract Shortfall:** Reduced by **~88.7%** compared to baseline heuristics.
   * **Unserved Critical Load:** Exactly **0.00 MWh** across all models.

---

### Test Scenario 6: 30-Day Stress Reliability Proof (Position D2 / F3)
> **Goal:** Verify reliability across an extensive multi-day rolling simulation with randomized forecast errors.

1. In the sidebar, navigate to **`6 🛡️ Reliability Report`**.
2. Review the summary of the **30-Day Stress Simulation** (2,880 consecutive intervals, 100+ injected disturbance events):
   * **Hard-Constraint Violations:** `0 / 2,880` (100% compliance).
   * **Critical Unserved Load:** `0.00 MWh`.
   * **Audit Table:** Scroll through the daily metrics table showing net cost, carbon emissions, and shortfall across Season A and Season B.

---

### Summary Checklist for Tester Feedback
- [ ] Did the dashboard load cleanly with no errors?
- [ ] Did clicking `Step (15m)` update power balance and battery levels smoothly?
- [ ] Did injecting an event trigger an observable change in the agent's mode and explanation?
- [ ] Did the 8 guardrail safety checks show green passes in the Decision Log?
- [ ] Was the candidate plan trade-off logic clearly understandable?
