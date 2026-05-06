"""Global Orchestrator — Phase 4 Plan 02 + Phase 5 Plan 04 extensions.

Pure Python class (D-01): no Claude Agent SDK session, no LLM, no skill injection.
Reads Linear state via the Phase 1 `run_validated_linear_agent` service, applies
deterministic filter and sort, returns a `GlobalOrchestratorOutput`.

Phase 4 surface (preserved verbatim):
- GORD-01 (todo-only filter), GORD-02 (dependency filter), GORD-03
  (empty backlog signal), GORD-04 (EPIC completion signal).

Phase 5 additive surface:
- D-10: Risk Agent priority queue insertion in ``get_ready_tasks`` after the
  existing dependency filter. ``ready_tasks`` is risk-sorted (RISK-02 sort +
  updatedAt tiebreaker) per cycle.
- D-01 / UATA-01: ``_detect_uat_ready_user_stories`` finds User Stories
  whose child tasks are all ``qa_status=approved`` and ``uat_status`` is
  not yet ``approved``. For each, ``run_uat_and_validate`` is dispatched
  inline via ``await`` (NOT a subprocess — 05-RESEARCH §Open Implementation
  Choices §4).
- UATA-03: on ``changes_required`` → ``run_validated_linear_agent(operation=
  "create_subtasks", ...)``. On ``approved`` → update ``uat_status``.
- G6 (UAT cycle cap = 3): User Stories at ``uat_cycle_count >= 3`` are
  excluded from re-dispatch and a Linear escalation comment is posted via
  the camelCase ``linear_createComment`` payload shape (``issueId``,
  ``body``).
- G10 (UAT pre-persist validation): :func:`_uat_passes_g10` re-runs the
  B1 coverage check and B3 banned-token regex on every ``UATResult``
  before any Linear write. Failure logs at ERROR and refuses persist.
- RISK-04 / D-09: ``improvement_triggers`` is always ``[]`` in the
  per-cycle path. Surfacing improvement triggers requires explicit
  operator-delegated CLI invocation (deferred to a future plan).
"""
from __future__ import annotations
import logging
import re
from typing import Any

from dotenv import load_dotenv

from hsb.agents.linear_agent import run_validated_linear_agent
from hsb.agents.risk_agent import RiskAgent
from hsb.agents.uat_agent import run_uat_and_validate
from hsb.contracts.global_orchestrator import GlobalOrchestratorOutput, ReadyTask
from hsb.contracts.risk import AutoImprovementTrigger
from hsb.contracts.uat import UATResult

load_dotenv()

logger = logging.getLogger(__name__)


# Phase 5 G10 helper (AI-SPEC §6) — module-level so unit tests can verify
# the predicate independently of the orchestrator class. The B3 banned
# tokens align with `tests/evals/code_based/test_uat_scope.py`.
_UAT_BANNED_RE = re.compile(
    r"\brefactor\b|\bcode quality\b|\bnaming\b|\bstyle\b|\blinter?\b|"
    r"\binefficient\b|\bshould also handle\b|\bfuture edge case\b",
    re.IGNORECASE,
)


def _uat_passes_g10(result: UATResult, acceptance_criteria: list[str]) -> bool:
    """G10 (AI-SPEC §6): validate ``UATResult`` before Linear persistence.

    B1: scenario set covers all expected ACs (``{AC-1, AC-2, ..., AC-N}``).
    B3: no banned tokens in scenario evidence/finding (scope-creep).

    Returns ``True`` only if both checks pass; the orchestrator refuses
    persist on a ``False`` return.
    """
    expected = {f"AC-{i + 1}" for i in range(len(acceptance_criteria))}
    actual = {s.criterion_id for s in result.scenarios}
    if actual != expected:
        return False
    for s in result.scenarios:
        for field in (s.evidence, s.finding or ""):
            if _UAT_BANNED_RE.search(field):
                return False
    return True


