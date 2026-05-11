"""Tests for hsb.settings.orchestrator.OrchestratorSettings."""

import pytest
from pydantic import ValidationError


def test_claim_delay_ms_default_is_200(monkeypatch):
    monkeypatch.delenv("HSB_CLAIM_DELAY_MS", raising=False)
    from hsb.settings.orchestrator import OrchestratorSettings

    assert OrchestratorSettings().claim_delay_ms == 200


def test_claim_delay_ms_reads_env(monkeypatch):
    monkeypatch.setenv("HSB_CLAIM_DELAY_MS", "500")
    from hsb.settings.orchestrator import OrchestratorSettings

    assert OrchestratorSettings().claim_delay_ms == 500


def test_claim_delay_ms_rejects_negative(monkeypatch):
    monkeypatch.setenv("HSB_CLAIM_DELAY_MS", "-1")
    from hsb.settings.orchestrator import OrchestratorSettings

    with pytest.raises(ValidationError):
        OrchestratorSettings()


def test_project_default(monkeypatch):
    monkeypatch.delenv("HSB_PROJECT", raising=False)
    from hsb.settings.orchestrator import OrchestratorSettings

    assert OrchestratorSettings().project == "task-management-agents"


def test_project_reads_env(monkeypatch):
    monkeypatch.setenv("HSB_PROJECT", "org-acme")
    from hsb.settings.orchestrator import OrchestratorSettings

    assert OrchestratorSettings().project == "org-acme"
