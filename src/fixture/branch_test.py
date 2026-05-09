"""Test fixture for LIN-TEST-201: branch naming validation.

This file serves as a fixture artifact for Git Agent integration tests.
It demonstrates the GITA-01 requirement: branches match feature/LIN-{id}-{slug}.
"""


def validate_branch_name(branch: str) -> bool:
    """Check if branch name follows feature/LIN-{id}-{slug} pattern."""
    import re

    pattern = r"^feature/LIN-\d+-[a-z0-9-]+$"
    return bool(re.match(pattern, branch))


if __name__ == "__main__":
    print("LIN-TEST-201: Branch naming validation test fixture")
