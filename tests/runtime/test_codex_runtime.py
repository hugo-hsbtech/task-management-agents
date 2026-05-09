"""CodexRuntime: wraps openai_codex_sdk.Codex behind Runtime Protocol.

API note (openai-codex-sdk v0.1.11):
- Codex() constructor needs a binary; tests patch hsb.runtime.codex.Codex.
- start_thread(ThreadOptions(...)) returns a Thread.
- await thread.run_streamed(TextInput(type="text", text=...), TurnOptions(...))
  returns a StreamedTurn whose .events is an async iterator.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hsb.runtime.protocol import AgentOptions


@pytest.fixture
def codex_home(tmp_path):
    home = tmp_path / "codex_home"
    home.mkdir()
    (home / "config.toml").write_text(
        'forced_login_method = "chatgpt"\nmodel = "gpt-5.4"\n\n'
        '[mcp_servers.linear]\ncommand = "npx"\nargs = []\n'
    )
    (home / "auth.json").write_text("{}")
    return home


@pytest.fixture
def opts():
    return AgentOptions(
        system_prompt="sys-prompt",
        allowed_tools=("Read",),
        permission_mode="acceptEdits",
        max_turns=5,
        model="gpt-5.4",
        mcp_servers={"linear": {"command": "npx", "args": []}},
    )


def _make_streamed_turn(events: list):
    """Build a fake StreamedTurn whose .events is an async iterator over `events`."""
    async def _aiter():
        for e in events:
            yield e
    return SimpleNamespace(events=_aiter())


def test_init_runs_oauth_check(codex_home):
    from hsb.runtime.codex import CodexRuntime
    rt = CodexRuntime(codex_home=codex_home)
    assert rt.name == "codex"
    assert rt._cached_config["forced_login_method"] == "chatgpt"


def test_init_fails_when_oauth_invalid(tmp_path):
    from hsb.runtime.codex import CodexRuntime
    bad_home = tmp_path / "no_codex"
    with pytest.raises(RuntimeError, match=r"G1-Codex"):
        CodexRuntime(codex_home=bad_home)


@pytest.mark.asyncio
async def test_query_rejects_hooks(codex_home, opts):
    from hsb.runtime.codex import CodexRuntime
    opts_with_hooks = AgentOptions(**{**opts.__dict__, "hooks": ["x"]})
    rt = CodexRuntime(codex_home=codex_home)
    with pytest.raises(NotImplementedError, match=r"hooks"):
        async for _ in rt.query("p", opts_with_hooks):
            pass


@pytest.mark.asyncio
async def test_query_verifies_mcp(codex_home, opts):
    """Requesting an MCP server not in config.toml raises before binary spawn."""
    from hsb.runtime.codex import CodexRuntime
    bad_opts = AgentOptions(
        **{**opts.__dict__, "mcp_servers": {"missing": {"command": "x"}}}
    )
    rt = CodexRuntime(codex_home=codex_home)
    with pytest.raises(RuntimeError, match=r"missing"):
        async for _ in rt.query("p", bad_opts):
            pass


@pytest.mark.asyncio
async def test_query_calls_codex_thread_run(codex_home, opts):
    from hsb.runtime.codex import CodexRuntime

    fake_event = SimpleNamespace(text="hi from codex")
    fake_thread = MagicMock()
    fake_thread.run_streamed = AsyncMock(return_value=_make_streamed_turn([fake_event]))
    fake_codex = MagicMock()
    fake_codex.start_thread = MagicMock(return_value=fake_thread)

    with patch("hsb.runtime.codex.Codex", return_value=fake_codex):
        rt = CodexRuntime(codex_home=codex_home)
        msgs = []
        async for m in rt.query("hello", opts):
            msgs.append(m)

    fake_codex.start_thread.assert_called_once()
    thread_options_arg = fake_codex.start_thread.call_args.args[0]
    assert thread_options_arg.model == "gpt-5.4"
    assert thread_options_arg.approval_policy == "never"

    # run_streamed received a TextInput with the system+user prompt.
    fake_thread.run_streamed.assert_awaited_once()
    call = fake_thread.run_streamed.call_args
    text_input = call.args[0]
    assert "<system>sys-prompt</system>" in text_input.text
    assert "hello" in text_input.text


@pytest.mark.asyncio
async def test_query_translates_permission_mode(codex_home, opts):
    from hsb.runtime.codex import CodexRuntime

    fake_thread = MagicMock()
    fake_thread.run_streamed = AsyncMock(return_value=_make_streamed_turn([]))
    fake_codex = MagicMock()
    fake_codex.start_thread = MagicMock(return_value=fake_thread)

    accept_opts = AgentOptions(**{**opts.__dict__, "permission_mode": "bypassPermissions"})

    with patch("hsb.runtime.codex.Codex", return_value=fake_codex):
        rt = CodexRuntime(codex_home=codex_home)
        async for _ in rt.query("p", accept_opts):
            pass

    thread_options_arg = fake_codex.start_thread.call_args.args[0]
    assert thread_options_arg.approval_policy == "never"


@pytest.mark.asyncio
async def test_query_passes_cwd_and_output_schema(codex_home, opts):
    from hsb.runtime.codex import CodexRuntime

    fake_thread = MagicMock()
    fake_thread.run_streamed = AsyncMock(return_value=_make_streamed_turn([]))
    fake_codex = MagicMock()
    fake_codex.start_thread = MagicMock(return_value=fake_thread)

    cwd_opts = AgentOptions(
        **{**opts.__dict__, "cwd": "/tmp", "output_schema": {"type": "object"}}
    )

    with patch("hsb.runtime.codex.Codex", return_value=fake_codex):
        rt = CodexRuntime(codex_home=codex_home)
        async for _ in rt.query("p", cwd_opts):
            pass

    thread_options_arg = fake_codex.start_thread.call_args.args[0]
    assert thread_options_arg.working_directory == "/tmp"
    turn_options_arg = fake_thread.run_streamed.call_args.args[1]
    assert turn_options_arg.output_schema == {"type": "object"}


@pytest.mark.asyncio
async def test_query_uses_codex_path_override_env(codex_home, opts, monkeypatch):
    """Setting CODEX_PATH_OVERRIDE makes CodexRuntime pass CodexOptions to Codex()."""
    from hsb.runtime.codex import CodexRuntime

    monkeypatch.setenv("CODEX_PATH_OVERRIDE", "/usr/local/bin/codex")

    fake_thread = MagicMock()
    fake_thread.run_streamed = AsyncMock(return_value=_make_streamed_turn([]))
    fake_codex = MagicMock()
    fake_codex.start_thread = MagicMock(return_value=fake_thread)

    with patch("hsb.runtime.codex.Codex", return_value=fake_codex) as codex_cls:
        rt = CodexRuntime(codex_home=codex_home)
        async for _ in rt.query("p", opts):
            pass

    # Codex(...) must have been called with a single CodexOptions arg whose
    # codex_path_override equals our env var.
    codex_cls.assert_called_once()
    args = codex_cls.call_args.args
    assert len(args) == 1
    codex_opts = args[0]
    assert codex_opts.codex_path_override == "/usr/local/bin/codex"
