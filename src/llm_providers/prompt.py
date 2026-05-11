"""SystemPrompt sum type — see Task 3 for full implementation."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass


class SystemPrompt(ABC):  # noqa: B024  # abstract methods added in Task 3
    """Base class for the SystemPrompt sum type."""


@dataclass(frozen=True)
class TextSystemPrompt(SystemPrompt):
    text: str
