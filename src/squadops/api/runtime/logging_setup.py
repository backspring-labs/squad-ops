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
