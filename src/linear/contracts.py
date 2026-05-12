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


class LinearItemType(StrEnum):
    epic = "epic"
    user_story = "user_story"
    task = "task"
    subtask = "subtask"


class LinearItemInput(BaseModel):
    """A pre-planned work item to be created or updated in Linear."""

    id: str | None = Field(None, pattern=r"^LIN-\d+$")
    type: LinearItemType
    title: str
    description: str | None = None
    parent_id: str | None = Field(None, pattern=r"^LIN-\d+$")

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
    """Input contract for the Linear System of Record Agent.

    The caller is responsible for decomposing the plan into epics, user
    stories, tasks, and subtasks before calling the agent. The agent
    only persists the pre-planned items into Linear.
    """

    operation: LinearOperation
    project: Project
    items: list[LinearItemInput] = Field(
        ..., min_length=1, description="Pre-planned work items to persist."
    )

    model_config = {"extra": "forbid"}


class LinearEntity(BaseModel):
    """A Linear entity after it has been persisted (id and url are known)."""

    id: str = Field(..., pattern=r"^LIN-\d+$")
    type: LinearItemType
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
