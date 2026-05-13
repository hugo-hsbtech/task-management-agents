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
        self.labels: list[dict] = []
        self._next_id = 2

    async def handle_list_issues(self, input_data: dict) -> dict:
        return {
            "issues": [
                {"id": "LIN-1", "identifier": "SAND-1", "title": "[EPIC] Existing"}
            ]
        }

    async def handle_create_issue(self, input_data: dict) -> dict:
        self.created.append(input_data)
        new_id = f"LIN-{self._next_id}"
        self._next_id += 1
        return {"id": new_id, "identifier": new_id, "title": input_data["title"]}

    async def handle_update_issue(self, input_data: dict) -> dict:
        self.updated.append(input_data)
        return {
            "id": input_data["issue_id"],
            "identifier": input_data["issue_id"],
            "title": input_data.get("title", ""),
        }

    async def handle_create_issue_relation(self, input_data: dict) -> dict:
        self.relations.append(input_data)
        return {
            "id": "rel-1",
            "type": input_data["type"],
            "issue_id": input_data["issue_id"],
            "related_issue_id": input_data["related_issue_id"],
        }

    async def handle_add_label(self, input_data: dict) -> dict:
        self.labels.append(input_data)
        return {
            "id": input_data["issue_id"],
            "identifier": input_data["issue_id"],
            "title": "labeled",
        }

    async def handle_get_team(self, input_data: dict) -> dict:
        return {"id": input_data["team_id"], "name": "Sandbox", "key": "SAND"}

    async def handle_get_project(self, input_data: dict) -> dict:
        return {
            "id": input_data["project_id"],
            "name": "Sandbox Project",
            "teamId": "SAND",
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def platform(monkeypatch: pytest.MonkeyPatch) -> LinearPlatform:
    monkeypatch.setattr(LinearPlatform, "api_key", property(lambda self: "lin-test"))
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

    results = await base_output.platform.execute(base_output)

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

    await base_output.platform.execute(base_output)

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

    results = await output.platform.execute(output)

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
        async def handle_list_issues(self, input_data: dict) -> dict:
            raise ValueError("permission denied")

    monkeypatch.setattr(
        "backlog.platforms.linear.LinearTools", lambda api_key: FailingTools(api_key)
    )

    with pytest.raises(ValueError, match="Unable to list Linear issues"):
        await base_output.platform.execute(base_output)


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
        async def handle_get_team(self, input_data: dict) -> dict:
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
        async def handle_get_project(self, input_data: dict) -> dict:
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
        id="2",
        issue_type="task",
        fields=IssueFields(
            title="[TASK] Login",
            description="Impl.",
            priority=3,
            parent_id="1",
            platform_fields={"team_id": "T1", "project_id": "P1"},
        ),
    )

    payload = _create_payload(issue)

    assert payload.title == "[TASK] Login"
    assert payload.team_id == "T1"
    assert payload.project_id == "P1"
    assert payload.priority == 3
    # parent_id is a plan-local temp id at this stage — resolved in a second
    # pass via _apply_parent_links, so it is intentionally NOT in the create
    # payload sent to Linear.
    assert payload.parent_id is None


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
    defaults = platform.issue_defaults
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
    results = await platform.execute(output)

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

    defaults = platform.issue_defaults
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

    await platform.execute(output)

    assert instances[0].relations == []


@pytest.mark.asyncio
async def test_execute_skips_relations_when_result_issue_has_no_id(
    monkeypatch, platform: LinearPlatform
) -> None:
    instances: list[FakeLinearTools] = []

    class NoIdTools(FakeLinearTools):
        async def handle_create_issue(self, input_data: dict) -> dict:
            self.created.append(input_data)
            return {"id": "", "identifier": "", "title": input_data["title"]}

    def fake_tools(api_key: str) -> NoIdTools:
        t = NoIdTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    output = _make_output_with_relations(platform, IssueRelationType.blocks)
    await platform.execute(output)

    assert instances[0].relations == []


