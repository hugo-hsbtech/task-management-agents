"""Pydantic v2 contract models for the Linear System of Record Agent."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class LinearOperation(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    READ = "read"
    LINK = "link"
    COMMENT = "comment"
    CREATE_SUBTASKS = "create_subtasks"


class LinearItemType(StrEnum):
    epic = "epic"
    user_story = "user_story"
    task = "task"
    subtask = "subtask"


class LinearItemStatus(StrEnum):
    """A Linear item status."""

    BACKLOG = "Backlog"
    PLANNED = "Planned"
    IN_PROGRESS = "In Progress"
    IN_REVIEW = "In Review"
    DONE = "Done"


class Project(BaseModel):
    """A Linear project."""

    url: HttpUrl | None = Field(None, pattern=r"^https://linear\.app/")
    name: str | None = None

    @model_validator(mode="before")
    def must_have(cls, values):
        if values.get("url") is None and values.get("name") is None:
            raise ValueError("Either url or name must be provided")
        return values


class LinearEntity(BaseModel):
    """A work item — used both as input (to be persisted) and output (after persistence).

    On input: id and url are absent (item does not exist yet).
    On output: id and url are populated by the agent after creation/update.
    """

    type: LinearItemType
    id: str | None = Field(None, pattern=r"^LIN-\d+$")
    url: str | None = Field(None, pattern=r"^https://linear\.app/")

    title: str
    description: str | None = None
    acceptance_criteria: str | None = None
    priority: int | None = None
    state: LinearItemStatus | None = None

    model_config = {"extra": "forbid"}


class LinearInput(BaseModel):
    """Input contract for the Linear System of Record Agent.

    The caller is responsible for decomposing the plan into epics, user
    stories, tasks, and subtasks before calling the agent. The agent
    only persists the pre-planned items into Linear.
    """

    operation: LinearOperation
    project: Project
    items: list[LinearEntity] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class LinearOutput(BaseModel):
    """Output contract for the Linear System of Record Agent."""

    operation: LinearOperation
    result: Literal["success", "failed"]
    items: list[LinearEntity] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def failed_must_have_error(self) -> "LinearOutput":
        if self.result == "failed" and not self.error:
            raise ValueError("failed result must include error message")
        return self

    model_config = {"extra": "forbid"}
