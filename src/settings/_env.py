"""Private os.environ chokepoint.

This is the **only** place outside pydantic-settings classes where the
repo reads or writes ``os.environ``. Every other module in
``src/llm_providers``, ``src/backlog``, and ``src/libs`` routes through
the helpers below so:

  - There is a single grep-target for env access audits.
  - Tests can monkeypatch one symbol to redirect every consumer.
  - The "settings owns env" invariant has a runtime home, not just a
    convention.

These helpers are intentionally low-level. Higher-level domain settings
(``CodexSettings``, ``RuntimeSettings``, etc.) consume them indirectly
via pydantic-settings.
"""

from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


def read_env(name: str, default: str | None = None) -> str | None:
    """Return ``os.environ[name]`` or ``default``. The only sanctioned env read
    outside pydantic-settings."""
    return os.environ.get(name, default)


def env_present(name: str) -> bool:
    """True iff ``name`` is set in the environment and non-empty."""
    return bool(os.environ.get(name))


def snapshot_env() -> dict[str, str]:
    """Return a shallow copy of the current process env.

    Used by callers that need to construct a subprocess env dict — they
    inherit-and-augment rather than mutating the parent process.
    """
    return dict(os.environ)


@contextlib.contextmanager
def scoped_env(updates: Mapping[str, str]) -> Iterator[None]:
    """Temporarily apply ``updates`` to ``os.environ``, restoring on exit.

    Use sparingly — the right answer is usually to pass the value to the
    callee explicitly (e.g. via a subprocess ``env=`` kwarg or an SDK
    options object). This exists only for libraries that hard-read env at
    call time and accept no override.
    """
    saved: dict[str, str | None] = {k: os.environ.get(k) for k in updates}
    try:
        os.environ.update(updates)
        yield
    finally:
        for key, prior in saved.items():
            if prior is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prior


__all__ = ["env_present", "read_env", "scoped_env", "snapshot_env"]