@pytest.mark.asyncio
async def test_execute_resolves_parent_id_temp_to_real(
    monkeypatch, platform: LinearPlatform
) -> None:
    """parent_id is a plan-local temp id; second pass resolves it to a real Linear id."""
    instances: list[FakeLinearTools] = []

    def fake_tools(api_key: str) -> FakeLinearTools:
        t = FakeLinearTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    defaults = platform.issue_defaults
    output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                id="1",
                issue_type="epic",
                fields=IssueFields(
                    title="[E] Parent",
                    description="Parent epic.",
                    platform_fields=dict(defaults),
                ),
            ),
            IssuePlan(
                id="2",
                issue_type="task",
                fields=IssueFields(
                    title="[T] Child",
                    description="Child task.",
                    parent_id="1",
                    platform_fields=dict(defaults),
                ),
            ),
        ],
    )

    results = await platform.execute(output)

    # Two creates, then one update_issue setting parent on the child.
    assert len(instances[0].created) == 2
    assert len(instances[0].updated) == 1
    parent_update = instances[0].updated[0]
    assert parent_update["issue_id"] == results[1].issue.id
    assert parent_update["parent_id"] == results[0].issue.id


@pytest.mark.asyncio
async def test_execute_skips_parent_link_for_reused_issues(
    monkeypatch, platform: LinearPlatform
) -> None:
    instances: list[FakeLinearTools] = []

    def fake_tools(api_key: str) -> FakeLinearTools:
        t = FakeLinearTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    defaults = platform.issue_defaults
    output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                id="1",
                issue_type="epic",
                fields=IssueFields(
                    title="[E] New parent",
                    description="Will be created.",
                    platform_fields=dict(defaults),
                ),
            ),
            IssuePlan(
                id="2",
                issue_type="task",
                fields=IssueFields(
                    # Title matches the fake's existing issue → reused.
                    title="[EPIC] Existing",
                    description="Reused; parent must NOT be re-linked.",
                    parent_id="1",
                    platform_fields=dict(defaults),
                ),
            ),
        ],
    )

    await platform.execute(output)

    assert instances[0].updated == []


@pytest.mark.skip(
    reason=(
        "Label application is disabled in LinearPlatform.execute() — the upstream "
        "Linear SDK's IssueManager no longer exposes add_label. Un-skip when the "
        "SDK regains the method (or we switch to a GraphQL mutation in "
        "linear_client.add_label_to_issue)."
    )
)
@pytest.mark.asyncio
async def test_execute_applies_labels_to_created_issues(
    monkeypatch, platform: LinearPlatform
) -> None:
    instances: list[FakeLinearTools] = []

    def fake_tools(api_key: str) -> FakeLinearTools:
        t = FakeLinearTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    defaults = platform.issue_defaults
    output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                id="1",
                issue_type="task",
                fields=IssueFields(
                    title="[T] Tagged",
                    description="Has labels.",
                    labels=["backend", "p1"],
                    platform_fields=dict(defaults),
                ),
            )
        ],
    )

    results = await platform.execute(output)

    assert [lbl["label_name"] for lbl in instances[0].labels] == ["backend", "p1"]
    assert all(lbl["issue_id"] == results[0].issue.id for lbl in instances[0].labels)


@pytest.mark.asyncio
async def test_execute_skips_labels_on_reused_issues(
    monkeypatch, platform: LinearPlatform
) -> None:
    instances: list[FakeLinearTools] = []

    def fake_tools(api_key: str) -> FakeLinearTools:
        t = FakeLinearTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    defaults = platform.issue_defaults
    output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                issue_type="epic",
                fields=IssueFields(
                    title="[EPIC] Existing",
                    description="Already in Linear.",
                    labels=["should-not-be-applied"],
                    platform_fields=dict(defaults),
                ),
            )
        ],
    )

    await platform.execute(output)

    assert instances[0].labels == []


