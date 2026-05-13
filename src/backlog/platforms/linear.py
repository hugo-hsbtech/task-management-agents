"""Linear platform implementation for backlog generation."""

from __future__ import annotations

import asyncio
from collections import deque
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel, Field

from libs.linear.schemas import Issue, IssueInput, IssueUpdateInput
from llm_providers.tools import ToolPolicy
from tools.linear import LinearTools

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from backlog.contracts import BacklogOutput, IssuePlan


# Linear's per-user rate limit (~1500 req/hour personal API key) is enforced
# with burst tolerance; over-bursts surface from `linear_api` as opaque
# GraphQL "Argument Validation Error" rather than a clean HTTP 429. We pace
# writes with a sliding-window limiter (max requests per window seconds) AND
# retry transient errors with exponential backoff. The window is intentionally
# conservative vs Linear's published limit to leave headroom for any other
# Linear traffic running off the same API key.
LINEAR_WRITE_MAX_REQUESTS_PER_WINDOW: int = 20
LINEAR_WRITE_WINDOW_SECONDS: float = 60.0
LINEAR_WRITE_MAX_ATTEMPTS: int = 4
LINEAR_WRITE_BACKOFF_BASE_SECONDS: float = 1.0
LINEAR_WRITE_BACKOFF_MAX_SECONDS: float = 16.0


class _SlidingWindowRateLimiter:
    """Allow at most ``max_calls`` events per rolling ``window_seconds``.

    Single-process, asyncio-only. Multiple coroutines may share one instance;
    the internal lock serialises window arithmetic. When the window is full,
    the next caller sleeps until the oldest recorded call falls out.
    """

    def __init__(self, max_calls: int, window_seconds: float) -> None:
        self._max = max_calls
        self._window = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        # Drop the lock around sleeps so concurrent waiters can re-check the
        # window when slots age out, instead of all queuing behind one sleeper.
        # Loops until a slot is reserved.
        while True:
            async with self._lock:
                loop = asyncio.get_running_loop()
                now = loop.time()
                while self._timestamps and now - self._timestamps[0] >= self._window:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._max:
                    self._timestamps.append(loop.time())
                    return
                sleep_for = self._window - (now - self._timestamps[0])
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)


_LINEAR_WRITE_LIMITER = _SlidingWindowRateLimiter(
    max_calls=LINEAR_WRITE_MAX_REQUESTS_PER_WINDOW,
    window_seconds=LINEAR_WRITE_WINDOW_SECONDS,
)


# Substrings that mark Linear/Cloudflare responses we should retry.
# Matched case-insensitively against the stringified exception or error
# envelope message. The "argument validation error" pattern is included
# because Linear's GraphQL gateway returns it under burst conditions where
# a clean 429 would be more informative.
_TRANSIENT_LINEAR_ERROR_TOKENS = (
    "argument validation error",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    "rate limit",
    "too many requests",
    "timeout",
    "502",
    "503",
    "504",
    "429",
)


def _is_transient_linear_error(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in _TRANSIENT_LINEAR_ERROR_TOKENS)


def _backoff_seconds(attempt: int) -> float:
    raw: float = LINEAR_WRITE_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
    return (
        raw
        if raw < LINEAR_WRITE_BACKOFF_MAX_SECONDS
        else LINEAR_WRITE_BACKOFF_MAX_SECONDS
    )


async def _linear_write_call(
    method: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    payload: dict[str, Any],
    *,
    op: str,  # noqa: ARG001 — reserved for future logging / metrics
) -> dict[str, Any]:
    """Rate-limit + retry-on-transient wrapper for Linear writes.

    Each attempt acquires a slot from the global sliding-window limiter (so
    retries pay the throttle too), then invokes ``method(payload)``. Transient
    failures — raised exceptions whose stringification matches a known token,
    or error-envelope dicts whose ``"error"`` value matches — trigger
    exponential backoff (1s, 2s, 4s, 8s; capped at 16s) up to
    ``LINEAR_WRITE_MAX_ATTEMPTS``. Non-transient failures and final-attempt
    failures are re-raised / returned unchanged for the caller to surface.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, LINEAR_WRITE_MAX_ATTEMPTS + 1):
        await _LINEAR_WRITE_LIMITER.acquire()
        try:
            raw = await method(payload)
        except Exception as exc:  # noqa: BLE001 — bubble unless transient
            if attempt >= LINEAR_WRITE_MAX_ATTEMPTS or not _is_transient_linear_error(
                str(exc)
            ):
                raise
            last_exc = exc
            await asyncio.sleep(_backoff_seconds(attempt))
            continue

        # Tool handlers may return an error envelope instead of raising —
        # inspect and retry if the message looks transient.
        if (
            isinstance(raw, dict)
            and "error" in raw
            and attempt < LINEAR_WRITE_MAX_ATTEMPTS
            and _is_transient_linear_error(str(raw.get("error", "")))
        ):
            await asyncio.sleep(_backoff_seconds(attempt))
            continue
        return raw

    # All attempts exhausted with raised exceptions — re-raise the last.
    assert last_exc is not None
    raise last_exc


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
                update_payload = {
                    "issue_id": issue_id,
                    **_update_payload(issue).model_dump(mode="json", by_alias=False),
                }
                raw = await _linear_write_call(
                    tools.handle_update_issue, update_payload, op="update_issue"
                )
                _raise_if_error(raw, op="update_issue")
                result = IssueResult(action="update", issue=Issue.model_validate(raw))
            else:
                create_payload = _create_payload(issue).model_dump(
                    mode="json", by_alias=False
                )
                raw = await _linear_write_call(
                    tools.handle_create_issue, create_payload, op="create_issue"
                )
                _raise_if_error(raw, op="create_issue")
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
            parent_payload = {
                "issue_id": result.issue.id,
                "parent_id": parent_real_id,
            }
            raw = await _linear_write_call(
                tools.handle_update_issue,
                parent_payload,
                op="update_issue (parent link)",
            )
            _raise_if_error(raw, op="update_issue (parent link)")

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
                relation_payload = {
                    "issue_id": result.issue.id,
                    "related_issue_id": target_id,
                    "type": relation.type,
                }
                raw = await _linear_write_call(
                    tools.handle_create_issue_relation,
                    relation_payload,
                    op="create_issue_relation",
                )
                _raise_if_error(raw, op="create_issue_relation")

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
    reason as ``_create_payload``. ``state`` is sourced from
    ``platform_fields["state"]`` when provided so the LLM can express workflow
    transitions in the plan.
    """
    fields = issue.fields
    issue_id = fields.platform_fields.get("issue_id")
    if not issue_id:
        raise ValueError("update action requires fields.platform_fields.issue_id")
    return IssueUpdateInput(
        title=fields.title,
        description=fields.description,
        priority=fields.priority,
        state=fields.platform_fields.get("state"),
    )


def _raise_if_error(raw: dict[str, Any], *, op: str) -> None:
    """Surface tool-handler error envelopes as RuntimeError before validation."""
    if isinstance(raw, dict) and "error" in raw:
        raise RuntimeError(f"Linear {op} failed: {raw['error']}")
