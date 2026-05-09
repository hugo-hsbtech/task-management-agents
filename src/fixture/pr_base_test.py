"""Test fixture for LIN-TEST-202: PR base branch validation.

This file serves as a fixture artifact for Git Agent integration tests.
It demonstrates the GITA-02 + D-07 requirement: task PRs target the EPIC branch directly,
not main or other task branches.
"""


def get_pr_base(epic_id: str) -> str:
    """Return the correct PR base branch for a given epic."""
    # All task PRs target their EPIC branch per D-07
    return f"epic/{epic_id.split('-')[1]}"


def validate_pr_base(base_branch: str, epic_id: str) -> bool:
    """Check if PR base branch targets the EPIC (not main, not another task)."""
    if base_branch == "main":
        return False  # D-07: must NOT target main
    if base_branch.startswith("feature/"):
        return False  # D-07: must NOT target another task branch
    return base_branch.startswith("epic/")


if __name__ == "__main__":
    print("LIN-TEST-202: PR base branch validation test fixture")
