"""Pydantic contracts for the QA Agent — mirrors agents/AGENT-CONTRACTS.md §6
+ 02-RESEARCH.md Pattern 2.

QAAG-04 / Pitfall 2: The model_validator on QAOutput is the LAST line of defense
against QA runaway (infinite fix loops). NEVER remove or weaken it. The SKILL.md
system prompt instruction is probabilistic — only the model_validator is deterministic.

QAAG-03: Field(max_length=5) on findings enforces the fix-subtask cap at the schema
level, not just the system prompt.

QAAG-05: All Linear writes (qa_cycle_count increment, fix subtask creation) happen
OUTSIDE the agent loop via Phase 1 service — see qa_agent.py._write_qa_results_to_linear.
"""
from __future__ import annotations
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class QAEvidence(BaseModel):
    file: str
    component: str
    location: str
    related_requirement: str
    model_config = {"extra": "forbid"}


class SuggestedSubtask(BaseModel):
    """Per skills/03-QA-REVIEW.md, fix subtask titles MUST start with '[FIX] '."""
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


class PRTargetingGuidance(BaseModel):
    target_pr: str
    model_config = {"extra": "forbid"}


class QAFinding(BaseModel):
    title: str
    severity: Literal["critical", "high", "medium", "low"]
    category: Literal[
        "functional", "architecture", "code_quality", "test", "security", "regression"
    ]
    status: Literal["blocking", "non_blocking"]
    problem: str
    evidence: QAEvidence
    expected_behavior: str
    actual_behavior: str
    suggested_fix: str
    suggested_subtask: Optional[SuggestedSubtask] = None
    pr_targeting_guidance: Optional[PRTargetingGuidance] = None
    model_config = {"extra": "forbid"}


class PullRequestInput(BaseModel):
    url: str
    diff: str  # full diff text from `gh pr diff`
    model_config = {"extra": "forbid"}


class QAInput(BaseModel):
    """Input contract for the QA Agent.

    Mirrors AGENT-CONTRACTS.md §6 Input + qa_cycle_count.

    qa_cycle_count is 0-indexed: 0 = first review, 1 = second, 2 = third.
    Caller MUST fetch this from Linear immediately before constructing QAInput
    (Pitfall 6) — the agent itself does not read Linear.
    """
    work_item_id: str
    linear_issue: dict
    pull_request: PullRequestInput
    implementation_notes: dict = Field(default_factory=dict)
    epic_context: dict = Field(default_factory=dict)
    qa_cycle_count: int = Field(ge=0, le=2)

    model_config = {"extra": "forbid"}


class QAOutput(BaseModel):
    """Output contract for the QA Agent.

    Mirrors AGENT-CONTRACTS.md §6 Output + qa_cycle_count + tech_debt_annotation.

    qa_cycle_count is 1-indexed in output: 1 = first review done, 2 = second, 3 = third.

    IMMUTABLE CONSTRAINT: The model_validator below enforces the QA cycle cap.
    NEVER remove or weaken it — it is the last line of defense against QA runaway
    (PITFALLS.md Pitfall 2 of Phase 2 RESEARCH.md). The SKILL.md system prompt
    instruction is probabilistic; the model_validator is deterministic.
    """
    work_item_id: str
    qa_status: Literal["approved", "changes_required"]
    qa_cycle_count: int = Field(ge=1, le=3)
    summary: str
    findings: list[QAFinding] = Field(max_length=5)  # QAAG-03 hard cap
    tech_debt_annotation: Optional[str] = None  # required when qa_cycle_count >= 3

    @model_validator(mode="after")
    def validate_cycle_cap_logic(self) -> "QAOutput":
        # IMMUTABLE: do not modify. See class docstring.
        if self.qa_cycle_count >= 3 and self.qa_status == "changes_required":
            raise ValueError(
                "At qa_cycle_count >= 3, status must be 'approved' with tech_debt_annotation. "
                "QA runaway prevention (QAAG-04, PITFALLS.md Pitfall 2)."
            )
        if self.qa_cycle_count >= 3 and not self.tech_debt_annotation:
            raise ValueError(
                "tech_debt_annotation required when qa_cycle_count >= 3"
            )
        return self

    model_config = {"extra": "forbid"}
