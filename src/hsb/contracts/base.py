"""Standard runtime envelope and error contract.
Mirrors AGENT-CONTRACTS.md §Standard Runtime Envelope and §Error Contract exactly.
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from hsb.contracts.linear import LinearOutput


class RuntimeEnvelope(BaseModel):
    """Standard envelope wrapping every agent invocation result."""
    execution_id: str  # UUID
    requested_by: Literal["global_orchestrator", "work_item_orchestrator", "human"]
    skill: str
    agent: str
    input: dict
    output: LinearOutput | None = None
    status: Literal["success", "failed", "blocked"]
    errors: list[str] = Field(default_factory=list)
    next_recommended_action: str | None = None

    model_config = {"extra": "forbid"}


class ErrorContract(BaseModel):
    """Error contract. Mirrors AGENT-CONTRACTS.md §Error Contract exactly."""
    status: Literal["failed"]
    error_type: Literal[
        "missing_input",
        "invalid_state",
        "tool_failure",
        "validation_failure",
        "blocked_dependency",
    ]
    message: str
    recoverable: bool
    required_action: str

    model_config = {"extra": "forbid"}
