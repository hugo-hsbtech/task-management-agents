"""Deprecation shim — see :mod:`hsb.runtime.compat`.

The canonical body lives in :mod:`hsb.runtime.compat`. SDK symbols and
small helpers are re-exported here so existing call sites (and
``mock.patch`` / ``monkeypatch.setattr`` targets in the test suite) keep
resolving to module-level names on ``hsb.runtime.codex``.

Prefer ``llm_providers.ProviderRegistry.build_auto("openai", ...)`` for
new code — Codex CLI OAuth is selected automatically when
``~/.codex/auth.json`` is present.
"""

from __future__ import annotations

import os
from typing import Any

# Re-exports of the SDK symbols the legacy runtime touched. Tests patch
# ``hsb.runtime.codex.Codex`` — keeping the class imported here means the
# patch target resolves correctly. The shim in :mod:`hsb.runtime.compat`
# looks these up via the ``hsb.runtime.codex`` module so the patches take
# effect.
from openai_codex_sdk import (
    Codex,
    TextInput,
    ThreadOptions,
    TurnCompletedEvent,
    TurnFailedEvent,
    TurnOptions,
)
from openai_codex_sdk.types import CodexOptions

from hsb.runtime.compat import CodexRuntime
from hsb.runtime.protocol import PermissionMode


def _extract_event_text(evt: Any) -> str:
    """Pull the text payload from a Codex ThreadEvent.

    Real Codex events vary: AgentMessageItem has a .text on its content
    blocks; ItemCompletedEvent wraps an item; SimpleNamespace fakes used
    in tests just have .text. Return "" if nothing readable.
    """
    direct = getattr(evt, "text", None)
    if isinstance(direct, str) and direct:
        return direct
    item = getattr(evt, "item", None)
    if item is not None:
        item_text = getattr(item, "text", None)
        if isinstance(item_text, str) and item_text:
            return item_text
    return ""


_PERMISSION_MAP: dict[PermissionMode, str] = {
    "default": "on-request",
    "acceptEdits": "never",
    "plan": "on-request",
    "bypassPermissions": "never",
}


def _build_codex_options() -> CodexOptions | None:
    """Honor CODEX_PATH_OVERRIDE so operators can reuse a globally-installed
    ``codex`` binary (``npm i -g @openai/codex``) without populating the
    SDK's vendor dir. Returns None when no override is set, letting the
    SDK fall back to ``find_codex_path()``.
    """
    override = os.environ.get("CODEX_PATH_OVERRIDE")
    if override:
        return CodexOptions(codexPathOverride=override)
    return None


__all__ = [
    "Codex",
    "CodexOptions",
    "CodexRuntime",
    "TextInput",
    "ThreadOptions",
    "TurnCompletedEvent",
    "TurnFailedEvent",
    "TurnOptions",
    "_PERMISSION_MAP",
    "_build_codex_options",
    "_extract_event_text",
]
