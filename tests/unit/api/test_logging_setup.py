"""Runtime-api application logging configuration (#427).

The bug: the runtime-api container emitted only uvicorn access logs, so the
in-process executor's application logs — including a run's terminal exception —
never reached stdout and every failure was a black box. ``configure_logging``
attaches a named stdout handler to the root logger so those logs surface.
"""

from __future__ import annotations

import io
import logging

import pytest

from squadops.api.runtime.logging_setup import _HANDLER_NAME, configure_logging

pytestmark = [pytest.mark.domain_api]


@pytest.fixture(autouse=True)
def _restore_root_logging():
    """Save/restore the global root logger so these tests can't leak handlers or a
    mutated level into the rest of the suite."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


def _our_handlers() -> list[logging.Handler]:
    return [h for h in logging.getLogger().handlers if getattr(h, "name", None) == _HANDLER_NAME]


def test_attaches_a_named_stdout_handler_at_info_by_default(monkeypatch):
    monkeypatch.delenv("SQUADOPS_LOG_LEVEL", raising=False)
    configure_logging()
    handlers = _our_handlers()
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.StreamHandler)
    assert handlers[0].level == logging.INFO
    assert logging.getLogger().level == logging.INFO


def test_level_from_env(monkeypatch):
    monkeypatch.setenv("SQUADOPS_LOG_LEVEL", "debug")  # case-insensitive
    configure_logging()
    assert logging.getLogger().level == logging.DEBUG
    assert _our_handlers()[0].level == logging.DEBUG


def test_explicit_level_arg_overrides_env(monkeypatch):
    monkeypatch.setenv("SQUADOPS_LOG_LEVEL", "DEBUG")
    configure_logging(level="WARNING")
    assert logging.getLogger().level == logging.WARNING


def test_unknown_level_falls_back_to_info_not_crash(monkeypatch):
    # a bad env value must never crash the process at import or silently disable logging
    monkeypatch.setenv("SQUADOPS_LOG_LEVEL", "NOT_A_LEVEL")
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_idempotent_reuses_handler_and_updates_level(monkeypatch):
    monkeypatch.delenv("SQUADOPS_LOG_LEVEL", raising=False)
    configure_logging()
    configure_logging(level="ERROR")  # second call — re-import / re-assert
    handlers = _our_handlers()
    assert len(handlers) == 1  # no duplicate stacked on root
    assert handlers[0].level == logging.ERROR


def test_squadops_logger_message_reaches_the_stream(monkeypatch):
    # the functional guarantee: an application log actually lands on our handler
    monkeypatch.delenv("SQUADOPS_LOG_LEVEL", raising=False)
    configure_logging()
    buf = io.StringIO()
    _our_handlers()[0].setStream(buf)
    logging.getLogger("squadops.cycles.executor").info("run failed: CycleError boom")
    assert "run failed: CycleError boom" in buf.getvalue()


def test_below_level_message_is_suppressed(monkeypatch):
    monkeypatch.delenv("SQUADOPS_LOG_LEVEL", raising=False)
    configure_logging(level="WARNING")
    buf = io.StringIO()
    _our_handlers()[0].setStream(buf)
    logging.getLogger("squadops.x").info("chatty")  # below WARNING
    logging.getLogger("squadops.x").warning("important")
    out = buf.getvalue()
    assert "chatty" not in out
    assert "important" in out
