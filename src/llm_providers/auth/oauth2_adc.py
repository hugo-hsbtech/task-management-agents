"""OAuth2ADC auth strategy — typed value holder for Google ADC.

Holds a project-ID reference for Vertex AI routing. The actual ADC
resolution (``google.auth.default()``) is handled internally by the
``google-genai`` SDK when constructed with ``vertexai=True``. Build via
the auth factory (:func:`llm_providers.auth.factory.resolve_auth`) which
maps ``(gemini, oauth2_adc)`` to this strategy. Tests construct directly.
"""

from __future__ import annotations

from typing import ClassVar

from llm_providers.auth.base import AuthStrategy, Credential
from llm_providers.registry import AuthRegistry


@AuthRegistry.register("oauth2_adc")
class OAuth2ADC(AuthStrategy):
    """Google Application Default Credentials holder.

    Construction:
      OAuth2ADC()                               — project resolved from ADC env
      OAuth2ADC(project_id="my-gcp-project")    — explicit project for Vertex AI
    """

    kind: ClassVar[str] = "oauth2_adc"

    def __init__(self, *, project_id: str | None = None) -> None:
        self._project_id = project_id

    def resolve(self) -> Credential:
        return Credential(
            kind="oauth2_adc",
            payload={"project_id": self._project_id, "source": "adc"},
        )
