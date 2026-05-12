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

    def issue_defaults(self) -> dict[str, str]:
        """Return platform fields injected into generated issues."""
        ...

    def tool_policy(self, *, api_key: str) -> ToolPolicy:
        """Return provider-agnostic tools supported by the platform."""
        ...

    async def execute(
        self,
        output: BacklogOutput,
        *,
        api_key: str,
    ) -> list[IssueResult]:
        """Apply a planned BacklogOutput to the platform (create/update issues)."""
        ...
