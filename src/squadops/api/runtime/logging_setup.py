"""Application logging configuration for the runtime-api process (#427).

The runtime-api container runs the ``DispatchedFlowExecutor`` in-process but emitted
only uvicorn access logs: the ``squadops``/``adapters`` application loggers had no
handler, so a run's terminal exception (logged by the executor) never reached stdout
and every failure had to be reconstructed by hand — the run was a black box.

uvicorn configures only its own loggers (``uvicorn`` / ``uvicorn.error`` /
``uvicorn.access``) and leaves the root logger untouched — its ``LOGGING_CONFIG`` has
no ``root`` key and ``disable_existing_loggers=False`` (verified empirically) — so a
root stdout handler installed at import time survives uvicorn's startup ``dictConfig``
and captures every application logger, before and after boot.
"""

from __future__ import annotations

import logging
import os
import sys

# Marks our handler so a re-import (or a second call under test) re-uses it rather
# than stacking duplicates on the root logger.
_HANDLER_NAME = "squadops-stdout"
_DEFAULT_LEVEL = "INFO"
_ENV_LEVEL = "SQUADOPS_LOG_LEVEL"

#: #560: the audit records (SIP-0062, a compliance surface — nothing here reduces what is
#: recorded) leave the application stream. ``squadops.audit`` gets its own handler and
#: stops propagating to the root stdout handler; with the path set (the compose mounts
#: ``./data/audit`` and sets it), records land in a rotating JSONL file; unset, they keep
#: going to stdout as before and boot says so once — a deploy pipeline that forgot the
#: sink loses nothing, it just keeps the noise.
AUDIT_LOGGER_NAME = "squadops.audit"
_AUDIT_HANDLER_NAME = "squadops-audit-sink"
_ENV_AUDIT_PATH = "SQUADOPS_AUDIT_LOG_PATH"
_AUDIT_ROTATE_BYTES = 50 * 1024 * 1024
_AUDIT_ROTATE_COUNT = 5

#: #560: third-party chatter demoted below INFO — httpx logs a line per Prefect POST
#: (``/api/logs/``, ``/api/task_runs/``, ``set_state``), three per task-state transition.
_QUIET_LOGGERS = {"httpx": logging.WARNING, "httpcore": logging.WARNING}


def _resolve_level(level: str | None) -> int:
    """Resolve a level name (arg → ``SQUADOPS_LOG_LEVEL`` → INFO) to a logging int.

    An unknown name falls back to INFO rather than raising — a bad env value must
    never crash the process at import, and silently dropping to no logging would
    reintroduce exactly the swallow this fixes.
    """
    name = (level or os.getenv(_ENV_LEVEL) or _DEFAULT_LEVEL).upper()
    resolved = logging.getLevelName(name)
    return resolved if isinstance(resolved, int) else logging.INFO


def configure_logging(level: str | None = None) -> None:
    """Attach a stdout handler to the root logger so ``squadops``/``adapters``
    application logs reach ``docker logs`` alongside uvicorn's (#427).

    Idempotent: a second call re-uses the existing named handler and only updates the
    level, so re-import under test (or a startup re-assert) never stacks duplicates.
    Level comes from ``level``, else ``SQUADOPS_LOG_LEVEL``, else ``INFO``.
    """
    root = logging.getLogger()
    resolved = _resolve_level(level)
    root.setLevel(resolved)

    existing = next((h for h in root.handlers if getattr(h, "name", None) == _HANDLER_NAME), None)
    if existing is not None:
        existing.setLevel(resolved)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(_HANDLER_NAME)
    handler.setLevel(resolved)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    for name, quiet_level in _QUIET_LOGGERS.items():
        logging.getLogger(name).setLevel(quiet_level)
    configure_audit_sink(os.getenv(_ENV_AUDIT_PATH))


def configure_audit_sink(path: str | None) -> logging.Handler | None:
    """Route ``squadops.audit`` to its own sink (#560). Returns the handler installed, or
    None when no path is configured (records keep propagating to stdout, unchanged).

    Idempotent like ``configure_logging``: a second call with the same path re-uses the
    named handler; with a different path it replaces it.
    """
    audit = logging.getLogger(AUDIT_LOGGER_NAME)
    existing = next(
        (h for h in audit.handlers if getattr(h, "name", None) == _AUDIT_HANDLER_NAME), None
    )
    if not path:
        if existing is None:
            logging.getLogger(__name__).warning(
                "audit records share the application stream — set %s to give them their "
                "own sink (#560)",
                _ENV_AUDIT_PATH,
            )
        return existing
    if existing is not None and getattr(existing, "baseFilename", None) == os.path.abspath(path):
        return existing
    if existing is not None:
        audit.removeHandler(existing)
        existing.close()
    from logging.handlers import RotatingFileHandler

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    handler = RotatingFileHandler(
        path, maxBytes=_AUDIT_ROTATE_BYTES, backupCount=_AUDIT_ROTATE_COUNT, encoding="utf-8"
    )
    handler.set_name(_AUDIT_HANDLER_NAME)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))  # the record IS the JSON line
    audit.addHandler(handler)
    audit.setLevel(logging.INFO)
    audit.propagate = False
    return handler
