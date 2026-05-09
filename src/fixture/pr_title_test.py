"""Test fixture for LIN-TEST-203: PR title validation.

This file serves as a fixture artifact for Git Agent integration tests.
It demonstrates the GITA-03 requirement: PR titles use [LIN-{id}] prefix format.
"""


def format_pr_title(issue_id: str, description: str) -> str:
    """Format PR title with issue ID prefix per GITA-03."""
    return f"[{issue_id}] {description}"


def validate_pr_title(title: str) -> bool:
    """Check if PR title follows [LIN-{id}] prefix pattern."""
    import re

    pattern = r"^\[LIN-\d+\]"
    return bool(re.match(pattern, title))


if __name__ == "__main__":
    print("LIN-TEST-203: PR title validation test fixture")
