"""Universal Orchestrator — manages the tool loop and agnostic hooks.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

from hsb.runtime.protocol import Message

if TYPE_CHECKING:
    from hsb.runtime.protocol import AgentOptions, Runtime


class UniversalOrchestrator:
    """Orchestrates the conversation loop, tool execution, and hooks.
    
    Acts as a wrapper around a Runtime, adding tool execution and 
    agnostic hook support for runtimes that don't have it natively.
    """

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime

    @property
    def name(self) -> str:
        """Proxies the underlying runtime name."""
        return self._runtime.name

    @property
    def runtime(self) -> Runtime:
        """Exposes the underlying runtime for tests."""
        return self._runtime

    async def query(self, prompt: str, options: AgentOptions) -> AsyncIterator[Message]:
        """Runs the conversation loop.
        
        Currently delegates to the underlying runtime. In Phase 3, 
        this will implement the universal tool loop.
        """
        # For now, we just delegate.
        async for msg in self._runtime.query(prompt, options):
            yield msg
