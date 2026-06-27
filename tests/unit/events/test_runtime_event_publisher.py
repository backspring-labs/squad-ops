"""Unit tests for SIP-0089 §2.6 — LoggingRuntimeEventPublisher.

The coordinator/scheduler depend on the publisher being **best-effort** (D22):
a logging failure must never propagate and turn a successful mode transition
into an application error. The structured fields it records are also the only
observability an activated scheduler has, so they are asserted exactly.
"""

from __future__ import annotations

import logging

import pytest

from adapters.events.runtime_event_publisher import LoggingRuntimeEventPublisher
from squadops.runtime import events, reasons

pytestmark = [pytest.mark.domain_runtime]


def test_emit_records_structured_transition_fields(caplog):
    """Bug class: a publisher that dropped any of event_name/agent_id/reason_code/
    payload would blind the only observability path for live transitions. Assert
    each canonical field lands on the log record exactly."""
    pub = LoggingRuntimeEventPublisher()
    with caplog.at_level(logging.INFO, logger="squadops.runtime.events"):
        pub.emit(
            events.MODE_TRANSITION,
            agent_id="max",
            reason_code=reasons.DUTY_WINDOW_OPENED,
            payload={"from_mode": "ambient", "to_mode": "duty"},
        )

    [record] = [r for r in caplog.records if r.name == "squadops.runtime.events"]
    assert record.runtime_event == "runtime_state.mode_transition"
    assert record.agent_id == "max"
    assert record.reason_code == "duty_window_opened"
    assert record.payload == {"from_mode": "ambient", "to_mode": "duty"}


def test_emit_normalizes_missing_payload_to_empty_dict(caplog):
    """Bug class: callers may omit payload (e.g. a bare window-skip). It must log
    as an empty dict, never `None`, so downstream parsing never hits a NoneType."""
    pub = LoggingRuntimeEventPublisher()
    with caplog.at_level(logging.INFO, logger="squadops.runtime.events"):
        pub.emit(
            events.ASSIGNMENT_WINDOW_SKIPPED,
            agent_id="neo",
            reason_code=reasons.DUTY_WINDOW_MISSED,
        )

    [record] = [r for r in caplog.records if r.name == "squadops.runtime.events"]
    assert record.payload == {}


def test_emit_never_raises_when_logging_fails(monkeypatch):
    """Bug class (D22 best-effort): if the sink raises, emit must swallow it.
    A propagated logging error would abort the coordinator's transition AFTER the
    mode was already written, desyncing state from its event stream. Force the
    info() call to raise and assert emit still returns cleanly."""
    pub = LoggingRuntimeEventPublisher()

    def _boom(*_args, **_kwargs):
        raise RuntimeError("sink down")

    monkeypatch.setattr("adapters.events.runtime_event_publisher.logger.info", _boom)

    # Must not raise.
    pub.emit(events.MODE_TRANSITION, agent_id="max", reason_code=reasons.DUTY_WINDOW_OPENED)
