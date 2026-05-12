"""BaseProvider ABC + StatefulClient Protocol.

Subclasses declare three ClassVars (name, capabilities, supported_auth) and
implement query() and client(). Translation hooks default to NotImplementedError;
each subclass overrides the ones relevant to its capability set.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, ClassVar, Protocol, Self

from llm_providers.auth.base import AuthStrategy
from llm_providers.errors import UnsupportedAuthError, UnsupportedCapabilityError
from llm_providers.prompt import SystemPrompt
from llm_providers.protocol import Capabilities, Message, ProviderOptions
from llm_providers.tools import McpServerSpec, ToolPolicy


class StatefulClient(Protocol):
    """Multi-turn session counterpart to query(). Used by stateful providers."""

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc: Any) -> None: ...
    async def query(self, prompt: str) -> AsyncIterator[Message]: ...


class BaseProvider(ABC):
    """Vendor-neutral provider interface.

    Liskov contract:
      - Every subclass accepts the same ProviderOptions in query()/client().
      - Vendor specifics travel through ProviderOptions.extras[<provider name>].
      - Capability gaps are surfaced via UnsupportedCapabilityError, never
        silently ignored.
    """

    name: ClassVar[str]
    capabilities: ClassVar[Capabilities]
    supported_auth: ClassVar[tuple[type[AuthStrategy], ...]]

    def __init__(self, auth: AuthStrategy) -> None:
        self._auth = self._validate_auth(auth)

    @classmethod
    def _validate_auth(cls, auth: AuthStrategy) -> AuthStrategy:
        if not isinstance(auth, cls.supported_auth):
            raise UnsupportedAuthError(
                provider=cls.name,
                got=type(auth).__name__,
                accepted=[a.__name__ for a in cls.supported_auth],
            )
        return auth

    def require_capability(self, name: str) -> None:
        """Raise UnsupportedCapabilityError if capabilities.supports_<name> is False."""
        flag = f"supports_{name}"
        if not getattr(self.capabilities, flag, False):
            raise UnsupportedCapabilityError(provider=self.name, capability=name)

    # ---- Required overrides --------------------------------------------------

    @abstractmethod
    async def query(
        self, prompt: str, options: ProviderOptions
    ) -> AsyncIterator[Message]:
        """One-shot streaming query. Yields Messages; emits a final Message
        with is_final=True before the iterator ends."""
        ...

    @abstractmethod
    def client(self, options: ProviderOptions) -> StatefulClient:
        """Stateful multi-turn client. Raise UnsupportedCapabilityError if
        capabilities.supports_stateful_client is False."""
        ...

    # ---- Translation hooks ---------------------------------------------------
    # Subclasses override the ones relevant to their feature set. The base
    # raises NotImplementedError with a clear name so an over-eager caller
    # gets a precise error instead of a silent AttributeError.

    def _translate_system_prompt(self, sp: SystemPrompt) -> Any:
        raise NotImplementedError(
            f"{type(self).__name__}._translate_system_prompt not implemented"
        )

    def _translate_tools(self, policy: ToolPolicy) -> Any:
        raise NotImplementedError(
            f"{type(self).__name__}._translate_tools not implemented"
        )

    def _translate_mcp(self, servers: tuple[McpServerSpec, ...]) -> Any:
        raise NotImplementedError(
            f"{type(self).__name__}._translate_mcp not implemented"
        )
