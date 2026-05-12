"""Unit tests for backlog.platforms.linear — 100% coverage."""

from __future__ import annotations

import pytest

from backlog.contracts import (
    BacklogOutput,
    IssueFields,
    IssuePlan,
    IssueRelation,
    IssueRelationType,
)
from backlog.platforms import LinearPlatform
from backlog.platforms.linear import IssueResult, _create_payload, _update_payload

# ---------------------------------------------------------------------------
# Shared fake
# ---------------------------------------------------------------------------


class FakeLinearTools:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.created: list[dict] = []
        self.updated: list[dict] = []
        self.relations: list[dict] = []

    async def _handle_list_issues(self, input_data: dict) -> dict:
        return {
            "issues": [
                {"id": "LIN-1", "identifier": "SAND-1", "title": "[EPIC] Existing"}
            ]
        }

    async def _handle_create_issue(self, input_data: dict) -> dict:
        self.created.append(input_data)
        return {"id": "LIN-2", "identifier": "SAND-2", "title": input_data["title"]}

    async def _handle_update_issue(self, input_data: dict) -> dict:
        self.updated.append(input_data)
        return {
            "id": input_data["issue_id"],
            "identifier": input_data["issue_id"],
            "title": input_data.get("title", ""),
        }

    async def _handle_create_issue_relation(self, input_data: dict) -> dict:
        self.relations.append(input_data)
        return {
            "id": "rel-1",
            "type": input_data["type"],
            "issue_id": input_data["issue_id"],
            "related_issue_id": input_data["related_issue_id"],
        }

    async def _handle_get_team(self, input_data: dict) -> dict:
        return {"id": input_data["team_id"], "name": "Sandbox", "key": "SAND"}

    async def _handle_get_project(self, input_data: dict) -> dict:
        return {
            "id": input_data["project_id"],
            "name": "Sandbox Project",
            "teamId": "SAND",
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def platform() -> LinearPlatform:
    return LinearPlatform(team_id="SAND", project_id="project-1")


@pytest.fixture
def base_output(platform: LinearPlatform) -> BacklogOutput:
    return BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                issue_type="epic",
                fields=IssueFields(
                    title="[EPIC] Existing",
                    description="Already there.",
                    platform_fields={"team_id": "SAND", "project_id": "project-1"},
                ),
            ),
            IssuePlan(
                issue_type="task",
                fields=IssueFields(
                    title="[TASK] New",
                    description="Create me.",
                    labels=["backlog"],
                    platform_fields={"team_id": "SAND", "project_id": "project-1"},
                ),
            ),
        ],
    )


# ---------------------------------------------------------------------------
# execute() — create / reuse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_reuses_existing_and_creates_missing(
    monkeypatch, base_output: BacklogOutput
) -> None:
    instances: list[FakeLinearTools] = []

    def fake_tools(api_key: str) -> FakeLinearTools:
        t = FakeLinearTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    results = await base_output.platform.execute(base_output, api_key="lin-test")

    assert [r.action for r in results] == ["reuse", "create"]
    assert results[0].issue.identifier == "SAND-1"
    assert results[1].issue.id == "LIN-2"
    assert isinstance(results[0], IssueResult)
    assert isinstance(results[1], IssueResult)


@pytest.mark.asyncio
async def test_execute_passes_correct_create_payload(
    monkeypatch, base_output: BacklogOutput
) -> None:
    instances: list[FakeLinearTools] = []

    def fake_tools(api_key: str) -> FakeLinearTools:
        t = FakeLinearTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    await base_output.platform.execute(base_output, api_key="lin-test")

    assert instances[0].created[0]["title"] == "[TASK] New"
    assert instances[0].created[0]["team_id"] == "SAND"
    assert instances[0].created[0]["project_id"] == "project-1"


# ---------------------------------------------------------------------------
# execute() — update branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_update_branch(monkeypatch, platform: LinearPlatform) -> None:
    instances: list[FakeLinearTools] = []

    def fake_tools(api_key: str) -> FakeLinearTools:
        t = FakeLinearTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                action="update",
                issue_type="task",
                fields=IssueFields(
                    title="[TASK] Updated",
                    description="Updated desc.",
                    platform_fields={
                        "team_id": "SAND",
                        "project_id": "project-1",
                        "issue_id": "LIN-99",
                    },
                ),
            )
        ],
    )

    results = await output.platform.execute(output, api_key="lin-test")

    assert results[0].action == "update"
    assert results[0].issue.id == "LIN-99"
    assert instances[0].updated[0]["issue_id"] == "LIN-99"


# ---------------------------------------------------------------------------
# _list_existing_by_title — error propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_reraises_list_issues_failure(
    monkeypatch, base_output: BacklogOutput
) -> None:
    class FailingTools(FakeLinearTools):
        async def _handle_list_issues(self, input_data: dict) -> dict:
            raise ValueError("permission denied")

    monkeypatch.setattr(
        "backlog.platforms.linear.LinearTools", lambda api_key: FailingTools(api_key)
    )

    with pytest.raises(ValueError, match="Unable to list Linear issues"):
        await base_output.platform.execute(base_output, api_key="lin-test")


# ---------------------------------------------------------------------------
# validate_target()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_target_succeeds(monkeypatch, platform: LinearPlatform) -> None:
    instances: list[FakeLinearTools] = []

    def fake_tools(api_key: str) -> FakeLinearTools:
        t = FakeLinearTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    await platform.validate_target(api_key="lin-test")

    assert instances[0].api_key == "lin-test"


