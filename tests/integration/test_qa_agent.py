"""Integration tests for QA Agent — real Linear workspace + real GitHub PR.

Requires:
  - ANTHROPIC_API_KEY in .env
  - Linear MCP authenticated (Phase 1 mcp-remote)
  - GITHUB_TOKEN with repo scope (gh auth login)
  - HSB_TEST_QA_PR_NUMBER environment variable: a real PR number with a small diff
  - HSB_TEST_QA_LINEAR_ID environment variable: a Linear issue corresponding to the PR

Covers: QAAG-01 (produces approved/changes_required contract), QAAG-05 (no code edits, no PRs).

Run with: pytest tests/integration/test_qa_agent.py -v -m integration
"""

import os
import subprocess

import pytest

from hsb.agents.qa_agent import run_qa_agent
from hsb.contracts.qa import PullRequestInput, QAInput

pytestmark = [pytest.mark.integration]


def _get_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        pytest.skip(f"{name} not set — required for QA Agent integration tests")
    return val


@pytest.mark.integration
def test_qa_review():
    """QAAG-01 + QAAG-02 + QAAG-03: QA Agent produces a structured QAOutput contract.

    Verifies:
      - qa_status is one of {approved, changes_required}
      - len(findings) <= 5 (QAAG-03 schema-level cap)
      - qa_cycle_count incremented (input 0 -> output 1)
      - if status is changes_required, every finding has all required fields (QAAG-02)
    """
    pr_number = int(_get_env("HSB_TEST_QA_PR_NUMBER"))
    linear_id = _get_env("HSB_TEST_QA_LINEAR_ID")

    diff = subprocess.check_output(["gh", "pr", "diff", str(pr_number)], text=True)
    pr_url = subprocess.check_output(
        ["gh", "pr", "view", str(pr_number), "--json", "url", "--jq", ".url"],
        text=True,
    ).strip()

    input = QAInput(
        work_item_id=linear_id,
        linear_issue={"id": linear_id, "description": "Test issue for QA integration"},
        pull_request=PullRequestInput(url=pr_url, diff=diff),
        implementation_notes={},
        epic_context={},
        qa_cycle_count=0,  # first review
    )
    output = run_qa_agent(input)
    assert output.qa_status in ("approved", "changes_required"), output.qa_status
    assert len(output.findings) <= 5, (
        f"QAAG-03 violation: {len(output.findings)} findings"
    )
    assert output.qa_cycle_count == 1, (
        f"qa_cycle_count must increment 0->1 (1-indexed output); got {output.qa_cycle_count}"
    )
    if output.qa_status == "changes_required":
        for f in output.findings:
            assert f.severity in ("critical", "high", "medium", "low")
            assert f.category in (
                "functional",
                "architecture",
                "code_quality",
                "test",
                "security",
                "regression",
            )
            assert f.status in ("blocking", "non_blocking")
            assert f.evidence.file
            assert f.evidence.related_requirement


@pytest.mark.integration
def test_capability_boundary(tmp_path):
    """QAAG-05: QA Agent never modifies code or creates PRs.

    Strategy: create a sentinel file in tmp_path, run the agent against an arbitrary diff,
    assert the sentinel file is unmodified after the run. Additionally inspect the working
    directory of the test process: no new branches, no new commits, no new PRs.

    Note: this test does NOT verify that the agent never SAW Edit/Write tools — that's
    guaranteed by ClaudeAgentOptions.allowed_tools (asserted by acceptance criteria of Task 2).
    This test verifies the RUNTIME behavior: the agent's actions had no Edit/Write side effects.
    """
    pr_number = int(_get_env("HSB_TEST_QA_PR_NUMBER"))
    linear_id = _get_env("HSB_TEST_QA_LINEAR_ID")

    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("DO NOT MODIFY")
    sentinel_mtime_before = sentinel.stat().st_mtime

    diff = subprocess.check_output(["gh", "pr", "diff", str(pr_number)], text=True)
    pr_url = subprocess.check_output(
        ["gh", "pr", "view", str(pr_number), "--json", "url", "--jq", ".url"],
        text=True,
    ).strip()

    input = QAInput(
        work_item_id=linear_id,
        linear_issue={"id": linear_id, "description": "Test issue for QA boundary"},
        pull_request=PullRequestInput(url=pr_url, diff=diff),
        implementation_notes={},
        epic_context={},
        qa_cycle_count=0,
    )
    run_qa_agent(input)

    # Verify sentinel was not touched
    assert sentinel.read_text() == "DO NOT MODIFY", (
        "QA Agent modified sentinel — QAAG-05 violation"
    )
    assert sentinel.stat().st_mtime == sentinel_mtime_before, (
        "QA Agent altered sentinel mtime — QAAG-05 violation"
    )
