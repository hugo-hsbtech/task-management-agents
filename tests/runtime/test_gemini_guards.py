import os
import pytest
from unittest.mock import patch
from hsb.runtime.gemini_guards import assert_gemini_oauth_only

def test_gemini_guard_rejects_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "sk-123")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY set — forbidden"):
        assert_gemini_oauth_only()

def test_gemini_guard_requires_project(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT environment variable not set"):
        assert_gemini_oauth_only()

def test_gemini_guard_requires_adc(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-project")
    
    with patch("google.auth.default", side_effect=Exception("No ADC")):
        with pytest.raises(RuntimeError, match="Application Default Credentials \(ADC\) missing"):
            assert_gemini_oauth_only()

def test_gemini_guard_passes_with_valid_config(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west1")
    
    with patch("google.auth.default", return_value=("mock-creds", "mock-project")):
        config = assert_gemini_oauth_only()
        assert config["project"] == "my-project"
        assert config["location"] == "europe-west1"
        assert config["credentials"] == "mock-creds"
