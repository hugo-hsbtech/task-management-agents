"""Abstract platform protocol for backlog generation."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol, runtime_checkable

from llm_providers.tools import ToolPolicy

if TYPE_CHECKING:
    from backlog.contracts import BacklogOutput
    from backlog.platforms.linear import IssueResult


@runtime_checkable
class BacklogPlatform(Protocol):
    """Common dependency surface every backlog platform must provide."""

    platform_name: ClassVar[str]

    @property
    def issue_defaults(self) -> dict[str, str]:
        """Platform fields injected into generated issues."""
        ...

    @property
    def api_key(self) -> str:
        """Resolved API key for this platform.

        Implementations read from their own settings module (e.g. Linear reads
        ``settings.linear.api_key``). Raises ``ValueError`` if not configured.
        Keeps the agent layer free of platform-specific settings imports.
        """
        ...

    def tool_policy(self, *, api_key: str) -> ToolPolicy:
        """Return provider-agnostic tools supported by the platform."""
        ...

    async def execute(self, output: BacklogOutput) -> list[IssueResult]:
        """Apply a planned BacklogOutput to the platform (create/update issues).

        Each platform reads its own credential via ``self.api_key``.
        """
        ...
