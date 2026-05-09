"""INTL-02: WIO Step 5 writes Knowledge Store entries with all 8 required
fields after a QA finding."""

from pathlib import Path

import pytest
import yaml

from hsb.contracts.knowledge import KnowledgeStorageInput

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_wio_step5_writes_knowledge_entry(
    linear_test_workspace,
    test_task_with_qa_finding_fixture,  # conftest.py fixture (Phase 5 — to be added)
    tmp_knowledge_cleanup,
):
    """INTL-02 + INTL-03: After QA, a ``knowledge/<category>/*.md`` file is
    written with all 8 fields."""
    from hsb.agents.work_item_orchestrator import run_orchestration_cycle

    knowledge_root = Path("knowledge")
    before = (
        set(p.relative_to(knowledge_root) for p in knowledge_root.rglob("*.md"))
        if knowledge_root.exists()
        else set()
    )

    await run_orchestration_cycle(
        work_item_id=test_task_with_qa_finding_fixture["id"],
    )

    after = (
        set(p.relative_to(knowledge_root) for p in knowledge_root.rglob("*.md"))
        if knowledge_root.exists()
        else set()
    )
    new_files = after - before
    assert new_files, "INTL-02: No new knowledge/ entry written after WIO Step 5"

    # INTL-03: every new entry parses as KnowledgeStorageInput.
    for rel in new_files:
        text = (knowledge_root / rel).read_text()
        assert text.startswith("---\n"), f"{rel} missing YAML frontmatter"
        _, frontmatter, _ = text.split("---\n", 2)
        data = yaml.safe_load(frontmatter)
        KnowledgeStorageInput(**data)
