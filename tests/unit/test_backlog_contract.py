"""Unit tests for hsb.contracts.backlog (Phase 2 Plan 02).

Wave 0 scaffold — uses pytest.importorskip so tests skip cleanly until Plan 02
creates src/hsb/contracts/backlog.py. Wave 1 plan MUST NOT rename test functions —
02-VALIDATION.md commands match these exact names.

Covers: BKPK-01, BKPK-05 (schema validity + traceability + extra-field guard).
"""

import pytest

contracts = pytest.importorskip(
    "hsb.contracts.backlog",
    reason="Wave 1 Plan 02 (Backlog Agent) has not yet created hsb.contracts.backlog",
)

from pydantic import ValidationError  # noqa: E402

BacklogInput = contracts.BacklogInput
BacklogOutput = contracts.BacklogOutput


def test_valid_backlog_output_passes():
    """BKPK-01: minimal valid BacklogOutput accepts."""
    output = BacklogOutput.model_validate(
        {
            "epics": [
                {
                    "title": "[EPIC] Test",
                    "description": "desc",
                    "acceptance_criteria": [],
                    "user_stories": [],
                    "tasks": [],
                }
            ],
            "traceability": {"plan_source": "/docs/plan.md"},
        }
    )
    assert output.epics[0].title == "[EPIC] Test"


def test_empty_epics_fails():
    """BKPK-01: BacklogOutput requires at least one EPIC (min_length=1)."""
    with pytest.raises(ValidationError):
        BacklogOutput.model_validate(
            {
                "epics": [],
                "traceability": {"plan_source": "/docs/plan.md"},
            }
        )


def test_extra_field_rejected():
    """BKPK-01: extra='forbid' guards against silent schema drift (Pitfall 4)."""
    with pytest.raises(ValidationError):
        BacklogOutput.model_validate(
            {
                "epics": [
                    {
                        "title": "[EPIC] T",
                        "description": "d",
                        "acceptance_criteria": [],
                        "user_stories": [],
                        "tasks": [],
                    }
                ],
                "traceability": {"plan_source": "/p"},
                "unexpected_field": "boom",
            }
        )


def test_missing_traceability_fails():
    """BKPK-05: traceability is required (per AGENT-CONTRACTS.md §1)."""
    with pytest.raises(ValidationError):
        BacklogOutput.model_validate(
            {
                "epics": [
                    {
                        "title": "[EPIC] T",
                        "description": "d",
                        "acceptance_criteria": [],
                        "user_stories": [],
                        "tasks": [],
                    }
                ],
            }
        )


def test_backlog_input_requires_plan_source():
    """BKPK-01 + D-02: BacklogInput.plan_source is required (no default)."""
    with pytest.raises(ValidationError):
        BacklogInput.model_validate(
            {
                "project_context": {"name": "x", "repository": "y"},
            }
        )
