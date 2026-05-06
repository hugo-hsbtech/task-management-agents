"""Pydantic v2 contract models for the Linear System of Record Agent.
These MUST exactly mirror the JSON schemas in agents/AGENT-CONTRACTS.md.
Do not add or remove fields without updating AGENT-CONTRACTS.md first.
"""
from __future__ import annotations
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class LinearOperation(str, Enum):
    create = "create"
    update = "update"
    read = "read"
    link = "link"
    comment = "comment"
    create_subtasks = "create_subtasks"


class LinearInput(BaseModel):
    """Input contract for the Linear System of Record Agent.
    Mirrors AGENT-CONTRACTS.md §2 Input exactly.
    """
    operation: LinearOperation
    payload: dict  # Operation-specific; validated by operation-specific models

    model_config = {"extra": "forbid"}


class LinearEntity(BaseModel):
    """A Linear entity returned after a create/update operation."""
    id: str = Field(..., pattern=r"^LIN-\d+$")
    type: Literal["epic", "user_story", "task", "subtask"]
    url: str = Field(..., pattern=r"^https://linear\.app/")

    model_config = {"extra": "forbid"}


class LinearOutput(BaseModel):
    """Output contract for the Linear System of Record Agent.
    Mirrors AGENT-CONTRACTS.md §2 Output exactly.
    """
    operation: str
    result: Literal["success", "failed"]
    linear_entities: list[LinearEntity] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def failed_must_have_error(self) -> "LinearOutput":
        if self.result == "failed" and not self.error:
            raise ValueError("failed result must include error message")
        return self

    model_config = {"extra": "forbid"}
