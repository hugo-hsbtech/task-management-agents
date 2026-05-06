"""Pydantic contracts for the Work Item Orchestrator — mirrors agents/AGENT-CONTRACTS.md §3.

The Work Item Orchestrator drives a single Linear task through its full lifecycle
(Linear read → Builder → Git → QA → fix loop → done) inside one Claude Agent SDK
session. These contracts define the structured input/output for that cycle.

WORC-05: ``lifecycle_summary`` is the persistence payload posted as a Linear comment
after every cycle. Layer 1 of the QA cycle cap (QAAG-04) lives in
:mod:`hsb.contracts.qa` (``QAOutput.validate_cycle_cap_logic``); the Layer 2 safety
net is in :mod:`hsb.agents.work_item_orchestrator`. Do NOT add a model_validator
here — Phase 3 contracts are pure schema (CONTEXT.md D-05).
"""
from __future__ import annotations
from typing import Literal, Optional

from pydantic import BaseModel, Field


class WorkItemOrchInput(BaseModel):
    """Input contract for the Work Item Orchestrator.

    Mirrors agents/AGENT-CONTRACTS.md §3 Input exactly. Fields:

    - ``work_item``: Linear work item snapshot (id, type, status, dependencies)
      fetched fresh from Linear at cycle start.
    - ``epic_context``: parent EPIC metadata required for handoff to Builder/QA.
    - ``linear_state``: arbitrary ancillary Linear state (qa_status, qa_cycle_count,
      pr_link, etc.) required by downstream skills.
    """

    work_item: dict
    epic_context: dict
    linear_state: dict

    model_config = {"extra": "forbid"}


class WorkItemOrchOutput(BaseModel):
    """Output contract for the Work Item Orchestrator.

    Mirrors agents/AGENT-CONTRACTS.md §3 Output exactly. Fields:

    - ``work_item_id``: Linear ID for the orchestrated task.
    - ``lifecycle_status``: terminal state of this orchestration cycle. The
      ``escalated_to_human`` value is the explicit terminal state for QA cycle
      cap escalation (CONTEXT.md D-05 Layer 2 / WORC-03).
    - ``next_skill``: optional handoff hint for the operator / loop driver. ``None``
      when the cycle ended in a terminal state (``done`` or ``escalated_to_human``).
    - ``handoff_payload``: dict carried into the next skill invocation. Default
      empty dict per AGENT-CONTRACTS.md §3.
    - ``lifecycle_summary``: WORC-05 — short prose summary persisted to Linear as
      a comment after every cycle so downstream observers (humans, the global
      orchestrator in Phase 4) can audit progress without replaying the agent log.
    """

    work_item_id: str
    lifecycle_status: Literal[
        "implementation_ready",
        "pr_ready",
        "qa_ready",
        "fix_required",
        "done",
        "escalated_to_human",
    ]
    next_skill: Optional[
        Literal[
            "implementation",
            "git_pr_management",
            "qa_review",
            "linear_system_of_record",
        ]
    ] = None
    handoff_payload: dict = Field(default_factory=dict)
    lifecycle_summary: str  # WORC-05 — posted to Linear as a comment after each cycle

    model_config = {"extra": "forbid"}
