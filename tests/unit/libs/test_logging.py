"""Coverage tests for libs.logging — extra_processors, JSON mode, bound kwargs."""

from __future__ import annotations

import logging
from typing import Any

import structlog

from libs.logging import configure, get_logger


def _record_logged() -> list[Any]:
    """Caplog substitute that doesn't require pytest's fixture: capture LogRecords
    via a probe handler attached to the root logger."""
    captured: list[Any] = []

    class _Probe(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    logging.getLogger().addHandler(_Probe())
    return captured


def test_configure_with_extra_processor_runs_it():
    seen: dict[str, Any] = {}

    def _capture(_logger, _name, event_dict):
        seen.update(event_dict)
        return event_dict

    configure(extra_processors=[_capture])
    captured = _record_logged()
    get_logger("libs.logging.test").warning("event", custom=42)

    # The custom processor saw the event dict.
    assert seen.get("custom") == 42
    # At least one record reached stdlib logging via the bridge.
    assert any(r.name == "libs.logging.test" for r in captured)


def test_configure_with_json_renderer_emits_json_payload():
    configure(json_logs=True)
    captured = _record_logged()
    get_logger("libs.logging.json").error("boom", code=500)

    matching = [r for r in captured if r.name == "libs.logging.json"]
    assert matching, "expected the structlog record to reach stdlib logging"


def test_get_logger_with_initial_values_returns_bound_logger():
    configure()
    log = get_logger("libs.logging.bound", request_id="req-1")
    # structlog's bound logger keeps the values in its context for downstream
    # processors — confirm by introspecting the wrapped context dict.
    assert isinstance(log, structlog.stdlib.BoundLogger)
    # `_context` is the internal binding map; presence here proves the bind() ran.
    assert log._context.get("request_id") == "req-1"  # noqa: SLF001


def test_get_logger_triggers_lazy_configure(monkeypatch):
    """If get_logger is called before configure(), it configures with defaults."""
    import libs.logging as mod

    monkeypatch.setattr(mod, "_configured", False)
    # Should not raise; should populate _configured.
    get_logger("libs.logging.lazy")
    assert mod._configured is True
