"""Unit tests for hsb.contracts.qa — schema + cycle-cap model_validator.

Covers: QAAG-02 (finding fields), QAAG-03 (max 5 findings),
QAAG-04 (cycle cap at 3 → approved + tech_debt_annotation),
QAAG-05 (extra-field schema guard).

The model_validator on QAOutput is the LAST line of defense against QA runaway
(Pitfall 2). These tests must NEVER be relaxed.
"""
import pytest

contracts = pytest.importorskip(
    "hsb.contracts.qa",
    reason="Wave 1 Plan 05 (QA Agent) has not yet created hsb.contracts.qa",
)

from pydantic import ValidationError  # noqa: E402

QAOutput = contracts.QAOutput

VALID_FINDING = {
    "title": "Missing null check",
    "severity": "high",
    "category": "functional",
    "status": "blocking",
    "problem": "x is None causes crash",
    "evidence": {
        "file": "src/x.py",
        "component": "XClass",
        "location": "line 42",
        "related_requirement": "LIN-123 AC-1",
    },
    "expected_behavior": "Returns 0 on None input",
    "actual_behavior": "Raises TypeError",
    "suggested_fix": "Add null guard",
}

VALID_APPROVED_OUTPUT = {
    "work_item_id": "LIN-123",
    "qa_status": "approved",
    "qa_cycle_count": 1,
    "summary": "No issues found",
    "findings": [],
}


def test_valid_approved_output_passes():
    """QAAG-01: minimal approved QAOutput accepts."""
    output = QAOutput.model_validate(VALID_APPROVED_OUTPUT)
    assert output.qa_status == "approved"


def test_finding_fields():
    """QAAG-02: a single finding with all required fields validates."""
    output = QAOutput.model_validate({
        **VALID_APPROVED_OUTPUT,
        "qa_status": "changes_required",
        "findings": [VALID_FINDING],
    })
    f = output.findings[0]
    assert f.severity == "high"
    assert f.category == "functional"
    assert f.status == "blocking"
    assert f.evidence.file == "src/x.py"


def test_findings_max_length():
    """QAAG-03: hard cap of 5 findings (Field(max_length=5))."""
    with pytest.raises(ValidationError):
        QAOutput.model_validate({
            **VALID_APPROVED_OUTPUT,
            "qa_status": "changes_required",
            "findings": [VALID_FINDING] * 6,
        })


def test_cycle_cap_validator():
    """QAAG-04: at qa_cycle_count=3 with status=changes_required → ValidationError."""
    with pytest.raises(ValidationError, match="qa_cycle_count >= 3"):
        QAOutput.model_validate({
            "work_item_id": "LIN-123",
            "qa_status": "changes_required",
            "qa_cycle_count": 3,
            "summary": "Still has issues",
            "findings": [VALID_FINDING],
        })


def test_cycle_cap_at_3_requires_tech_debt_annotation():
    """QAAG-04: approved at cycle 3 without annotation → ValidationError."""
    with pytest.raises(ValidationError, match="tech_debt_annotation required"):
        QAOutput.model_validate({
            "work_item_id": "LIN-123",
            "qa_status": "approved",
            "qa_cycle_count": 3,
            "summary": "Approved with tech debt",
            "findings": [],
        })


def test_cycle_cap_at_3_approved_with_annotation_passes():
    """QAAG-04: approved at cycle 3 with annotation is valid."""
    output = QAOutput.model_validate({
        "work_item_id": "LIN-123",
        "qa_status": "approved",
        "qa_cycle_count": 3,
        "summary": "Approved on 3rd cycle",
        "findings": [],
        "tech_debt_annotation": "Known limitation: edge case deferred to LIN-200",
    })
    assert output.qa_status == "approved"
    assert output.tech_debt_annotation is not None


def test_qa_output_extra_field_rejected():
    """QAAG-05: extra='forbid' rejects accidental git/code-edit fields."""
    with pytest.raises(ValidationError):
        QAOutput.model_validate({
            **VALID_APPROVED_OUTPUT,
            "git_branch_created": "feature/x",
        })
