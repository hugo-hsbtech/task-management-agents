"""Gemini-side analogues of the G1 guards.

Ensures that the Gemini runtime is only used with OAuth2/ADC credentials 
and that the required Google Cloud project configuration is present.
"""
from __future__ import annotations

import os
import google.auth
from typing import Any

FORBIDDEN_API_KEY_VAR = "GEMINI_API_KEY"

def assert_gemini_oauth_only() -> dict[str, Any]:
    """Init-time check for Gemini OAuth2 compliance.
    
    Returns:
        A dict containing 'project' and 'location'.
    
    Raises:
        RuntimeError: If GEMINI_API_KEY is set or if ADC is missing.
    """
    if FORBIDDEN_API_KEY_VAR in os.environ:
        raise RuntimeError(
            f"G1-Gemini violation: {FORBIDDEN_API_KEY_VAR} set — forbidden. "
            "Gemini runtime must use OAuth2/ADC only. "
            "Run 'make auth-gemini' and unset GEMINI_API_KEY."
        )

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError(
            "G1-Gemini violation: GOOGLE_CLOUD_PROJECT environment variable not set. "
            "Vertex AI requires a Google Cloud project ID. "
            "Add it to your .env file."
        )

    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    try:
        credentials, _ = google.auth.default()
        if not credentials:
             raise RuntimeError("No credentials found.")
    except Exception as exc:
        raise RuntimeError(
            "G1-Gemini violation: Google Cloud Application Default Credentials (ADC) missing. "
            "Run 'make auth-gemini' to authenticate."
        ) from exc

    return {
        "project": project,
        "location": location,
        "credentials": credentials
    }
