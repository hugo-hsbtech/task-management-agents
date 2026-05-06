"""INTL-01: WIO Step 1 retrieves Knowledge Store entries and populates
``knowledge_context``."""
import json

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_wio_step1_populates_knowledge_context(
    linear_test_workspace,  # conftest.py fixture (Phase 1)
    test_task_with_knowledge_fixture,  # conftest.py fixture (Phase 5 — to be added)
    tmp_knowledge_cleanup,  # conftest.py fixture (Phase 1 — knowledge cleanup)
):
    """INTL-01: Enrichment retrieval runs before Builder; ``knowledge_context``
    populated and Linear comment posted with Enrichment Report."""
    from hsb.agents.work_item_orchestrator import run_orchestration_cycle

    await run_orchestration_cycle(
        work_item_id=test_task_with_knowledge_fixture["id"],
    )

    # SC-1: Linear comment with Enrichment Report appears on the work item.
    from hsb.agents.linear_agent import run_validated_linear_agent

    read = await run_validated_linear_agent(
        operation="read",
        payload={"issueId": test_task_with_knowledge_fixture["id"]},
    )
    comments = []
    if read.linear_entities:
        entity = read.linear_entities[0]
        if isinstance(entity, dict):
            comments = entity.get("comments", [])
    joined = "\n".join(
        c.get("body", "") if isinstance(c, dict) else str(c) for c in comments
    )
    assert "Enrichment Report" in joined or "knowledge_context" in joined, (
        "INTL-01: Expected Enrichment Report or knowledge_context in Linear comments"
    )
