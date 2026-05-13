"""AuthStrategy ABC + Credential dataclass.

Strategies are typed value holders, NOT detection/discovery objects. The
``resolve_auth`` factory in ``llm_providers.auth.factory`` is the single
place that maps (provider, auth_kind) → credential source → strategy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class Credential:
    """Resolved credential. Opaque to general callers; providers read what
    they need from `payload` based on `kind`."""

    kind: Literal["api_key", "oauth2_cli_token", "oauth2_adc", "oauth2_service_account"]
    payload: Mapping[str, Any]


class AuthStrategy(ABC):
    """Strategy interface — one instance holds one resolved credential value.

    Subclasses declare ``kind`` (ClassVar) and implement ``resolve()``.
    Construction validates the held value (non-empty); ``resolve()`` simply
    wraps it in a ``Credential``.
    """

    kind: ClassVar[str]

    @abstractmethod
    def resolve(self) -> Credential: ...
