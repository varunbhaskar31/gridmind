"""Explainer Agent: Generates clear, professional control room operator briefings.

Translates complex optimization and risk numbers into human-readable headlines,
concrete actions, motives, trade-offs, and pivot conditions for the Shift Dispatch Manager.
"""

from typing import Optional
from gridmind.agents.llm_client import LLMClient
from gridmind.agents.mock_logic import mock_explanation
from gridmind.agents.prompts import EXPLAINER_SYSTEM_PROMPT
from gridmind.agents.schemas import Explanation, StrategyDecision
from gridmind.sim.state import DispatchAction, GridState


class ExplainerAgent:
    """Produces structured operator explanations of dispatch decisions."""

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def run(
        self,
        decision: StrategyDecision,
        action: DispatchAction,
        state: GridState,
        force_mock_template: bool = False,
    ) -> Explanation:
        """Generate human-interpretable briefing of the interval dispatch."""
        if self.llm_client.is_mock or force_mock_template:
            return mock_explanation(decision, action, state)

        prompt = (
            f"DISPATCH DECISION EXECUTION SUMMARY:\n"
            f"- Operating Mode: {decision.mode}\n"
            f"- Strategy Rationale: {decision.rationale}\n"
            f"- Explicit Trade-off: {decision.tradeoff_statement}\n"
            f"- Interval: {state.interval_index} ({state.timestamp})\n"
            f"- Battery Charge Command: {action.battery_charge} MW\n"
            f"- Battery Discharge Command: {action.battery_discharge} MW\n"
            f"- Grid Exchange: Import={action.grid_import} MW, Export={action.grid_export} MW\n"
            f"- Demand Response Called: {action.demand_response} MW\n"
            f"- Contract Shortfall: {action.contract_shortfall} MW\n\n"
            f"Please synthesize the shift explanation adhering strictly to the Explanation schema."
        )

        explanation, _ = self.llm_client.generate_structured(
            prompt=prompt,
            schema=Explanation,
            system_instruction=EXPLAINER_SYSTEM_PROMPT,
            fallback_fn=mock_explanation,
            fallback_kwargs={
                "decision": decision,
                "action": action,
                "state": state,
            },
        )
        return explanation
