"""Global Orchestrator — Phase 4 Plan 02.

Pure Python class (D-01): no Claude Agent SDK session, no LLM, no skill injection.
Reads Linear state via the Phase 1 `run_validated_linear_agent` service, applies
deterministic filter and sort, returns a `GlobalOrchestratorOutput`.

Implements GORD-01 (todo-only filter), GORD-02 (dependency filter), GORD-03
(empty backlog signal), and GORD-04 (EPIC completion signal). All architectural
no-LLM assertions are enforced by `tests/unit/test_main_orchestrator.py::
test_no_sdk_session_in_global_orchestrator` (filled in by Plan 03).
"""
from __future__ import annotations
import logging
from typing import Any

from dotenv import load_dotenv

from hsb.agents.linear_agent import run_validated_linear_agent
from hsb.contracts.global_orchestrator import GlobalOrchestratorOutput, ReadyTask

load_dotenv()

logger = logging.getLogger(__name__)


class GlobalOrchestrator:
    """
    Pure Python class — no LLM, no SDK session (D-01).
    Reads Linear state via run_validated_linear_agent, applies deterministic
    filter/sort, returns GlobalOrchestratorOutput.
    """

    async def get_ready_tasks(self) -> GlobalOrchestratorOutput:
        """Public entrypoint — returns the prioritized ready-task list plus signals.

        Implements GORD-01..04:
          - GORD-01/02: _filter_ready_items applies the todo + dependency filter.
          - GORD-03: empty Linear response → is_backlog_empty=True.
          - GORD-04: _check_epic_complete on the full set → is_epic_ready.
        """
        all_items = await self._fetch_all_items()

        if not all_items:
            return GlobalOrchestratorOutput(
                ready_tasks=[],
                is_backlog_empty=True,
                is_epic_ready=False,
            )

        ready = self._filter_ready_items(all_items)
        # Sort key: Linear priority ascending (1=urgent, 2=high, 3=medium, 4=low,
        # 0/None=no priority). Default 999 sorts unset items last. createdAt is
        # the deterministic tiebreaker (oldest first).
        ready.sort(key=lambda x: (x.get("priority", 999), x.get("createdAt", "")))

        is_epic_ready = self._check_epic_complete(all_items)

        return GlobalOrchestratorOutput(
            ready_tasks=[ReadyTask(id=t["id"], title=t["title"]) for t in ready],
            is_backlog_empty=False,
            is_epic_ready=is_epic_ready,
        )

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
