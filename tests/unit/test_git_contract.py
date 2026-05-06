"""Unit tests for hsb.contracts.git + capability-boundary check on git SKILL.md.

Covers: GITA-01 (branch naming regex), GITA-03 (PR title regex),
GITA-05 (no `merge` / no `--force` without `--lease` in SKILL.md allowed-tools).
"""
import re
from pathlib import Path

import pytest

contracts = pytest.importorskip(
    "hsb.contracts.git",
    reason="Wave 1 Plan 04 (Git Agent) has not yet created hsb.contracts.git",
)

from pydantic import ValidationError  # noqa: E402

GitOutput = contracts.GitOutput

BRANCH_PATTERN = re.compile(r"^feature/LIN-\d+-[a-z0-9-]+$")
PR_TITLE_PATTERN = re.compile(r"^\[LIN-\d+\]")


def test_valid_git_output_passes():
    """GITA-01 + GITA-03: minimal valid GitOutput accepts."""
    output = GitOutput.model_validate({
        "work_item_id": "LIN-123",
        "branch": "feature/LIN-123-add-auth",
        "commits": ["abc123"],
        "pull_request": {
            "url": "https://github.com/org/repo/pull/42",
            "title": "[LIN-123] Add auth endpoint",
            "base": "epic/LIN-100",
            "head": "feature/LIN-123-add-auth",
        },
    })
    assert BRANCH_PATTERN.match(output.branch), (
        f"Branch '{output.branch}' violates GITA-01"
    )
    assert PR_TITLE_PATTERN.match(output.pull_request.title), (
        f"PR title '{output.pull_request.title}' violates GITA-03"
    )


def test_branch_naming_regex():
    """GITA-01: feature/LIN-{id}-{slug} pattern enforced."""
    valid = ["feature/LIN-1-slug", "feature/LIN-999-long-slug-name"]
    invalid = [
        "LIN-123-slug",        # missing feature/ prefix
        "feature/lin-123-slug",  # lowercase LIN
        "feature/LIN-123",     # missing slug
    ]
    for b in valid:
        assert BRANCH_PATTERN.match(b), f"Should be valid: {b}"
    for b in invalid:
        assert not BRANCH_PATTERN.match(b), f"Should be invalid: {b}"


def test_pr_title_regex():
    """GITA-03: PR title MUST start with [LIN-{id}]."""
    valid = ["[LIN-123] Add auth", "[LIN-1] x"]
    invalid = ["LIN-123 Add auth", "[lin-123] x", "Add auth"]
    for t in valid:
        assert PR_TITLE_PATTERN.match(t), f"Should be valid: {t}"
    for t in invalid:
        assert not PR_TITLE_PATTERN.match(t), f"Should be invalid: {t}"


def test_git_output_extra_field_rejected():
    """GITA-05: extra='forbid' rejects 'merged_to_main' or any non-spec field."""
    with pytest.raises(ValidationError):
        GitOutput.model_validate({
            "work_item_id": "LIN-123",
            "branch": "feature/LIN-123-add-auth",
            "commits": [],
            "pull_request": {
                "url": "x",
                "title": "[LIN-123] x",
                "base": "epic/LIN-100",
                "head": "feature/LIN-123-add-auth",
            },
            "merged_to_main": True,  # GITA-05 violation
        })


def test_no_merge_in_allowed_tools():
    """GITA-05: .claude/skills/git-pr-management/SKILL.md allowed-tools must NOT
    include `Bash(git merge *)` or `Bash(git push --force *)` (only --force-with-lease).
    Wave 1 Plan 04 creates this SKILL.md — test skips until then.
    """
    skill_path = Path(".claude/skills/git-pr-management/SKILL.md")
    if not skill_path.exists():
        pytest.skip("Wave 1 Plan 04 has not yet created git-pr-management SKILL.md")
    content = skill_path.read_text()
    # Frontmatter check: forbidden tool fragments must be absent
    forbidden = [
        "Bash(git merge",
        "git push --force *)",  # bare --force without --lease
        "git push --force)",
        "git push -f",
    ]
    for needle in forbidden:
        assert needle not in content, (
            f"GITA-05 violation: '{needle}' must NOT appear in git SKILL.md allowed-tools"
        )
    # Required affirmative: --force-with-lease must be present
    assert "git push --force-with-lease" in content, (
        "GITA-05: SKILL.md must allow git push --force-with-lease (not --force)"
    )
