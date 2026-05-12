"""Backlog runtime parity: same plan.md fixture must produce a valid
BacklogOutput on both runtimes when the underlying SDKs are mocked.

Covers three assertions:
1. Claude runtime path yields a valid BacklogOutput.
2. Codex runtime path yields a valid BacklogOutput (same fixture JSON).
3. Pydantic retry (up to 3 attempts) never silently swaps runtimes.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hsb.agents.backlog_agent import _run_backlog_agent_async
from hsb.contracts.backlog import BacklogInput, ProjectContext

# ---------------------------------------------------------------------------
# Fixture JSON — matches the real BacklogOutput / EpicItem / UserStory /
# TaskItem / BacklogTraceability Pydantic schemas exactly:
#
#   EpicItem:          title, description, acceptance_criteria=[], user_stories=[], tasks=[]
#   UserStory:         title, description, acceptance_criteria=[], tasks=[]
#   TaskItem:          title, description, acceptance_criteria=[]
#   BacklogTraceability: plan_source
#   BacklogOutput:     epics (min_length=1), traceability
#
# All models use extra="forbid", so no extra keys allowed.
# ---------------------------------------------------------------------------
FIXTURE_BACKLOG_JSON = json.dumps(
    {
        "epics": [
            {
                "title": "[EPIC] Pilot epic",
                "description": "> from plan.md",
                "acceptance_criteria": [],
                "user_stories": [
                    {
                        "title": "Story 1",
                        "description": "> story excerpt",
                        "acceptance_criteria": [],
                        "tasks": [
                            {
                                "title": "Task 1.1",
                                "description": "> task excerpt",
                                "acceptance_criteria": [],
                            }
                        ],
                    }
                ],
                "tasks": [],
            }
        ],
        "traceability": {"plan_source": "fixture/plan.md"},
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_claude_fake_messages(result_json: str):
    """Build fake AssistantMessage + ResultMessage compatible with the
    backlog_agent isinstance checks (sdk_msg = message.raw).
    """
    from claude_agent_sdk import AssistantMessage, ResultMessage

    fake_assistant = MagicMock(spec=AssistantMessage)
    text_block = MagicMock()
    text_block.text = result_json
    del text_block.name  # ensure hasattr(block, "name") is False for this block
    fake_assistant.content = [text_block]

    fake_result = MagicMock(spec=ResultMessage)
    fake_result.subtype = "success"
    fake_result.result = result_json
    fake_result.usage = {}

    return fake_assistant, fake_result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def backlog_input(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\nA tiny fixture plan.\n")
    return BacklogInput(
        plan_source=str(plan),
        project_context=ProjectContext(
            name="fixture",
            repository="https://github.com/example/fixture",
        ),
    )


@pytest.fixture
def codex_home(tmp_path, monkeypatch):
    """Minimal ~/.codex dir satisfying G1-Codex guard."""
    home = tmp_path / "codex_home"
    home.mkdir()
    (home / "config.toml").write_text(
        'forced_login_method = "chatgpt"\n\n'
        '[mcp_servers.linear]\ncommand = "npx"\nargs = []\n'
    )
    (home / "auth.json").write_text("{}")
    monkeypatch.setenv("CODEX_HOME", str(home))
    return home


# ---------------------------------------------------------------------------
# Test 1: Claude path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claude_path_yields_valid_backlog_output(monkeypatch, backlog_input):
    """HSB_RUNTIME_BACKLOG=claude: ClaudeRuntime path produces a valid BacklogOutput."""
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")

    fake_assistant, fake_result = _make_claude_fake_messages(FIXTURE_BACKLOG_JSON)

    async def fake_query(prompt, options):
        yield fake_assistant
        yield fake_result

    # Patch at the ClaudeRuntime seam — same approach as test_claude_runtime.py.
    with patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_query):
        out = await _run_backlog_agent_async(backlog_input)

    assert len(out.epics) == 1
    assert out.epics[0].title.startswith("[EPIC]")
    assert out.traceability.plan_source == "fixture/plan.md"


# ---------------------------------------------------------------------------
# Test 2: Codex path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_codex_path_yields_valid_backlog_output(
    monkeypatch, backlog_input, codex_home
):
    """HSB_RUNTIME_BACKLOG=codex: real CodexRuntime, mocked SDK at the seam.

    Verifies the runtime-agnostic completion path: backlog_agent must
    pick up result_text from message.is_final (Codex) — NOT from
    isinstance(raw, ResultMessage) (Claude-only).
    """
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "codex")

    # Fake one Codex event carrying the JSON. CodexRuntime will yield it
    # then a synthetic is_final=True Message containing the buffered text.
    fake_event = SimpleNamespace(text=FIXTURE_BACKLOG_JSON)

    async def _events():
        yield fake_event

    fake_thread = MagicMock()
    fake_thread.run_streamed = AsyncMock(return_value=SimpleNamespace(events=_events()))
    fake_codex = MagicMock()
    fake_codex.start_thread = MagicMock(return_value=fake_thread)

    # LINEAR_HOOKS must be None for the Codex path (CodexRuntime rejects hooks).
    with (
        patch("hsb.agents.backlog_agent.LINEAR_HOOKS", None),
        patch("hsb.runtime.codex.Codex", return_value=fake_codex),
    ):
        out = await _run_backlog_agent_async(backlog_input)

    assert len(out.epics) == 1
    fake_codex.start_thread.assert_called_once()


# ---------------------------------------------------------------------------
# Test 3: Pydantic retry does not swap runtimes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pydantic_retry_does_not_swap_runtimes(monkeypatch, backlog_input):
    """Pydantic validation failure triggers retry on the *same* runtime — never swaps.

    First call: agent returns non-JSON → ValidationError / JSONDecodeError.
    Second call: agent returns valid FIXTURE_BACKLOG_JSON → success.

    Asserts:
      - claude_agent_sdk.query called exactly twice (one retry).
      - CodexRuntime never instantiated (no silent runtime swap).
    """
    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "claude")

    bad_assistant, bad_result = _make_claude_fake_messages("not json")
    good_assistant, good_result = _make_claude_fake_messages(FIXTURE_BACKLOG_JSON)

    call_count = {"n": 0}

    async def fake_query(prompt, options):
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield bad_assistant
            yield bad_result
        else:
            yield good_assistant
            yield good_result

    with (
        patch("hsb.runtime.claude.claude_agent_sdk.query", side_effect=fake_query) as q,
        patch("hsb.runtime.codex.CodexRuntime") as codex_cls,
    ):
        out = await _run_backlog_agent_async(backlog_input)

    assert q.call_count == 2  # one retry on same runtime
    codex_cls.assert_not_called()  # never silently switched runtime
    assert len(out.epics) == 1
