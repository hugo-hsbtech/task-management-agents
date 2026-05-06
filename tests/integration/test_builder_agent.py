"""Integration tests for Builder Agent — hsb-test-fixture GitHub repo (D-11).

Covers: BLDR-01, BLDR-02, BLDR-04.
"""
import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
def test_scoped_implementation():
    """BLDR-01: Builder reads work item from Linear and implements only the scoped change."""
    pytest.skip("Wave 1 Plan 03 (Builder Agent) implements this test body")


@pytest.mark.integration
def test_validation_run():
    """BLDR-02: Builder runs available local validations and reports passed|failed|not_run."""
    pytest.skip("Wave 1 Plan 03 (Builder Agent) implements this test body")


@pytest.mark.integration
def test_capability_boundary():
    """BLDR-04: Builder Agent does NOT use git or Linear tools — verified via Phoenix
    trace inspection or by asserting no `Bash(git *)` / `mcp__linear__*` calls in run.
    """
    pytest.skip("Wave 1 Plan 03 (Builder Agent) implements this test body")
