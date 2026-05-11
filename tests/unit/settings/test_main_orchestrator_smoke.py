"""Smoke-test parity check: main_orchestrator.CLAIM_DELAY_MS uses
OrchestratorSettings as the env-var source."""

import importlib

import pytest


def _reload_main_orchestrator():
    """Force a fresh module-level read of CLAIM_DELAY_MS."""
    import hsb.agents.main_orchestrator as mo

    return importlib.reload(mo)


def test_claim_delay_ms_default(monkeypatch):
    monkeypatch.delenv("HSB_CLAIM_DELAY_MS", raising=False)
    mo = _reload_main_orchestrator()
    assert mo.CLAIM_DELAY_MS == 200
    assert isinstance(mo.CLAIM_DELAY_MS, int)


def test_claim_delay_ms_reads_env(monkeypatch):
    monkeypatch.setenv("HSB_CLAIM_DELAY_MS", "750")
    mo = _reload_main_orchestrator()
    assert mo.CLAIM_DELAY_MS == 750


def test_claim_delay_ms_rejects_negative(monkeypatch):
    from pydantic import ValidationError

    monkeypatch.setenv("HSB_CLAIM_DELAY_MS", "-1")
    with pytest.raises(ValidationError):
        _reload_main_orchestrator()
