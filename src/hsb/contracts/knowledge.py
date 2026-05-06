"""Knowledge Store contracts (Phase 5).

Three pydantic models per AI-SPEC §4b.1 + 05-RESEARCH.md §Files Created.
All models use ``model_config = {"extra": "forbid"}`` so any LLM-emitted
payload with rogue fields fails parse.

INTL-03: ``KnowledgeStorageInput.applicability`` MUST identify specific
conditions; the validator rejects empty/whitespace strings and the
case-insensitive set ``{"all tasks", "all", "n/a", "tbd"}``.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class KnowledgeEnrichmentOutput(BaseModel):
    work_item_id: str
    enrichment_report: dict  # matches AGENT-CONTRACTS.md §9 output structure
    retrieved_entries: list[str]  # file paths of Knowledge Store entries retrieved

    model_config = {"extra": "forbid"}


class KnowledgeStorageInput(BaseModel):
    """8 required fields per INTL-03. ``applicability`` must not be empty or 'all tasks'."""

    title: str
    type: Literal[
        "architecture",
        "qa",
        "implementation",
        "backlog",
        "risk",
        "pattern",
        "anti_pattern",
    ]
    context: str
    evidence: dict  # linear_issue, pr, files, qa_finding
    insight: str
    recommendation: str
    applicability: str = Field(..., description="Non-empty, not 'all tasks'")
    date: str  # YYYY-MM-DD

    @field_validator("applicability")
    @classmethod
    def applicability_not_all_tasks(cls, v: str) -> str:
        if not v.strip() or v.strip().lower() in ("all tasks", "all", "n/a", "tbd"):
            raise ValueError(
                "applicability must identify specific conditions — "
                "not 'all tasks', empty, or 'n/a'"
            )
        return v

    model_config = {"extra": "forbid"}


class KnowledgeStorageOutput(BaseModel):
    stored: bool
    location: str
    entry_id: str
    was_duplicate: bool

    model_config = {"extra": "forbid"}
