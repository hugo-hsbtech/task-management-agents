"""B1 coverage eval (AI-SPEC §5): UATResult.scenarios covers every acceptance criterion.

Also includes UAT contract schema unit tests since they share fixtures with
the coverage eval (kept under ``tests/evals/code_based/`` rather than
``tests/unit/`` to avoid a separate package).
"""
import pytest
from pydantic import ValidationError

from hsb.contracts.uat import UATResult, UATScenario


def make_result(
    criterion_ids: list[str],
    overall_status: str = "approved",
) -> UATResult:
    return UATResult(
        user_story_id="LIN-1",
        overall_status=overall_status,
        scenarios=[
            UATScenario(
                criterion_id=cid,
                criterion_text=f"Criterion {cid}",
                status="pass",
                evidence="Observed expected behavior in PR runtime test",
            )
            for cid in criterion_ids
        ],
        uat_cycle=1,
    )


def coverage_complete(result: UATResult, acceptance_criteria: list[str]) -> bool:
    """B1 coverage check from AI-SPEC §5 dimension B1."""
    expected = {f"AC-{i + 1}" for i in range(len(acceptance_criteria))}
    actual = {s.criterion_id for s in result.scenarios}
    return actual == expected


def test_uat_scenarios_cover_every_acceptance_criterion():
    criteria = ["User logs in", "User sees dashboard", "User logs out"]
    result = make_result(["AC-1", "AC-2", "AC-3"])
    assert coverage_complete(result, criteria) is True


def test_uat_scenarios_with_missing_ac_fails_coverage():
    criteria = ["A", "B", "C"]
    result = make_result(["AC-1", "AC-2"])  # AC-3 missing
    assert coverage_complete(result, criteria) is False


def test_uat_scenarios_with_extra_ac_fails_coverage():
    criteria = ["A"]
    result = make_result(["AC-1", "AC-2"])  # AC-2 not expected
    assert coverage_complete(result, criteria) is False


# ----- UAT contract schema tests -----


def test_evidence_min_length_enforced():
    with pytest.raises(ValidationError):
        UATScenario(
            criterion_id="AC-1",
            criterion_text="x",
            status="pass",
            evidence="short",
        )


def test_uat_cycle_ge_1_enforced():
    with pytest.raises(ValidationError):
        UATResult(
            user_story_id="LIN-1",
            overall_status="approved",
            scenarios=[],
            uat_cycle=0,
        )


def test_scope_violations_defaults_to_empty_list():
    r = UATResult(
        user_story_id="LIN-1",
        overall_status="approved",
        scenarios=[],
        uat_cycle=1,
    )
    assert r.scope_violations == []


def test_uat_extra_fields_rejected():
    with pytest.raises(ValidationError):
        UATResult(
            user_story_id="LIN-1",
            overall_status="approved",
            scenarios=[],
            uat_cycle=1,
            rogue_field="x",
        )


def test_uat_status_literal_enforced():
    with pytest.raises(ValidationError):
        UATScenario(
            criterion_id="AC-1",
            criterion_text="x",
            status="invalid",
            evidence="The system behaves as expected",
        )
