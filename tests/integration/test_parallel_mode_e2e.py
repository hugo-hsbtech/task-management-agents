"""Phase 4 Plan 04 — Live integration tests for parallel mode acceptance gate.

THE Phase 4 Success Criterion 5 lives here: test_no_double_claim_parallel_two_tasks
verifies that two ready tasks dispatched in parallel are claimed exactly once
each (MORD-03), and test_worktree_cleanup_after_parallel verifies D-09 cleanup.
Both run against a real Linear workspace via mcp-remote OAuth2 (Phase 1 D-01).
"""

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_double_claim_parallel_two_tasks():
    """
    MORD-03 acceptance gate: Two ready tasks dispatched in parallel must not be
    double-claimed. Phase 4 Success Criterion 5 (CONTEXT.md Specific Ideas).

    Pre-condition: At least 2 todo tasks exist in the Linear test workspace
    with no blocking dependencies.
    """
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    from hsb.agents.main_orchestrator import run_main_orchestrator
    from hsb.agents.linear_agent import run_validated_linear_agent

    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()

    if len(output.ready_tasks) < 2:
        pytest.skip("Requires at least 2 todo tasks in Linear test workspace")

    captured_ids = [t.id for t in output.ready_tasks[:2]]

    # Run parallel mode — should claim and dispatch both without double-claiming
    await run_main_orchestrator(mode="parallel")

    # Post-condition: read Linear state — both tasks should be in_progress or
    # done, neither should still be in todo (a double-claim would leave one
    # unclaimed).
    for task_id in captured_ids:
        fresh = await run_validated_linear_agent(
            operation="read",
            payload={"issueId": task_id},
        )
        assert fresh.linear_entities, f"Task {task_id} disappeared from Linear"
        entity = fresh.linear_entities[0]
        status = (
            entity.get("status")
            if isinstance(entity, dict)
            else getattr(entity, "status", None)
        )
        assert status != "todo", (
            f"Task {task_id} still in todo after parallel dispatch — possible double-claim failure."
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_double_claim():
    """Alias for test_no_double_claim_parallel_two_tasks (matches 04-VALIDATION.md row 04-03-01)."""
    await test_no_double_claim_parallel_two_tasks()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_worktree_cleanup_after_parallel():
    """D-09: Worktrees are removed after parallel dispatch completes."""
    import os
    from hsb.agents.main_orchestrator import run_main_orchestrator, WORKTREES_DIR

    worktrees_path = os.path.join(os.getcwd(), WORKTREES_DIR)

    await run_main_orchestrator(mode="parallel")

    # .worktrees/ should be empty (or non-existent) after cleanup
    if os.path.exists(worktrees_path):
        remaining = os.listdir(worktrees_path)
        assert remaining == [], (
            f"Stale worktrees found after parallel dispatch: {remaining}. "
            "Cleanup must succeed regardless of WIO outcome (D-09)."
        )
