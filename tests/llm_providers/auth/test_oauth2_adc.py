"""OAuth2ADC strategy: typed value holder + Credential resolution."""

from __future__ import annotations

from llm_providers.auth.oauth2_adc import OAuth2ADC


def test_resolve_returns_adc_credential():
    s = OAuth2ADC(project_id="my-project")
    cred = s.resolve()
    assert cred.kind == "oauth2_adc"
    assert cred.payload["project_id"] == "my-project"
    assert cred.payload["source"] == "adc"


def test_project_id_defaults_to_none():
    s = OAuth2ADC()
    cred = s.resolve()
    assert cred.payload["project_id"] is None


def test_kind_classvar():
    assert OAuth2ADC.kind == "oauth2_adc"
