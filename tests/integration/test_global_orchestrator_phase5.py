"""End-to-end Phase 5 integration test: Risk priority queue + UAT dispatch
+ improvement_triggers."""

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_ready_tasks_sorted_by_risk_score(linear_test_workspace):
    """SC-4: ``GlobalOrchestratorOutput.ready_tasks`` is risk-sorted by
    ``RiskAgent.get_priority_queue()``."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    from hsb.agents.risk_agent import RiskAgent

    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()

    # Recompute the expected priority order from the same Linear state and
    # assert the GlobalOrchestrator output order matches.
    all_items = await go._fetch_all_items()
    linear_state = {
        (item["id"] if isinstance(item, dict) else item.id): (
            item if isinstance(item, dict) else item.model_dump()
        )
        for item in all_items
    }
    ra = RiskAgent()
    raw = go._filter_ready_items(all_items)
    raw_ids = [(t["id"] if isinstance(t, dict) else t.id) for t in raw]
    expected_pq = ra.get_priority_queue(raw_ids, linear_state)

    actual_ids = [
        (t["id"] if isinstance(t, dict) else (t.id if hasattr(t, "id") else t))
        for t in output.ready_tasks
    ]
    assert actual_ids == expected_pq.items, (
        f"SC-4 violated: ready_tasks order mismatch.\n"
        f"  Expected: {expected_pq.items}\n  Actual:   {actual_ids}"
    )


@pytest.mark.asyncio
async def test_phase5_output_has_optional_fields(linear_test_workspace):
    """Output extension regression: ``uat_dispatched`` and
    ``improvement_triggers`` always present."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator

    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()
    assert hasattr(output, "uat_dispatched"), "uat_dispatched field missing"
    assert hasattr(output, "improvement_triggers"), "improvement_triggers field missing"
    assert isinstance(output.uat_dispatched, list)
    assert isinstance(output.improvement_triggers, list)


def test_phase4_features_preserved():
    """Regression: Phase 4 features still present (GORD-01..04)."""
    src = open("src/hsb/agents/global_orchestrator.py").read()
    assert "_filter_ready_items" in src, (
        "GORD-01..02 regression: _filter_ready_items removed"
    )
    assert "_check_epic_complete" in src, (
        "GORD-04 regression: _check_epic_complete removed"
    )
    assert "is_backlog_empty" in src, (
        "GORD-03 regression: is_backlog_empty signal removed"
    )
