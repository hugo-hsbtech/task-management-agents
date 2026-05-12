"""AuthStrategy ABC + Credential dataclass.

Each strategy resolves a credential from one source (env var, file, gcloud
ADC, etc.). Providers declare their supported_auth as an ordered tuple of
strategy classes; the registry's auto_resolve_auth walks the tuple in
preferred-first order.
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
    """Strategy interface — one instance == one resolved credential source.

    Lifecycle:
      1. detect()  — cheap check: is this strategy available in the environment?
      2. resolve() — full resolution; may read files, refresh tokens.
      3. default() — classmethod returning the conventional zero-arg form
                     used by auto_resolve_auth.
    """

    kind: ClassVar[str]

    @abstractmethod
    def detect(self) -> bool: ...

    @abstractmethod
    def resolve(self) -> Credential: ...

    @classmethod
    @abstractmethod
    def default(cls) -> AuthStrategy: ...