@pytest.mark.asyncio
async def test_validate_target_raises_on_team_error(
    monkeypatch, platform: LinearPlatform
) -> None:
    class BadTeamTools(FakeLinearTools):
        async def _handle_get_team(self, input_data: dict) -> dict:
            return {"error": "not found"}

    monkeypatch.setattr(
        "backlog.platforms.linear.LinearTools", lambda api_key: BadTeamTools(api_key)
    )

    with pytest.raises(ValueError, match="team does not exist or is inaccessible"):
        await platform.validate_target(api_key="lin-test")


@pytest.mark.asyncio
async def test_validate_target_raises_on_project_error(
    monkeypatch, platform: LinearPlatform
) -> None:
    class BadProjectTools(FakeLinearTools):
        async def _handle_get_project(self, input_data: dict) -> dict:
            return {"error": "not found"}

    monkeypatch.setattr(
        "backlog.platforms.linear.LinearTools", lambda api_key: BadProjectTools(api_key)
    )

    with pytest.raises(ValueError, match="project does not exist or is inaccessible"):
        await platform.validate_target(api_key="lin-test")


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------


def test_create_payload_maps_fields_correctly() -> None:
    issue = IssuePlan(
        issue_type="task",
        fields=IssueFields(
            title="[TASK] Login",
            description="Impl.",
            priority=3,
            parent_id="LIN-10",
            platform_fields={"team_id": "T1", "project_id": "P1"},
        ),
    )

    payload = _create_payload(issue)

    assert payload.title == "[TASK] Login"
    assert payload.team_id == "T1"
    assert payload.project_id == "P1"
    assert payload.priority == 3
    assert payload.parent_id == "LIN-10"


def test_update_payload_maps_fields_correctly() -> None:
    issue = IssuePlan(
        action="update",
        issue_type="task",
        fields=IssueFields(
            title="[TASK] Updated",
            description="New desc.",
            priority=1,
            platform_fields={"team_id": "T1", "project_id": "P1", "issue_id": "LIN-5"},
        ),
    )

    payload = _update_payload(issue)

    assert payload.title == "[TASK] Updated"
    assert payload.priority == 1


# ---------------------------------------------------------------------------
# Relations — _apply_relations
# ---------------------------------------------------------------------------


def _make_output_with_relations(
    platform: LinearPlatform,
    relation_type: IssueRelationType,
) -> BacklogOutput:
    defaults = platform.issue_defaults()
    return BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                issue_type="epic",
                fields=IssueFields(
                    title="[EPIC] Alpha",
                    description="Alpha epic.",
                    platform_fields=dict(defaults),
                ),
                relations=[
                    IssueRelation(type=relation_type, target_title="[TASK] Beta")
                ],
            ),
            IssuePlan(
                issue_type="task",
                fields=IssueFields(
                    title="[TASK] Beta",
                    description="Beta task.",
                    platform_fields=dict(defaults),
                ),
            ),
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "relation_type",
    [
        IssueRelationType.blocks,
        IssueRelationType.blocked_by,
        IssueRelationType.relates_to,
        IssueRelationType.duplicate_of,
    ],
)
async def test_execute_creates_relation_all_types(
    monkeypatch, platform: LinearPlatform, relation_type: IssueRelationType
) -> None:
    instances: list[FakeLinearTools] = []

    def fake_tools(api_key: str) -> FakeLinearTools:
        t = FakeLinearTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    output = _make_output_with_relations(platform, relation_type)
    results = await platform.execute(output, api_key="lin-test")

    assert len(instances[0].relations) == 1
    rel = instances[0].relations[0]
    assert rel["issue_id"] == results[0].issue.id
    assert rel["related_issue_id"] == results[1].issue.id
    assert rel["type"] == relation_type


@pytest.mark.asyncio
async def test_execute_skips_relation_when_target_title_not_found(
    monkeypatch, platform: LinearPlatform
) -> None:
    instances: list[FakeLinearTools] = []

    def fake_tools(api_key: str) -> FakeLinearTools:
        t = FakeLinearTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    defaults = platform.issue_defaults()
    output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                issue_type="task",
                fields=IssueFields(
                    title="[TASK] Solo",
                    description="Only issue.",
                    platform_fields=dict(defaults),
                ),
                relations=[
                    IssueRelation(
                        type=IssueRelationType.blocks,
                        target_title="[TASK] Does Not Exist",
                    )
                ],
            )
        ],
    )

    await platform.execute(output, api_key="lin-test")

    assert instances[0].relations == []


@pytest.mark.asyncio
async def test_execute_skips_relations_when_result_issue_has_no_id(
    monkeypatch, platform: LinearPlatform
) -> None:
    instances: list[FakeLinearTools] = []

    class NoIdTools(FakeLinearTools):
        async def _handle_create_issue(self, input_data: dict) -> dict:
            self.created.append(input_data)
            return {"id": "", "identifier": "", "title": input_data["title"]}

    def fake_tools(api_key: str) -> NoIdTools:
        t = NoIdTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    output = _make_output_with_relations(platform, IssueRelationType.blocks)
    await platform.execute(output, api_key="lin-test")

    assert instances[0].relations == []


def test_update_payload_raises_when_issue_id_missing() -> None:
    issue = IssuePlan(
        action="update",
        issue_type="task",
        fields=IssueFields(
            title="[TASK] No ID",
            description="Missing issue_id.",
            platform_fields={"team_id": "T1", "project_id": "P1"},
        ),
    )

    with pytest.raises(
        ValueError, match="update action requires fields.platform_fields.issue_id"
    ):
        _update_payload(issue)
