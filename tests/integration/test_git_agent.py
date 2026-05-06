"""Integration tests for Git Agent — hsb-test-fixture GitHub repo (D-11).

Covers: GITA-01, GITA-02, GITA-03, GITA-04.
"""
import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
def test_branch_naming():
    """GITA-01: branch matches feature/LIN-{id}-{slug} regex."""
    pytest.skip("Wave 1 Plan 04 (Git Agent) implements this test body")


@pytest.mark.integration
def test_pr_base():
    """GITA-02 + D-07: task PR targets EPIC branch directly (not main, not another task)."""
    pytest.skip("Wave 1 Plan 04 (Git Agent) implements this test body")


@pytest.mark.integration
def test_pr_title():
    """GITA-03: PR title starts with [LIN-{id}]."""
    pytest.skip("Wave 1 Plan 04 (Git Agent) implements this test body")


@pytest.mark.integration
def test_rebase_stack():
    """GITA-04 + D-08: REBASE_STACK rebases all open sibling task PRs after merge.
    Uses --force-with-lease (NOT --force) per Pattern 5.
    """
    pytest.skip("Wave 1 Plan 04 (Git Agent) implements this test body")
