"""Plan 03-04 — Orchestrator end-to-end integration tests.

These tests run against the real Linear test workspace + the
``hsb-test-fixture`` GitHub repo (Phase 2 D-11) and the live Claude Agent
SDK. They are marked ``pytest.mark.integration`` and are SKIPPED unless
the operator has set ``TEST_WORK_ITEM_ID`` to a seeded Linear Task ID.

VALIDATION.md aliases:
- WORC-01: ``test_full_lifecycle``
- WORC-05: ``test_lifecycle_comment``
"""
from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

pytestmark = [pytest.mark.integration]


def _require_test_work_item_id() -> str:
    """Skip the test if ``TEST_WORK_ITEM_ID`` is not set."""
    work_item_id = os.environ.get("TEST_WORK_ITEM_ID")
    if not work_item_id:
        pytest.skip(
            "TEST_WORK_ITEM_ID env var not set — set to a seeded Linear Task ID "
            "(see 03-04-PLAN.md Task 2 setup)."
        )
    return work_item_id


# --- WORC-01: Full lifecycle todo → terminal state --------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_lifecycle_todo_to_done() -> None:
    """WORC-01: orchestrator drives a real Linear task to a terminal lifecycle state.

    Prereqs: real Linear test workspace, ``hsb-test-fixture`` GitHub repo,
    ANTHROPIC_API_KEY set, TEST_WORK_ITEM_ID env var pointing at a todo task.

    Acceptance: ``run_orchestration_cycle`` completes without raising; the
    target Linear issue can be re-read after the cycle. Final lifecycle status
    may be ``done``, ``fix_required``, or ``escalated_to_human`` depending on
    QA outcome (CONTEXT.md D-04).
    """
    from hsb.agents.work_item_orchestrator import run_orchestration_cycle
    from hsb.agents.linear_agent import run_validated_linear_agent

    work_item_id = _require_test_work_item_id()

    # One full orchestration cycle. Should complete without raising.
    await run_orchestration_cycle(work_item_id)

    # Re-read the Linear issue to confirm it is reachable post-cycle.
    result = await run_validated_linear_agent("read", {"issueId": work_item_id})
    assert result is not None
    assert result.result in ("success", "ok")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_lifecycle() -> None:
    """WORC-01 alias matching VALIDATION.md command ID."""
    await test_full_lifecycle_todo_to_done()


# --- WORC-05: lifecycle_summary persisted to Linear --------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_lifecycle_comment_persisted() -> None:
    """WORC-05: ``lifecycle_summary`` is persisted to Linear as a comment after the cycle.

    Snapshots the comment count before and after a single
    ``run_orchestration_cycle`` invocation; expects at least one new comment
    (the ``lifecycle_summary``).
    """
    from hsb.agents.work_item_orchestrator import run_orchestration_cycle
    from hsb.agents.linear_agent import run_validated_linear_agent

    work_item_id = _require_test_work_item_id()

    # Snapshot comment count BEFORE the cycle
    before = await run_validated_linear_agent(
        "read", {"issueId": work_item_id, "include": "comments"}
    )
    before_count = len(getattr(before, "linear_entities", []) or [])

    await run_orchestration_cycle(work_item_id)

    after = await run_validated_linear_agent(
        "read", {"issueId": work_item_id, "include": "comments"}
    )
    after_count = len(getattr(after, "linear_entities", []) or [])

    assert after_count >= before_count + 1, (
        "WORC-05: expected lifecycle_summary comment posted to Linear; "
        f"before={before_count}, after={after_count}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lifecycle_comment() -> None:
    """WORC-05 alias matching VALIDATION.md command ID."""
    await test_lifecycle_comment_persisted()


# --- WORC-03: orchestrator never initiates a 4th QA cycle -------------------

@pytest.mark.integration
def test_qa_cycle_cap_not_exceeded() -> None:
    """WORC-03: contract Layer 1 rejects ``qa_cycle_count >= 3 + changes_required``.

    The orchestrator-level Layer 2 safety net is verified in unit tests
    (``test_qa_cycle_cap_safety_net_posts_comment``). This integration check
    confirms the contract guard is intact in the running test environment —
    the same QAOutput contract that the orchestrator depends on.
    """
    from hsb.contracts.qa import QAOutput

    with pytest.raises(ValidationError):
        QAOutput.model_validate(
            {
                "work_item_id": "LIN-TEST-1",
                "qa_status": "changes_required",
                "qa_cycle_count": 3,
                "summary": "Fourth cycle attempt",
                "findings": [],
            }
        )
