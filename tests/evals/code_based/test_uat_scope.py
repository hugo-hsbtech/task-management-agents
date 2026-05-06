"""B3 banned-token eval (AI-SPEC §5): UAT findings must not include
code-quality or scope-creep terms."""
import re

import pytest

from hsb.contracts.uat import UATResult, UATScenario

# AI-SPEC §5 B3 banned tokens (case-insensitive). Scope-creep indicators.
BANNED_TOKENS = [
    r"\brefactor\b",
    r"\bcode quality\b",
    r"\bnaming\b",
    r"\bstyle\b",
    r"\blinter?\b",
    r"\binefficient\b",
    r"\bshould also handle\b",
    r"\bfuture edge case\b",
]
BANNED_RE = re.compile("|".join(BANNED_TOKENS), re.IGNORECASE)


def has_banned_token(text: str) -> bool:
    return bool(BANNED_RE.search(text or ""))


def violations_in_result(result: UATResult) -> list[str]:
    violations = []
    for s in result.scenarios:
        for field in (s.evidence, s.finding or ""):
            if has_banned_token(field):
                violations.append(f"{s.criterion_id}: '{field[:80]}'")
    return violations


def _scenario(criterion_id: str, status: str, finding: str | None) -> UATScenario:
    return UATScenario(
        criterion_id=criterion_id,
        criterion_text="x",
        status=status,
        evidence="The system behaves as expected during runtime",
        finding=finding,
    )


def test_uat_findings_contain_no_code_quality_terms():
    good = UATResult(
        user_story_id="LIN-1",
        overall_status="approved",
        scenarios=[_scenario("AC-1", "pass", None)],
        uat_cycle=1,
    )
    assert violations_in_result(good) == []


def test_uat_findings_with_refactor_term_flagged():
    bad = UATResult(
        user_story_id="LIN-1",
        overall_status="changes_required",
        scenarios=[_scenario("AC-1", "fail", "The code should refactor the login handler")],
        uat_cycle=1,
    )
    assert violations_in_result(bad), "B3 violated: 'refactor' must be flagged"


@pytest.mark.parametrize(
    "token",
    [
        "code quality",
        "Refactor",
        "naming",
        "style",
        "linter",
        "inefficient",
        "should also handle",
        "future edge case",
    ],
)
def test_uat_banned_token_each_flagged(token):
    bad = UATResult(
        user_story_id="LIN-1",
        overall_status="changes_required",
        scenarios=[_scenario("AC-1", "fail", f"This {token} thing is bad")],
        uat_cycle=1,
    )
    assert violations_in_result(bad), (
        f"B3 violated: token '{token}' was not flagged"
    )
