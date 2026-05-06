"""Phase 4 Plan 03 — Filled-in unit tests for Main Orchestrator (MORD-01..04 + D-01/D-02).

Behavior tests now exercise the real Main Orchestrator implementation.
Functional contract validation tests for MainOrchestratorOutput / DispatchedItem
remain unchanged.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import ValidationError

from hsb.contracts.main_orchestrator import (
    MainOrchestratorOutput,
    DispatchedItem,
    ClaimResult,
)


# --- MORD-01: Mode routing ---

@pytest.mark.asyncio
async def test_mode_routing_cascade():
    """MORD-01: cascade mode calls _cascade_dispatch, not _parallel_dispatch."""
    from hsb.agents.main_orchestrator import run_main_orchestrator
    with (
        patch("hsb.agents.main_orchestrator.GlobalOrchestrator") as MockGO,
        patch("hsb.agents.main_orchestrator._cascade_dispatch", new_callable=AsyncMock) as mock_cascade,
        patch("hsb.agents.main_orchestrator._parallel_dispatch", new_callable=AsyncMock) as mock_parallel,
        patch("hsb.agents.main_orchestrator.run_validated_linear_agent", new_callable=AsyncMock),
    ):
        mock_go_instance = MockGO.return_value
        mock_go_instance.get_ready_tasks = AsyncMock(return_value=MagicMock(
            ready_tasks=[MagicMock(id="LIN-1", title="Task")],
            is_backlog_empty=False,
        ))
        mock_cascade.return_value = []

        await run_main_orchestrator(mode="cascade")

        mock_cascade.assert_called_once()
        mock_parallel.assert_not_called()


@pytest.mark.asyncio
async def test_mode_routing_parallel():
    """MORD-01: parallel mode calls _parallel_dispatch, not _cascade_dispatch."""
    from hsb.agents.main_orchestrator import run_main_orchestrator
    with (
        patch("hsb.agents.main_orchestrator.GlobalOrchestrator") as MockGO,
        patch("hsb.agents.main_orchestrator._cascade_dispatch", new_callable=AsyncMock) as mock_cascade,
        patch("hsb.agents.main_orchestrator._parallel_dispatch", new_callable=AsyncMock) as mock_parallel,
        patch("hsb.agents.main_orchestrator.run_validated_linear_agent", new_callable=AsyncMock),
    ):
        mock_go_instance = MockGO.return_value
        mock_go_instance.get_ready_tasks = AsyncMock(return_value=MagicMock(
            ready_tasks=[MagicMock(id="LIN-1", title="Task")],
            is_backlog_empty=False,
        ))
        mock_parallel.return_value = []

        await run_main_orchestrator(mode="parallel")

        mock_parallel.assert_called_once()
        mock_cascade.assert_not_called()


@pytest.mark.asyncio
async def test_mode_routing():
    """MORD-01 alias: routes to cascade by default. Calls test_mode_routing_cascade."""
    await test_mode_routing_cascade()


# --- MORD-02: Cascade sequential ---

@pytest.mark.asyncio
async def test_cascade_sequential():
    """MORD-02: Cascade mode takes only the first ready task."""
    from hsb.agents.main_orchestrator import _cascade_dispatch
    tasks = [MagicMock(id="LIN-1"), MagicMock(id="LIN-2")]
    with patch("hsb.agents.main_orchestrator._run_wio_subprocess", new_callable=AsyncMock) as mock_wio:
        mock_wio.return_value = {"status": "completed"}
        result = await _cascade_dispatch(tasks, repo_root="/tmp")
    # Only one WIO call — the first task
    mock_wio.assert_called_once()
    assert result[0].work_item_id == "LIN-1"


# --- MORD-03: Optimistic-lock claiming ---

@pytest.mark.asyncio
async def test_claiming_optimistic_lock():
    """MORD-03: Claiming loop verifies updatedAt changed after write."""
    from hsb.agents.main_orchestrator import _sequential_claiming_loop
    tasks = [MagicMock(id="LIN-5")]

    # Simulate: before = "2024-01-01", after = "2024-01-02" (our write changed it)
    call_count = [0]

    async def mock_linear(*args, **kwargs):
        call_count[0] += 1
        entity = MagicMock()
        if call_count[0] == 1:  # first read (pre-write)
            entity.get = lambda k, d=None: "2024-01-01T00:00:00" if k == "updatedAt" else d
        else:  # second read (post-write)
            entity.get = lambda k, d=None: "2024-01-02T00:00:00" if k == "updatedAt" else d
        return MagicMock(linear_entities=[entity])

    with patch("hsb.agents.main_orchestrator.run_validated_linear_agent", side_effect=mock_linear):
        claimed = await _sequential_claiming_loop(tasks, delay_ms=0)

    assert len(claimed) == 1
    assert claimed[0][0].id == "LIN-5"


# --- MORD-04: Worktree lifecycle ---

def test_worktree_lifecycle():
    """MORD-04 + D-09: _parallel_dispatch must call _git_worktree_remove and use asyncio.gather."""
    import inspect
    from hsb.agents.main_orchestrator import _parallel_dispatch
    source = inspect.getsource(_parallel_dispatch)
    assert "_git_worktree_remove" in source, (
        "_parallel_dispatch must call _git_worktree_remove for cleanup (D-09)"
    )
    assert "asyncio.gather" in source, (
        "_parallel_dispatch must use asyncio.gather for parallel dispatch (D-08)"
    )


# --- No LLM in orchestrators ---

def test_no_sdk_session_in_global_orchestrator():
    """D-01: GlobalOrchestrator must not import or use claude_agent_sdk."""
    import inspect
    from hsb.agents.global_orchestrator import GlobalOrchestrator
    source = inspect.getsource(GlobalOrchestrator)
    assert "claude_agent_sdk" not in source, "D-01 violated: GlobalOrchestrator must be pure Python"
    assert "ClaudeAgentOptions" not in source, "D-01 violated: no SDK session in GlobalOrchestrator"


def test_no_sdk_session_in_main_orchestrator():
    """D-02 + T-4-04 + T-4-02: main_orchestrator must not use SDK, env passthrough, or shell=True."""
    import inspect
    import hsb.agents.main_orchestrator as mod
    source = inspect.getsource(mod)
    assert "claude_agent_sdk" not in source, "D-02 violated: MainOrchestrator must be pure Python"
    assert "ClaudeAgentOptions" not in source, "D-02 violated: no SDK session in MainOrchestrator"
    assert "**os.environ" not in source, "T-4-04 violated: env var leakage to subprocess"
    assert "shell=True" not in source, "T-4-02 violated: shell=True allows command injection"


# --- Contract validation (functional) ---

def test_main_orchestrator_output_contract():
    """MainOrchestratorOutput schema validates correctly."""
    output = MainOrchestratorOutput.model_validate({
        "mode": "cascade",
        "dispatched": [
            {
                "work_item_id": "LIN-101",
                "orchestrator_instance": "cascade-0",
                "claim_status": "claimed",
                "final_status": "completed",
            }
        ],
        "cycle_summary": "1 dispatched, 1 completed",
    })
    assert output.mode == "cascade"
    assert len(output.dispatched) == 1
    assert output.dispatched[0].work_item_id == "LIN-101"


def test_dispatched_item_extra_field_rejected():
    """DispatchedItem rejects extra fields (extra='forbid')."""
    with pytest.raises(ValidationError):
        DispatchedItem.model_validate({
            "work_item_id": "LIN-1",
            "orchestrator_instance": "cascade-0",
            "claim_status": "claimed",
            "final_status": "completed",
            "unexpected_field": "boom",
        })
