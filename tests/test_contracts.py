"""Pydantic contract validation tests — FOUND-03 schema-drift detection.

Reference Dataset scenarios 9 and 10 plus edge cases that prove
extra="forbid", regex constraints, and the model_validator all fire.
"""
import pytest
from pydantic import ValidationError
from hsb.contracts.linear import LinearInput, LinearOutput
from hsb.contracts.base import RuntimeEnvelope, ErrorContract


def test_valid_output_passes(valid_linear_output):
    result = LinearOutput.model_validate(valid_linear_output)
    assert result.result == "success"
    assert result.linear_entities[0].id == "LIN-123"
    assert result.linear_entities[0].type == "task"


def test_failed_output_passes(failed_linear_output):
    result = LinearOutput.model_validate(failed_linear_output)
    assert result.result == "failed"
    assert result.error is not None
    assert "tool_failure" in result.error


@pytest.mark.parametrize("bad_payload,case_id", [
    # Scenario 9: raw UUID instead of LIN-xxx (regex on id)
    ({"operation": "create", "result": "success",
      "linear_entities": [{"id": "abc123-uuid", "type": "task",
                            "url": "https://linear.app/x/LIN-1"}],
      "error": None}, "uuid_id_rejected"),
    # Scenario 10: extra undeclared field at envelope level (extra=forbid)
    ({"operation": "create", "result": "success", "linear_entities": [],
      "error": None, "unexpected_field": "should_fail"}, "extra_field_rejected"),
    # Edge: failed result without error message (model_validator)
    ({"operation": "create", "result": "failed", "linear_entities": [],
      "error": None}, "failed_without_error_rejected"),
    # Edge: wrong url domain (regex on url)
    ({"operation": "create", "result": "success",
      "linear_entities": [{"id": "LIN-1", "type": "task",
                            "url": "https://gitlab.com/x"}],
      "error": None}, "wrong_url_domain_rejected"),
    # Edge: invalid type literal
    ({"operation": "create", "result": "success",
      "linear_entities": [{"id": "LIN-1", "type": "invalid_type",
                            "url": "https://linear.app/x/LIN-1"}],
      "error": None}, "invalid_type_literal_rejected"),
])
def test_invalid_output_raises(bad_payload, case_id):
    with pytest.raises(ValidationError):
        LinearOutput.model_validate(bad_payload)


def test_input_extra_forbidden():
    with pytest.raises(ValidationError):
        LinearInput.model_validate({
            "operation": "create",
            "payload": {},
            "extra_field": "should_fail",
        })


def test_runtime_envelope_extra_forbidden():
    with pytest.raises(ValidationError):
        RuntimeEnvelope.model_validate({
            "execution_id": "uuid-1",
            "requested_by": "human",
            "skill": "linear-system-of-record",
            "agent": "linear",
            "input": {},
            "status": "success",
            "extra_field": "should_fail",
        })


def test_error_contract_invalid_error_type():
    with pytest.raises(ValidationError):
        ErrorContract.model_validate({
            "status": "failed",
            "error_type": "unknown_type",
            "message": "x",
            "recoverable": False,
            "required_action": "retry",
        })


def test_runtime_envelope_happy_path():
    envelope = RuntimeEnvelope.model_validate({
        "execution_id": "uuid-1",
        "requested_by": "human",
        "skill": "linear-system-of-record",
        "agent": "linear",
        "input": {"foo": "bar"},
        "status": "success",
    })
    assert envelope.errors == []
    assert envelope.output is None
    assert envelope.next_recommended_action is None
