"""UAT Agent contracts (Phase 5).

Two pydantic models per AI-SPEC §4b.1.

- :class:`UATScenario`: one scenario per acceptance criterion. ``evidence``
  has ``min_length=10`` to enforce the not-a-paraphrase domain requirement
  (AI-SPEC §5 dimension B2).
- :class:`UATResult`: the top-level UAT output. ``uat_cycle`` is 1-indexed
  (``ge=1``); ``scope_violations`` defaults to an empty list.

Both models use ``model_config = {"extra": "forbid"}`` so the LLM cannot
sneak rogue fields past parse.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class UATScenario(BaseModel):
    criterion_id: str = Field(
        ..., description="Identifier matching the [AC-N] label in the prompt"
    )
    criterion_text: str
    status: Literal["pass", "fail", "blocked"]
    evidence: str = Field(
        ...,
        description="Specific observable evidence — not a paraphrase",
        min_length=10,
    )
    finding: str | None = Field(None, description="Required when status=fail")
    model_config = {"extra": "forbid"}


class UATResult(BaseModel):
    user_story_id: str
    overall_status: Literal["approved", "changes_required", "blocked"]
    scenarios: list[UATScenario]
    scope_violations: list[str] = Field(default_factory=list)
    uat_cycle: int = Field(..., ge=1)
    model_config = {"extra": "forbid"}