class GlobalOrchestrator:
    """
    Pure Python class — no LLM, no SDK session (D-01).
    Reads Linear state via run_validated_linear_agent, applies deterministic
    filter/sort, returns GlobalOrchestratorOutput.
    """

    async def get_ready_tasks(self) -> GlobalOrchestratorOutput:
        """Public entrypoint — returns the prioritized ready-task list plus signals.

        Phase 4 (preserved):
          - GORD-01/02: _filter_ready_items applies the todo + dependency filter.
          - GORD-03: empty Linear response → is_backlog_empty=True.
          - GORD-04: _check_epic_complete on the full set → is_epic_ready.

        Phase 5 (additive):
          - D-10: Risk Agent priority queue replaces the Phase 4 priority sort.
          - UATA-01 / D-01: _detect_uat_ready_user_stories + inline-await
            dispatch of run_uat_and_validate.
          - UATA-03: create_subtasks on changes_required; uat_status update on
            approved.
          - G6: UAT cycle cap escalation comment (camelCase issueId/body).
          - G10: _uat_passes_g10 pre-persist validation.
          - RISK-04 / D-09: improvement_triggers = [] (operator-delegated).
        """
        all_items = await self._fetch_all_items()

        if not all_items:
            return GlobalOrchestratorOutput(
                ready_tasks=[],
                is_backlog_empty=True,
                is_epic_ready=False,
                uat_dispatched=[],
                improvement_triggers=[],
            )

        # [Phase 4] Step 1: Dependency filter (todo + no unresolved blocked-by).
        raw_ready = self._filter_ready_items(all_items)

        # [Phase 5] Step 2: Risk Agent priority queue. Replaces the Phase 4
        # `priority/createdAt` sort with the deterministic risk-score sort
        # (RISK-02: score descending, updatedAt ascending tiebreaker).
        risk_agent = RiskAgent()
        linear_state = {item["id"]: item for item in all_items}
        raw_task_ids = [t["id"] for t in raw_ready]
        priority_queue = risk_agent.get_priority_queue(raw_task_ids, linear_state)
        ready_by_id = {t["id"]: t for t in raw_ready}
        # Preserve the ReadyTask Pydantic projection while reordering by risk.
        ready_tasks = [
            ReadyTask(id=tid, title=ready_by_id[tid].get("title", ""))
            for tid in priority_queue.items
            if tid in ready_by_id
        ]

        # [Phase 4] Step 3: EPIC readiness signal.
        is_epic_ready = self._check_epic_complete(all_items)

        # [Phase 5] Step 4: UAT readiness detection + inline dispatch.
        uat_dispatched: list[str] = []
        uat_ready = await self._detect_uat_ready_user_stories(linear_state)
        for us in uat_ready:
            uat_cycle = us.get("uat_cycle_count", 0) + 1
            try:
                uat_result = await run_uat_and_validate(
                    user_story_id=us["id"],
                    acceptance_criteria=us.get("acceptance_criteria", []),
                    uat_cycle=uat_cycle,
                )
            except RuntimeError as exc:
                # G7: never silently mask UAT Agent failure.
                logger.error("UAT Agent failed for %s: %s", us["id"], exc)
                continue

            # G10 pre-persist validation: B1 coverage + B3 banned tokens.
            if not _uat_passes_g10(uat_result, us.get("acceptance_criteria", [])):
                logger.error(
                    "UAT G10 validation failed for %s — refusing to persist "
                    "(coverage gap or scope-creep)",
                    us["id"],
                )
                continue

            uat_dispatched.append(us["id"])
            if uat_result.overall_status == "changes_required":
                # UATA-03: fix subtasks routed through Linear Agent (G5-guarded).
                fail_findings = [
                    s.finding
                    for s in uat_result.scenarios
                    if s.status == "fail" and s.finding
                ]
                await run_validated_linear_agent(
                    operation="create_subtasks",
                    payload={
                        "parent_id": us["id"],
                        "findings": fail_findings,
                    },
                )
            elif uat_result.overall_status == "approved":
                await run_validated_linear_agent(
                    operation="update",
                    payload={
                        "id": us["id"],
                        "uat_status": "approved",
                        "uat_cycle_count": uat_cycle,
                    },
                )

        # [Phase 5] Step 5: improvement triggers — RISK-04 + D-09 require
        # explicit operator delegation. Per-cycle path always returns [].
        improvement_triggers: list[AutoImprovementTrigger] = []

        return GlobalOrchestratorOutput(
            ready_tasks=ready_tasks,
            is_backlog_empty=False,
            is_epic_ready=is_epic_ready,
            uat_dispatched=uat_dispatched,
            improvement_triggers=improvement_triggers,
        )

    async def _detect_uat_ready_user_stories(
        self, linear_state: dict
    ) -> list[dict]:
        """Phase 5 (UATA-01 / D-01).

        Detect User Stories where all child tasks are QA-approved and UAT
        is pending. Mirrors the GORD-04 EPIC-readiness pattern. Stateless —
        re-runs each cycle.

        G6: skips and escalates User Stories at ``uat_cycle_count >= 3``
        (posts a Linear comment via the camelCase ``linear_createComment``
        payload shape — ``issueId``, ``body`` — NOT Python snake_case).
        """
        uat_ready: list[dict] = []
        user_stories = [
            item for item in linear_state.values()
            if (item.get("type") if isinstance(item, dict) else getattr(item, "type", None))
            == "user_story"
        ]
        for us in user_stories:
            us_dict = us if isinstance(us, dict) else us.model_dump()
            if us_dict.get("uat_status") == "approved":
                continue
            uat_cycle_count = us_dict.get("uat_cycle_count", 0)
            if uat_cycle_count >= 3:
                logger.warning(
                    "User Story %s reached max UAT cycles (3) — escalating to human",
                    us_dict["id"],
                )
                # G6 escalation: Linear MCP `linear_createComment` shape.
                # camelCase `issueId` and `body` — matches the Linear GraphQL API.
                try:
                    await run_validated_linear_agent(
                        operation="create_comment",
                        payload={
                            "issueId": us_dict["id"],
                            "body": (
                                "UAT cycle cap reached (3). Awaiting operator "
                                "decision. G6 / Pitfall 2 enforcement."
                            ),
                        },
                    )
                except Exception as exc:
                    logger.warning(
                        "G6 escalation comment failed for %s: %s",
                        us_dict["id"],
                        exc,
                    )
                continue
            children = await self._fetch_children(us_dict["id"])
            children_dicts = [
                c if isinstance(c, dict) else c.model_dump()
                for c in (children or [])
            ]
            if children_dicts and all(
                c.get("qa_status") == "approved" for c in children_dicts
            ):
                uat_ready.append(us_dict)
        return uat_ready

    async def _fetch_children(self, parent_id: str) -> list[dict]:
        """Fetch direct children of a Linear work item (used by Phase 5
        UAT-readiness detection).

        Delegates to ``run_validated_linear_agent(operation="list_children",
        payload={"parent_id": parent_id})``. Returns plain dicts so the
        caller does not depend on the Pydantic LinearEntity shape.
        """
        result = await run_validated_linear_agent(
            operation="list_children",
            payload={"parent_id": parent_id},
        )
        items: list[dict] = []
        for entity in (result.linear_entities or []):
            if hasattr(entity, "model_dump"):
                items.append(entity.model_dump())
            elif hasattr(entity, "__dict__"):
                items.append(dict(entity.__dict__))
            else:
                items.append(dict(entity))
        return items

    def _filter_ready_items(self, all_items: list[dict]) -> list[dict]:
        """
        GORD-01: Return items with status='todo'.
        GORD-02: Exclude items with any unresolved blocked-by dependency.
        """
        done_ids = {item["id"] for item in all_items if item["status"] == "done"}
        ready = []
        for item in all_items:
            if item.get("status") != "todo":
                continue
            deps = item.get("dependencies", [])
            if all(dep_id in done_ids for dep_id in deps):
                ready.append(item)
        return ready

    def _check_epic_complete(self, all_items: list[dict]) -> bool:
        """
        GORD-04: Signal is_epic_ready when all EPIC children are done + qa_approved.
        Returns False if no children exist (empty backlog case already handled above).
        """
        children = [i for i in all_items if i.get("type") != "epic"]
        if not children:
            return False
        return all(
            i.get("status") == "done" and i.get("qa_status") in ("approved", "not_required")
            for i in children
        )

    async def _fetch_all_items(self) -> list[dict]:
        """
        Fetch all work items from Linear for the current project scope.
        Uses run_validated_linear_agent — all Linear reads go through OAuth2 MCP layer (no API keys).

        Returns a list of plain dicts so the deterministic filter/sort code paths
        do not depend on the Pydantic LinearEntity shape (defensive: tolerates both
        BaseModel and plain-dict entities).
        """
        result = await run_validated_linear_agent(
            operation="read",
            payload={"filter": {"project": {"id": {"eq": "CURRENT_PROJECT_ID"}}}},
        )
        items: list[dict] = []
        for entity in result.linear_entities:
            if hasattr(entity, "model_dump"):
                items.append(entity.model_dump())
            elif hasattr(entity, "__dict__"):
                items.append(dict(entity.__dict__))
            else:
                items.append(dict(entity))
        return items
