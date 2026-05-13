"""Linear platform implementation for backlog generation."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel, Field

from libs.linear.schemas import Issue, IssueInput, IssueUpdateInput
from llm_providers.tools import ToolPolicy
from tools.linear import LinearTools

if TYPE_CHECKING:
    from backlog.contracts import BacklogOutput, IssuePlan


# Linear's per-user rate limit (~1500 req/hour) is enforced with burst
# tolerance; over-bursts surface from `linear_api` as opaque GraphQL
# "Argument Validation Error" rather than a clean HTTP 429. Pacing every
# write keeps a typical backlog (~50 issues × create + parent + relations)
# safely under the burst threshold without hand-coded 429 retry logic.
LINEAR_WRITE_THROTTLE_SECONDS = 0.4


async def _throttle() -> None:
    await asyncio.sleep(LINEAR_WRITE_THROTTLE_SECONDS)


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

    @property
    def issue_defaults(self) -> dict[str, str]:
        return {
            "team_id": self.team_id,
            "project_id": self.project_id,
        }

    @property
    def api_key(self) -> str:
        """Resolve the Linear API key from settings.linear.

        Kept here (not in the agent) so each platform owns its secret lookup.
        """
        from settings import settings

        secret = settings.linear.api_key
        if secret is None:
            raise ValueError(
                "Platform API key required: set LINEAR_API_KEY in settings.linear"
            )
        return secret.get_secret_value()

    def tool_policy(self, *, api_key: str) -> ToolPolicy:
        tools = LinearTools(api_key=api_key)
        specs = tools.get_tool_specs(list(LINEAR_BACKLOG_TOOL_NAMES))
        return ToolPolicy(
            allowed=tuple(spec.name for spec in specs),
            custom=specs,
        )

    async def execute(self, output: BacklogOutput) -> list[IssueResult]:
        """Create/update Linear issues from a validated BacklogOutput.

        Title-idempotent: if an issue with the same title already exists in the
        configured project it is reused instead of duplicated.
        """
        from backlog.contracts import IssueAction

        if output.platform.platform_name != self.platform_name:
            raise ValueError(
                f"BacklogOutput platform ({output.platform.platform_name!r}) "
                f"does not match {self.platform_name!r}"
            )

        tools = LinearTools(api_key=self.api_key)
        existing_by_title = await self._list_existing_by_title(tools)

        results: list[IssueResult] = []
        real_id_by_temp_id: dict[str, str] = {}

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
                raw = await tools.handle_update_issue(
                    {
                        "issue_id": issue_id,
                        **_update_payload(issue).model_dump(
                            mode="json", by_alias=False
                        ),
                    }
                )
                _raise_if_error(raw, op="update_issue")
                await _throttle()
                result = IssueResult(action="update", issue=Issue.model_validate(raw))
            else:
                raw = await tools.handle_create_issue(
                    _create_payload(issue).model_dump(mode="json", by_alias=False)
                )
                _raise_if_error(raw, op="create_issue")
                await _throttle()
                result = IssueResult(action="create", issue=Issue.model_validate(raw))

            if issue.id and result.issue.id:
                real_id_by_temp_id[issue.id] = result.issue.id

            results.append(result)

        await self._apply_parent_links(
            tools, output.issues, results, real_id_by_temp_id
        )
        await self._apply_relations(tools, output.issues, results)
        # Label application disabled: the upstream Linear SDK's IssueManager
        # no longer exposes `add_label`, so handle_add_label() bubbles up as
        # "'IssueManager' object has no attribute 'add_label'". Re-enable
        # once the SDK regains this method (or we switch to a GraphQL
        # mutation in linear_client.add_label_to_issue).
        # await self._apply_labels(tools, output.issues, results)
        return results

    async def _apply_parent_links(
        self,
        tools: LinearTools,
        plans: list[IssuePlan],
        results: list[IssueResult],
        real_id_by_temp_id: dict[str, str],
    ) -> None:
        """Wire parent_id linkage after all issues have been written.

        The prompt emits ``parent_id`` as a plan-local temp id (matching another
        IssuePlan.id in the same output). Resolution must happen post-create so
        forward references between siblings work regardless of order. Reused
        issues are skipped — preserving whatever parent the caller had set in
        Linear already.
        """
        for plan, result in zip(plans, results, strict=True):
            if result.action == "reuse":
                continue
            parent_temp_id = plan.fields.parent_id
            if not parent_temp_id or not result.issue.id:
                continue
            parent_real_id = real_id_by_temp_id.get(parent_temp_id)
            if not parent_real_id:
                continue
            raw = await tools.handle_update_issue(
                {"issue_id": result.issue.id, "parent_id": parent_real_id}
            )
            _raise_if_error(raw, op="update_issue (parent link)")
            await _throttle()

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

        for plan, result in zip(plans, results, strict=True):
            if not plan.relations or not result.issue.id:
                continue
            for relation in plan.relations:
                target_id = id_by_title.get(relation.target_title)
                if not target_id:
                    continue
                await tools.handle_create_issue_relation(
                    {
                        "issue_id": result.issue.id,
                        "related_issue_id": target_id,
                        "type": relation.type,
                    }
                )
                await _throttle()

    async def _apply_labels(
        self,
        tools: LinearTools,
        plans: list[IssuePlan],
        results: list[IssueResult],
    ) -> None:
        """Apply labels to created/updated issues after the write pass.

        Reused issues are skipped to preserve whatever labels the caller already
        curated in Linear.
        """
        for plan, result in zip(plans, results, strict=True):
            if result.action == "reuse":
                continue
            if not plan.fields.labels or not result.issue.id:
                continue
            for label_name in plan.fields.labels:
                raw = await tools.handle_add_label(
                    {"issue_id": result.issue.id, "label_name": label_name}
                )
                _raise_if_error(raw, op="add_label")

    async def validate_target(self, *, api_key: str) -> None:
        """Validate that the configured Linear team/project exist and are accessible."""
        tools = LinearTools(api_key=api_key)

        team = await tools.handle_get_team({"team_id": self.team_id})
        if "error" in team:
            raise ValueError(
                f"Configured Linear team does not exist or is inaccessible: "
                f"{self.team_id!r}"
            )

        project = await tools.handle_get_project({"project_id": self.project_id})
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
            response = await tools.handle_list_issues({"project_id": self.project_id})
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
    """Build the Linear create payload.

    ``parent_id`` is intentionally omitted: in the prompt's output it carries a
    plan-local temp id, not a Linear UUID, so we resolve and apply it in a
    second pass once every issue has a real id.
    """
    fields = issue.fields
    return IssueInput(
        title=fields.title,
        description=fields.description,
        team_id=fields.platform_fields["team_id"],
        project_id=fields.platform_fields["project_id"],
        priority=fields.priority,
    )


def _update_payload(issue: IssuePlan) -> IssueUpdateInput:
    """Build the Linear update payload.

    ``parent_id`` is resolved separately in ``_apply_parent_links`` for the same
    reason as ``_create_payload``.
    """
    fields = issue.fields
    issue_id = fields.platform_fields.get("issue_id")
    if not issue_id:
        raise ValueError("update action requires fields.platform_fields.issue_id")
    return IssueUpdateInput(
        title=fields.title,
        description=fields.description,
        priority=fields.priority,
    )


def _raise_if_error(raw: dict[str, Any], *, op: str) -> None:
    """Surface tool-handler error envelopes as RuntimeError before validation."""
    if isinstance(raw, dict) and "error" in raw:
        raise RuntimeError(f"Linear {op} failed: {raw['error']}")
