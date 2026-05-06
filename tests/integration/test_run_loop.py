"""Plan 03-04 — ``run_loop.py`` integration tests.

Verify the cascade-mode loop driver against an actual ``run_loop.py``
subprocess. The Pitfall 5 source-grep test is the only one that can run
without Linear MCP credentials — the other two require a live workspace
to drive ``has_ready_tasks()``.

VALIDATION.md aliases:
- CLIR-04: ``test_loop_terminates``
- Pitfall 5: ``test_loop_stops_on_run_next_step_failure``
"""
from __future__ import annotations

import importlib.util
import inspect
import os
import signal
import subprocess
import sys
import time

import pytest

pytestmark = [pytest.mark.integration]


def _require_linear_creds() -> None:
    if not (
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LINEAR_API_KEY")
    ):
        pytest.skip(
            "Neither ANTHROPIC_API_KEY nor LINEAR_API_KEY set — run_loop.py "
            "needs Linear MCP credentials to query has_ready_tasks()."
        )


# --- CLIR-04: run_loop terminates when no ready tasks -----------------------

@pytest.mark.integration
def test_loop_terminates_when_no_ready_tasks() -> None:
    """CLIR-04: ``run_loop.py`` exits cleanly when no todo tasks remain in Linear.

    PRECONDITION: the Linear test workspace has zero todo tasks. Operator must
    clear the workspace before running this test, OR run it after the WORC-01
    e2e test has consumed the only seeded task.
    """
    _require_linear_creds()
    result = subprocess.run(
        [sys.executable, "run_loop.py"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"run_loop.py failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert (
        "No ready tasks remaining" in result.stdout
        or "Loop complete" in result.stdout
        or "Loop interrupted" in result.stdout
    ), f"missing termination message: stdout={result.stdout!r}"


@pytest.mark.integration
def test_loop_terminates() -> None:
    """CLIR-04 alias matching VALIDATION.md command ID."""
    test_loop_terminates_when_no_ready_tasks()


# --- CLIR-04: graceful Ctrl+C handling --------------------------------------

@pytest.mark.integration
def test_loop_exits_on_ctrl_c() -> None:
    """CLIR-04: ``run_loop.py`` stops cleanly on KeyboardInterrupt."""
    _require_linear_creds()
    process = subprocess.Popen(
        [sys.executable, "run_loop.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(2)  # let the loop start its first iteration
    process.send_signal(signal.SIGINT)
    process.wait(timeout=15)
    assert process.returncode in (0, 130), (
        f"unexpected returncode {process.returncode}; "
        "expected 0 (KeyboardInterrupt handled) or 130 (default SIGINT)"
    )


# --- Pitfall 5: loop stops on non-zero exit ---------------------------------

@pytest.mark.integration
def test_loop_stops_on_run_next_step_failure() -> None:
    """RESEARCH.md Pitfall 5: ``run_loop.py main()`` MUST check subprocess
    returncode and stop on any non-zero exit.

    Source-grep verification — does NOT require Linear credentials.
    """
    spec = importlib.util.spec_from_file_location("run_loop", "run_loop.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    main_source = inspect.getsource(module.main)
    assert "returncode" in main_source, (
        "run_loop.py main() must check subprocess returncode "
        "(RESEARCH.md Pitfall 5)"
    )
    assert "sys.exit" in main_source, (
        "run_loop.py must sys.exit on non-zero subprocess exit "
        "(RESEARCH.md Pitfall 5)"
    )
    # The whole module must also handle KeyboardInterrupt cleanly
    module_source = inspect.getsource(module)
    assert "except KeyboardInterrupt" in module_source
