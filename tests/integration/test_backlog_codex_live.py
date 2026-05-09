"""Live Codex smoke test — requires real ChatGPT subscription auth.

CI never runs this. Operator runs it manually after setting up
`codex login --device-auth` and creating ~/.codex/config.toml per
GET-STARTED.md Step 1.5.

    HSB_LIVE_CODEX=1 HSB_RUNTIME_BACKLOG=codex \\
        uv run pytest tests/integration/test_backlog_codex_live.py -m live_codex -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hsb.agents.backlog_agent import _run_backlog_agent_async
from hsb.contracts.backlog import BacklogInput, ProjectContext

pytestmark = pytest.mark.live_codex


@pytest.fixture
def session_count_before():
    sessions_dir = Path.home() / ".codex" / "sessions"
    if not sessions_dir.exists():
        return 0
    return sum(1 for _ in sessions_dir.rglob("*"))


@pytest.mark.asyncio
async def test_backlog_runs_against_live_codex(
    monkeypatch, tmp_path, session_count_before
):
    if "HSB_LIVE_CODEX" not in os.environ:
        pytest.skip("HSB_LIVE_CODEX env var must be set explicitly to run live test")

    monkeypatch.setenv("HSB_RUNTIME_BACKLOG", "codex")
    plan = tmp_path / "plan.md"
    plan.write_text("# Tiny fixture plan\n\nOne user story: render hello world.\n")
    inp = BacklogInput(
        plan_source=str(plan),
        project_context=ProjectContext(
            name="live-codex-smoke",
            repository="https://github.com/example/live-codex-smoke",
        ),
    )

    out = await _run_backlog_agent_async(inp)

    assert len(out.epics) >= 1, "Codex should have produced at least one EPIC"
    assert out.epics[0].title.startswith("[EPIC]")

    sessions_dir = Path.home() / ".codex" / "sessions"
    sessions_after = (
        sum(1 for _ in sessions_dir.rglob("*")) if sessions_dir.exists() else 0
    )
    assert sessions_after > session_count_before, "Codex did not persist a session"
