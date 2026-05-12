"""Linear API library wrapping https://pypi.org/project/linear-api/.

Provides high-level service for teams, projects, and issue management.
All types are defined in schemas.py - consumers should NOT import from linear_api directly.
"""

from __future__ import annotations

from libs.linear.linear_client import LinearClient
from libs.linear.schemas import (
    Comment,
    CommentInput,
    CommentUser,
    Issue,
    IssueInput,
    IssueRelation,
    IssueState,
    IssueUpdateInput,
    Label,
    Priority,
    Project,
    ProjectCommentInput,
    ProjectUpdateInput,
    RelatedIssueRef,
    Team,
)

__all__ = [
    "LinearClient",
    "Comment",
    "CommentInput",
    "CommentUser",
    "Issue",
    "IssueInput",
    "IssueRelation",
    "IssueState",
    "IssueUpdateInput",
    "Label",
    "Priority",
    "Project",
    "ProjectCommentInput",
    "ProjectUpdateInput",
    "RelatedIssueRef",
    "Team",
]
