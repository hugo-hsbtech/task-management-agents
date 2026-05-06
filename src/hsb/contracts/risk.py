"""Risk Agent contracts (Phase 5).

Pydantic models for the deterministic skills 12+13 outputs and the skill 14
isolated-SDK-call output. All models use ``model_config = {"extra": "forbid"}``.

RISK-04 (defense-in-depth layer 2): ``AutoImprovementTrigger.linear_state`` is
``Literal["suggested"]``. Pydantic rejects any other value at parse time, so
even if the skill 14 LLM hallucinates a payload claiming ``"created"``, the
model will refuse to construct.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QualityScore(BaseModel):
    work_item_id: str
    score: float = Field(..., ge=0.0, le=100.0)
    qa_failures: int = 0
    fix_subtask_count: int = 0
    uat_failed: bool = False
    rework_cycles: int = 0
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    model_config = {"extra": "forbid"}


class PriorityQueue(BaseModel):
    items: list[str]
    scores: dict[str, float]
    model_config = {"extra": "forbid"}


class AutoImprovementTrigger(BaseModel):
    title: str
    description: str
    pattern_evidence: list[str] = Field(
        ..., description="Work item IDs or QA finding refs"
    )
    suggested_type: str
    linear_state: Literal["suggested"] = "suggested"
    model_config = {"extra": "forbid"}
