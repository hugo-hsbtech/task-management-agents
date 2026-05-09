"""G5 (AI-SPEC §6): :func:`linear_write_guard` stack inspection.

RISK-04 layer 4: any LinearAgent write originating from ``risk_agent.py``
is denied EXCEPT when the call stack also includes the explicit
operator-delegated entry point
``global_orchestrator.approve_improvement_trigger``.
"""
import textwrap

import pytest

from hsb.agents.guards import linear_write_guard


@linear_write_guard
async def _guarded_write(payload):
    return f"wrote {payload}"


@pytest.mark.asyncio
async def test_g5_allows_normal_caller():
    """Direct call from test code (no risk_agent.py frame) is allowed."""
    result = await _guarded_write({"id": "X"})
    assert result == "wrote {'id': 'X'}"


@pytest.mark.asyncio
async def test_g5_denies_caller_from_risk_agent_path(tmp_path):
    """A function defined in a file path containing ``hsb/agents/risk_agent.py``
    triggers G5 denial. We synthesize this by writing a tiny module to a
    path that includes the fragment and importing it."""
    synthetic_dir = tmp_path / "hsb" / "agents"
    synthetic_dir.mkdir(parents=True)
    synthetic_file = synthetic_dir / "risk_agent.py"
    synthetic_file.write_text(
        textwrap.dedent(
            """
            async def call_guarded(guarded_fn, payload):
                return await guarded_fn(payload)
            """
        )
    )

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "synthetic_risk_agent", str(synthetic_file)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with pytest.raises(PermissionError) as exc:
        await mod.call_guarded(_guarded_write, {"id": "X"})
    assert "RISK-04 violation (G5)" in str(exc.value)


@pytest.mark.asyncio
async def test_g5_allows_operator_delegated_path(tmp_path):
    """When the call stack contains BOTH ``risk_agent.py`` AND a
    ``global_orchestrator.py::approve_improvement_trigger`` frame, the
    call is ALLOWED (operator-delegated path)."""
    ga_dir = tmp_path / "ga" / "hsb" / "agents"
    ga_dir.mkdir(parents=True)
    (ga_dir / "global_orchestrator.py").write_text(
        textwrap.dedent(
            """
            async def approve_improvement_trigger(guarded_fn, payload):
                return await guarded_fn(payload)
            """
        )
    )
    ra_dir = tmp_path / "ra" / "hsb" / "agents"
    ra_dir.mkdir(parents=True)
    (ra_dir / "risk_agent.py").write_text(
        textwrap.dedent(
            """
            async def call_via_orchestrator(orch_fn, guarded_fn, payload):
                return await orch_fn(guarded_fn, payload)
            """
        )
    )

    import importlib.util

    ga_spec = importlib.util.spec_from_file_location(
        "synthetic_go", str(ga_dir / "global_orchestrator.py")
    )
    ga_mod = importlib.util.module_from_spec(ga_spec)
    ga_spec.loader.exec_module(ga_mod)

    ra_spec = importlib.util.spec_from_file_location(
        "synthetic_ra", str(ra_dir / "risk_agent.py")
    )
    ra_mod = importlib.util.module_from_spec(ra_spec)
    ra_spec.loader.exec_module(ra_mod)

    # Stack contains BOTH frames: risk_agent.py AND
    # global_orchestrator.py::approve_improvement_trigger. G5 should ALLOW.
    result = await ra_mod.call_via_orchestrator(
        ga_mod.approve_improvement_trigger, _guarded_write, {"id": "X"}
    )
    assert result == "wrote {'id': 'X'}"


def test_g5_decorator_preserves_sync_function():
    """``linear_write_guard`` returns a sync wrapper for a sync target."""

    @linear_write_guard
    def sync_write(payload):
        return f"sync wrote {payload}"

    assert sync_write({"id": "X"}) == "sync wrote {'id': 'X'}"


def test_linear_agent_write_methods_are_guarded():
    """``linear_agent.py`` applies ``@linear_write_guard`` to write methods."""
    src = open("src/hsb/agents/linear_agent.py").read()
    assert "linear_write_guard" in src, (
        "G5 violated: linear_agent.py does not import or apply linear_write_guard"
    )
    assert "from hsb.agents.guards import linear_write_guard" in src
