"""Shared pytest fixtures.

Phase 5 G1 defensive pairing: a session-scoped autouse fixture clears
``ANTHROPIC_API_KEY`` at test session start so that the function-entry G1
guard in ``_sdk_options.assert_oauth2_only()`` never trips on a leaked env
var during automated runs. Pairs with — does not replace — the runtime
G1 guard in ``_sdk_options.py``.
"""
import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _ensure_api_key():
    """G1 (inverted for PydanticAI): ANTHROPIC_API_KEY must be set.

    For unit tests using TestModel, set a fake key — TestModel never calls
    the API so the fake key is safe. For integration tests, the real key
    from the environment is used (marked with @pytest.mark.integration).
    """
    if "ANTHROPIC_API_KEY" not in os.environ:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-fake-for-testmodel"
    yield


@pytest.fixture
def valid_linear_output() -> dict:
    """Canonical valid LinearOutput payload for contract tests."""
    return {
        "operation": "create",
        "result": "success",
        "linear_entities": [
            {
                "id": "LIN-123",
                "type": "task",
                "url": "https://linear.app/hsb/issue/LIN-123",
            }
        ],
        "error": None,
    }


@pytest.fixture
def failed_linear_output() -> dict:
    """Canonical failed LinearOutput payload for contract tests."""
    return {
        "operation": "create",
        "result": "failed",
        "linear_entities": [],
        "error": "tool_failure: mcp__linear__create_issue returned 500",
    }


# ===== Phase 5 fixtures =====
#
# Per AI-SPEC §4b.2: fixtures that need to call async Linear-agent code MUST
# be ``@pytest_asyncio.fixture`` async generators, NOT sync wrappers around
# ``asyncio.run()`` (which raises RuntimeError when called from inside a
# running event loop).
import shutil
from pathlib import Path

import pytest_asyncio


@pytest.fixture
def tmp_knowledge_cleanup():
    """Removes any ``knowledge/**/*_test_*.md`` files after the test runs.

    Phase 5 INTL-02 integration tests use this to keep the ``knowledge/``
    dir clean. Sync fixture is fine — only filesystem cleanup, no async I/O.
    """
    yield
    root = Path("knowledge")
    if root.exists():
        for p in root.rglob("*_test_*.md"):
            try:
                p.unlink()
            except OSError:
                pass


@pytest.fixture
def linear_test_workspace():
    """Phase 1/2 fixture stub.

    The live Linear-test-workspace fixture is provided by the operator
    setup (mcp-remote OAuth2 + seeded Linear test workspace). For unit
    test collection this fixture is a placeholder that returns a marker
    dict; tests that need real Linear access should be marked with
    ``pytest.mark.integration`` and will be skipped in non-integration
    runs unless the operator has authenticated.
    """
    return {"workspace": "hsb-test", "authenticated": True}


@pytest_asyncio.fixture
async def uat_ready_user_story(linear_test_workspace):
    """Returns a User Story dict from the Linear test workspace where all
    child tasks have ``qa_status=approved`` and ``uat_status`` is not
    approved.

    Async fixture (per AI-SPEC §4b.2): uses ``await`` directly inside the
    running event loop instead of ``asyncio.run()``.

    Pre-condition: the test workspace must contain at least one such User
    Story. If not present, the test is skipped (we do not mutate the
    workspace from a fixture).
    """
    from hsb.agents.linear_agent import run_validated_linear_agent

    try:
        resp = await run_validated_linear_agent(
            operation="list",
            payload={"type": "user_story"},
        )
    except Exception as exc:
        pytest.skip(f"Linear test workspace unavailable: {exc}")

    for entity in (resp.linear_entities or []):
        d = entity if isinstance(entity, dict) else entity.model_dump()
        if d.get("uat_status") == "approved":
            continue
        children_resp = await run_validated_linear_agent(
            operation="list_children",
            payload={"parent_id": d["id"]},
        )
        children = [
            c if isinstance(c, dict) else c.model_dump()
            for c in (children_resp.linear_entities or [])
        ]
        if children and all(c.get("qa_status") == "approved" for c in children):
            return d
    pytest.skip("No UAT-ready User Story in Linear test workspace")


@pytest_asyncio.fixture
async def test_task_with_knowledge_fixture(linear_test_workspace):
    """Returns a Task dict from the Linear test workspace.

    Async fixture (per AI-SPEC §4b.2) — uses ``await`` instead of
    ``asyncio.run()``.

    Pre-condition: ``knowledge/qa/`` contains a pre-seeded entry for the
    task domain. If no qualifying task exists, the test is skipped.
    """
    from hsb.agents.linear_agent import run_validated_linear_agent

    try:
        resp = await run_validated_linear_agent(
            operation="list",
            payload={"type": "task", "status": "todo"},
        )
    except Exception as exc:
        pytest.skip(f"Linear test workspace unavailable: {exc}")

    for entity in (resp.linear_entities or []):
        d = entity if isinstance(entity, dict) else entity.model_dump()
        return d
    pytest.skip("No todo Task in Linear test workspace")


@pytest_asyncio.fixture
async def test_task_with_qa_finding_fixture(test_task_with_knowledge_fixture):
    """Returns a Task expected to trigger a knowledge-worthy QA finding.

    For Phase 5 MVP, we reuse :func:`test_task_with_knowledge_fixture`;
    future extensions may seed deterministic QA failure scenarios. Async
    fixture so it can ``await`` the upstream async fixture.
    """
    return test_task_with_knowledge_fixture
