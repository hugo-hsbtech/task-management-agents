"""Unit tests for hsb.contracts.builder (Phase 2 Plan 03).

Covers: BLDR-03 (output contract validity), BLDR-04 (extra-field schema guard
against accidentally-emitted git/Linear fields).
"""

import pytest

contracts = pytest.importorskip(
    "hsb.contracts.builder",
    reason="Wave 1 Plan 03 (Builder Agent) has not yet created hsb.contracts.builder",
)

from pydantic import ValidationError  # noqa: E402

BuilderOutput = contracts.BuilderOutput


def test_valid_builder_output_passes():
    """BLDR-03: minimal valid BuilderOutput accepts."""
    output = BuilderOutput.model_validate(
        {
            "work_item_id": "LIN-123",
            "implementation_status": "completed",
            "summary": "Implemented feature X",
            "files_changed": [{"path": "src/x.py", "change_summary": "added X"}],
            "validation": {
                "build": "passed",
                "tests": "passed",
                "lint": "passed",
                "typecheck": "not_run",
            },
            "implementation_notes": {
                "decisions": [],
                "assumptions": [],
                "risks": [],
                "qa_notes": [],
            },
        }
    )
    assert output.implementation_status == "completed"


def test_invalid_validation_status_fails():
    """BLDR-03: validation values are restricted to passed|failed|not_run."""
    with pytest.raises(ValidationError):
        BuilderOutput.model_validate(
            {
                "work_item_id": "LIN-123",
                "implementation_status": "completed",
                "summary": "s",
                "files_changed": [],
                "validation": {
                    "build": "unknown",  # invalid Literal
                    "tests": "passed",
                    "lint": "passed",
                    "typecheck": "not_run",
                },
                "implementation_notes": {
                    "decisions": [],
                    "assumptions": [],
                    "risks": [],
                    "qa_notes": [],
                },
            }
        )


def test_builder_output_extra_field_rejected():
    """BLDR-04: extra='forbid' guards against Builder leaking git/Linear fields."""
    with pytest.raises(ValidationError):
        BuilderOutput.model_validate(
            {
                "work_item_id": "LIN-123",
                "implementation_status": "completed",
                "summary": "s",
                "files_changed": [],
                "git_branch": "feature/X",  # BLDR-04 violation — must reject
                "validation": {
                    "build": "passed",
                    "tests": "passed",
                    "lint": "passed",
                    "typecheck": "not_run",
                },
                "implementation_notes": {
                    "decisions": [],
                    "assumptions": [],
                    "risks": [],
                    "qa_notes": [],
                },
            }
        )
