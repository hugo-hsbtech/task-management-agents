"""Structured logging configuration.

Single configuration entry point for every package in the repo. Call
``configure()`` once at process start (CLI entry, test conftest); after that
every module uses ``get_logger(__name__)`` to obtain a bound structlog logger.

Why structlog over stdlib ``logging``:
  - Native key/value pairs survive JSON serialization for production.
  - Context binding (``logger.bind(request_id=...)``) propagates without
    sprinkling fields through every call site.
  - Dev mode renders human-readable lines with colors; prod mode emits JSON.

The selection between dev and prod is driven by ``HSB_LOG_JSON`` (read by
``settings.logging.LoggingSettings``) so this module stays free of direct
env access.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from structlog.types import Processor

_configured = False


def configure(
    *,
    level: str = "INFO",
    json_logs: bool = False,
    extra_processors: list[Processor] | None = None,
) -> None:
    """Configure structlog routed through stdlib ``logging``.

    Routing through stdlib lets ``pytest``'s ``caplog`` fixture, third-party
    handler chains, and any external observability tooling see every record
    via the same well-known interface. Safe to call multiple times.
    """
    global _configured

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    # Pre-render processors — applied before the stdlib formatter takes over.
    # ``format_exc_info`` is intentionally NOT in this chain: ProcessorFormatter
    # plus ConsoleRenderer / JSONRenderer handle ``record.exc_info`` natively
    # and produce prettier output. Including it stringifies the exception too
    # early and triggers a structlog UserWarning at runtime.
    pre_chain: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]
    if extra_processors:
        pre_chain.extend(extra_processors)

    renderer: Processor
    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    # structlog → stdlib handoff
    structlog.configure(
        processors=[
            *pre_chain,
            # Hand off to stdlib; final rendering happens in the stdlib
            # formatter (so third-party loggers route through the same chain).
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # stdlib logging — single root handler that formats both structlog records
    # and plain stdlib records uniformly.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=pre_chain,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.getLevelNamesMapping().get(level.upper(), logging.INFO))

    _configured = True


def get_logger(name: str | None = None, **initial_values: Any) -> Any:
    """Return a bound structlog logger.

    ``name`` is the logger name (typically ``__name__``). Initial key/value
    pairs are bound onto the returned logger.
    """
    if not _configured:
        # Lazy default config — call sites don't have to know about ordering.
        configure()
    logger = structlog.get_logger(name)
    if initial_values:
        logger = logger.bind(**initial_values)
    return logger


__all__ = ["configure", "get_logger"]
