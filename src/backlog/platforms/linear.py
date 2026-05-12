"""Linear platform implementation for backlog generation."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import BaseModel, Field

from libs.linear.schemas import Issue, IssueInput, IssueUpdateInput
from llm_providers.tools import ToolPolicy
from tools.linear import LinearTools

if TYPE_CHECKING:
    from backlog.contracts import BacklogOutput, IssuePlan


class IssueResult(BaseModel):
    """Outcome of one issue write operation within execute()."""

    action: Literal["create", "reuse", "update"]
    issue: Issue

    model_config = {"frozen": True}


LINEAR_BACKLOG_TOOL_NAMES: tuple[str, ...] = (
    "linear_create_issue",
    "linear_update_issue",
    "linear_update_project",
    "linear_list_issues",
    "linear_get_issue",
    "linear_create_issue_relation",
)


class LinearPlatform(BaseModel):
    """Linear-specific backlog destination."""

    platform_name: ClassVar[str] = "linear"

    team_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)

    model_config = {"extra": "forbid"}

    def issue_defaults(self) -> dict[str, str]:
        return {
            "team_id": self.team_id,
            "project_id": self.project_id,
        }

    def tool_policy(self, *, api_key: str) -> ToolPolicy:
        tools = LinearTools(api_key=api_key)
        specs = tools.get_tool_specs(list(LINEAR_BACKLOG_TOOL_NAMES))
        return ToolPolicy(
            allowed=tuple(spec.name for spec in specs),
            custom=specs,
        )

    async def execute(
        self,
        output: BacklogOutput,
        *,
        api_key: str,
    ) -> list[IssueResult]:
        """Create/update Linear issues from a validated BacklogOutput.

        Title-idempotent: if an issue with the same title already exists in the
        configured project it is reused instead of duplicated.
        """
        from backlog.contracts import IssueAction

        tools = LinearTools(api_key=api_key)
        existing_by_title = await self._list_existing_by_title(tools)

        results: list[IssueResult] = []
        for issue in output.issues:
            if (
                issue.action == IssueAction.create
                and issue.fields.title in existing_by_title
            ):
                result = IssueResult(
                    action="reuse",
                    issue=existing_by_title[issue.fields.title],
                )
            elif issue.action == IssueAction.update:
                issue_id = issue.fields.platform_fields["issue_id"]
                raw = await tools._handle_update_issue(
                    {
                        "issue_id": issue_id,
                        **_update_payload(issue).model_dump(
                            mode="json", by_alias=False
                        ),
                    }
                )
                result = IssueResult(action="update", issue=Issue.model_validate(raw))
            else:
                raw = await tools._handle_create_issue(
                    _create_payload(issue).model_dump(mode="json", by_alias=False)
                )
                result = IssueResult(action="create", issue=Issue.model_validate(raw))

            results.append(result)

        await self._apply_relations(tools, output.issues, results)
        return results

    async def _apply_relations(
        self,
        tools: LinearTools,
        plans: list[IssuePlan],
        results: list[IssueResult],
    ) -> None:
        """Create issue relations after all issues have been written.

        Resolves target_title to the corresponding result issue ID so relations
        are wired correctly regardless of creation order.
        """
        id_by_title: dict[str, str] = {
            r.issue.title: r.issue.id for r in results if r.issue.id and r.issue.title
        }

        for plan, result in zip(plans, results, strict=False):
            if not plan.relations or not result.issue.id:
                continue
            for relation in plan.relations:
                target_id = id_by_title.get(relation.target_title)
                if not target_id:
                    continue
                await tools._handle_create_issue_relation(
                    {
                        "issue_id": result.issue.id,
                        "related_issue_id": target_id,
                        "type": relation.type,
                    }
                )

    async def validate_target(self, *, api_key: str) -> None:
        """Validate that the configured Linear team/project exist and are accessible."""
        tools = LinearTools(api_key=api_key)

        team = await tools._handle_get_team({"team_id": self.team_id})
        if "error" in team:
            raise ValueError(
                f"Configured Linear team does not exist or is inaccessible: "
                f"{self.team_id!r}"
            )

        project = await tools._handle_get_project({"project_id": self.project_id})
        if "error" in project:
            raise ValueError(
                f"Configured Linear project does not exist or is inaccessible: "
                f"{self.project_id!r}"
            )

    async def _list_existing_by_title(
        self,
        tools: LinearTools,
    ) -> dict[str, Issue]:
        try:
            response = await tools._handle_list_issues({"project_id": self.project_id})
        except ValueError as exc:
            raise ValueError(
                f"Unable to list Linear issues for project_id={self.project_id!r}. "
                "Check LINEAR_PROJECT_ID in settings.linear and ensure the API key "
                "can access that project."
            ) from exc
        return {
            issue["title"]: Issue.model_validate(issue)
            for issue in response.get("issues", [])
            if isinstance(issue, dict) and isinstance(issue.get("title"), str)
        }


def _create_payload(issue: IssuePlan) -> IssueInput:
    fields = issue.fields
    return IssueInput(
        title=fields.title,
        description=fields.description,
        team_id=fields.platform_fields["team_id"],
        project_id=fields.platform_fields["project_id"],
        priority=fields.priority,
        parent_id=fields.parent_id,
    )


def _update_payload(issue: IssuePlan) -> IssueUpdateInput:
    fields = issue.fields
    issue_id = fields.platform_fields.get("issue_id")
    if not issue_id:
        raise ValueError("update action requires fields.platform_fields.issue_id")
    return IssueUpdateInput(
        title=fields.title,
        description=fields.description,
        priority=fields.priority,
    )
