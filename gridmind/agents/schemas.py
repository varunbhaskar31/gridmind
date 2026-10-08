"""Pydantic schemas for structured agent outputs and tool calls.

Ensures strict validation across Monitor, Strategy, and Explainer agents.
Invalid JSON from LLM undergoes automatic one-time repair before fallback.
"""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class Signal(BaseModel):
    """An operational signal detected between actuals and expectations."""
    category: Literal["generation", "demand", "price", "storage", "grid", "event"]
    asset_id: Optional[str] = None
    metric: str
    current_value: float
    reference_value: float
    delta_pct: float
    description: str


class MonitorReport(BaseModel):
    """Structured report produced by the Monitor agent."""
    severity: Literal["low", "medium", "high", "critical"]
    signals: List[Signal] = Field(default_factory=list)
    summary: str = Field(..., description="Short situation briefing for the shift dispatch manager")
    replan_required: bool = Field(False, description="Whether immediate optimization replan is needed")


class CandidatePlanSummary(BaseModel):
    """Summary metrics of a candidate plan evaluated during strategy selection."""
    plan_id: str
    weights: Dict[str, float]
    expected_cost: float
    p_shortfall: float
    p_unserved: float
    min_soc: float = 0.50


class StrategyDecision(BaseModel):
    """Dispatch strategy proposed by the Strategy agent."""
    mode: Literal[
        "green",
        "economic",
        "reliability_first",
        "storm_preparation",
        "outage_recovery",
        "congestion_management",
    ]
    weights: Dict[str, float] = Field(
        ...,
        description="Weights for cost, carbon, curtailment, degradation, reliability (each 0..5)",
    )
    reserve_floor: float = Field(
        0.10, ge=0.0, le=0.80, description="Minimum battery SoC reserve floor fraction"
    )
    terminal_soc_target: float = Field(
        0.50, ge=0.0, le=1.0, description="Target SoC fraction at horizon boundary"
    )
    chosen_plan_id: str = Field(..., description="Identifier of the selected plan")
    candidates_considered: List[CandidatePlanSummary] = Field(
        default_factory=list, description="Evaluated candidate plan options"
    )
    tradeoff_statement: str = Field(
        ..., description="Explicit trade-off statement quoting verified tool metrics"
    )
    confidence: Literal["low", "medium", "high"] = "high"
    requires_operator_approval: bool = False
    rationale: str = Field(..., max_length=500, description="Dispatch rationale under 80 words")


class Explanation(BaseModel):
    """Operator briefing explaining an executed dispatch decision."""
    headline: str = Field(..., description="Punchy control room headline under 15 words")
    what_we_did: str = Field(..., description="Concrete actions taken across assets and grid")
    why: str = Field(..., description="Core operational or market motive")
    tradeoff: str = Field(..., description="What was sacrificed in exchange for the chosen benefit")
    what_would_change_our_mind: str = Field(
        ..., description="Specific conditions that would trigger an operational reversal"
    )