@pytest.mark.asyncio
async def test_execute_raises_on_tool_error_envelope(
    monkeypatch, platform: LinearPlatform
) -> None:
    """{'error': ...} responses must surface as RuntimeError, not ValidationError."""

    class FailingTools(FakeLinearTools):
        async def handle_create_issue(self, input_data: dict) -> dict:
            return {"error": "boom"}

    monkeypatch.setattr(
        "backlog.platforms.linear.LinearTools", lambda api_key: FailingTools(api_key)
    )

    defaults = platform.issue_defaults
    output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                issue_type="task",
                fields=IssueFields(
                    title="[T] Will fail",
                    description="Tool returns error envelope.",
                    platform_fields=dict(defaults),
                ),
            )
        ],
    )

    with pytest.raises(RuntimeError, match="create_issue failed: boom"):
        await platform.execute(output)


@pytest.mark.asyncio
async def test_execute_rejects_mismatched_platform(
    monkeypatch, platform: LinearPlatform
) -> None:
    """LinearPlatform.execute must refuse a BacklogOutput targeting a different platform."""

    class ForeignPlatform:
        platform_name = "jira"

        @property
        def issue_defaults(self) -> dict:
            return {}

    monkeypatch.setattr(
        "backlog.platforms.linear.LinearTools", lambda api_key: FakeLinearTools(api_key)
    )

    defaults = platform.issue_defaults
    output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                issue_type="task",
                fields=IssueFields(
                    title="[T] Anything",
                    description="Any.",
                    platform_fields=dict(defaults),
                ),
            )
        ],
    )
    # Bypass BacklogOutput's typed platform field by replacing post-validation.
    object.__setattr__(output, "platform", ForeignPlatform())

    with pytest.raises(ValueError, match="does not match 'linear'"):
        await platform.execute(output)


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


# ---------------------------------------------------------------------------
# api_key property — settings resolution
# ---------------------------------------------------------------------------


def test_api_key_property_reads_settings_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """api_key property must unwrap settings.linear.api_key.get_secret_value()."""
    monkeypatch.setenv("LINEAR_API_KEY", "lin-real-secret")
    plat = LinearPlatform(team_id="T1", project_id="P1")

    assert plat.api_key == "lin-real-secret"


def test_api_key_property_raises_when_settings_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """api_key property must raise a helpful ValueError when settings.linear.api_key is None."""
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    # The .env file at project root provides LINEAR_API_KEY; point pydantic-settings
    # at an empty cwd so the env-file fallback finds nothing either.
    monkeypatch.chdir(tmp_path)

    plat = LinearPlatform(team_id="T1", project_id="P1")

    with pytest.raises(ValueError, match="Platform API key required"):
        plat.api_key  # noqa: B018  # property access is the act under test


# ---------------------------------------------------------------------------
# _apply_parent_links — temp_id resolves to nothing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skips_parent_link_when_temp_id_unknown(
    monkeypatch, platform: LinearPlatform
) -> None:
    """A parent_id that points to a temp id not produced by this run must be skipped."""
    instances: list[FakeLinearTools] = []

    def fake_tools(api_key: str) -> FakeLinearTools:
        t = FakeLinearTools(api_key)
        instances.append(t)
        return t

    monkeypatch.setattr("backlog.platforms.linear.LinearTools", fake_tools)

    defaults = platform.issue_defaults
    output = BacklogOutput(
        platform=platform,
        issues=[
            IssuePlan(
                id="child",
                issue_type="task",
                fields=IssueFields(
                    title="[T] Child of phantom",
                    description="Parent ref never created.",
                    parent_id="phantom-temp-id",
                    platform_fields=dict(defaults),
                ),
            )
        ],
    )

    results = await platform.execute(output)

    assert results[0].action == "create"
    parent_link_updates = [
        u for u in instances[0].updated if u.get("parent_id") is not None
    ]
    assert parent_link_updates == []
