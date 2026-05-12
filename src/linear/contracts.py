"""Pydantic v2 contract models for the Linear System of Record Agent."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class LinearOperation(StrEnum):
    create = "create"
    update = "update"
    read = "read"
    link = "link"
    comment = "comment"
    create_subtasks = "create_subtasks"


class Plan(BaseModel):
    """The plan to be persisted into Linear."""

    content: bytes
    stacks: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class Project(BaseModel):
    """A Linear project."""

    url: HttpUrl | None = Field(None, pattern=r"^https://linear\.app/")
    name: str | None = None

    @model_validator(mode="before")
    def must_have(cls, values):
        if values.get("url") is None and values.get("name") is None:
            raise ValueError("Either url or name must be provided")
        return values


class LinearInput(BaseModel):
    """Input contract for the Linear System of Record Agent."""

    operation: LinearOperation
    project: Project
    plan: Plan

    model_config = {"extra": "forbid"}


class LinearEntity(BaseModel):
    """A Linear entity returned after a create/update operation."""

    id: str = Field(..., pattern=r"^LIN-\d+$")
    type: Literal["epic", "user_story", "task", "subtask"]
    url: str = Field(..., pattern=r"^https://linear\.app/")

    model_config = {"extra": "forbid"}


class LinearOutput(BaseModel):
    """Output contract for the Linear System of Record Agent."""

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
