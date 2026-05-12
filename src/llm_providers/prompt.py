"""SystemPrompt sum type — first-class support for vendor-neutral skills.

Three subclasses:
  - TextSystemPrompt:    raw string content.
  - SkillReference:      path to a markdown skill file. Provider decides
                         whether to load natively (Claude SystemPromptFile)
                         or read-and-inline (Codex / Gemini).
  - PresetSystemPrompt:  named preset; only valid for providers whose
                         capabilities.supports_system_prompt_file is True.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from pathlib import (
    Path,  # noqa: TC003  # runtime import; used in dataclass field annotation
)


class SystemPrompt(ABC):  # noqa: B024  # discriminated-union marker, no abstract methods by design
    """Base of the SystemPrompt sum type. Subclass-based discriminated union."""


@dataclass(frozen=True)
class TextSystemPrompt(SystemPrompt):
    text: str


@dataclass(frozen=True)
class SkillReference(SystemPrompt):
    """Path to a markdown skill file (e.g. .claude/skills/uat-validation/SKILL.md).

    `locator` is an optional human-readable identifier (typically the project-
    relative path) used for logging/observability. Not required for resolution.
    """

    path: Path
    locator: str | None = None


@dataclass(frozen=True)
class PresetSystemPrompt(SystemPrompt):
    """Vendor-managed named preset (e.g. claude_agent_sdk.SystemPromptPreset).

    Only valid when provider.capabilities.supports_system_prompt_file is True.
    Providers without native preset support raise UnsupportedCapabilityError.
    """

    preset_id: str
