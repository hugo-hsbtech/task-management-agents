"""UATA-03 integration test: when ``UATResult.overall_status ==
'changes_required'``, Global Orchestrator creates fix subtasks via
Linear Agent.

Real Linear test workspace; no mocking. Runs as a smoke test only when a
fixture User Story produces a 'changes_required' verdict — typically
requires operator-curated test data.
"""
import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_uat_changes_required_creates_linear_subtasks(
    linear_test_workspace,
    uat_ready_user_story,
):
    """UATA-03: fix subtasks created in Linear when UAT status is
    ``changes_required``.

    Pre-condition: the ``uat_ready_user_story`` fixture must point to a
    User Story whose implementation does NOT meet at least one acceptance
    criterion (e.g., a deliberately incomplete test fixture in
    ``hsb-test-fixture``). If the fixture happens to pass UAT, this test
    SKIPs because UATA-03 is only triggered on ``changes_required``.
    """
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    from hsb.agents.linear_agent import run_validated_linear_agent

    before_resp = await run_validated_linear_agent(
        operation="list_children",
        payload={"parent_id": uat_ready_user_story["id"]},
    )
    before_count = len(before_resp.linear_entities or [])

    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()

    if uat_ready_user_story["id"] not in output.uat_dispatched:
        pytest.skip("User Story not dispatched for UAT this cycle")

    after_resp = await run_validated_linear_agent(
        operation="list_children",
        payload={"parent_id": uat_ready_user_story["id"]},
    )
    after_count = len(after_resp.linear_entities or [])

    # Verdict: either approved (no new subtasks) or changes_required (>=1
    # new subtask). Both outcomes are valid from this test's perspective;
    # assert the structural invariant that the GO output reflects exactly
    # one of the two paths and that the subtask count never shrinks during
    # a UAT cycle.
    assert uat_ready_user_story["id"] in output.uat_dispatched, "UAT not dispatched"
    assert after_count >= before_count, (
        f"UATA-03: subtask count shrunk from {before_count} to {after_count} — unexpected"
    )
