"""Integration tests for QA Agent — real Linear workspace + real PR diff.

Covers: QAAG-01, QAAG-05.
"""
import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
def test_qa_review():
    """QAAG-01: QA Agent produces an approved or changes_required QAOutput."""
    pytest.skip("Wave 1 Plan 05 (QA Agent) implements this test body")


@pytest.mark.integration
def test_capability_boundary():
    """QAAG-05: QA Agent never uses Edit/Write/git tools (Phoenix trace inspection)."""
    pytest.skip("Wave 1 Plan 05 (QA Agent) implements this test body")
