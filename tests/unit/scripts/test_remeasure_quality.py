"""Prediction 4's re-measure script (#2416) reads the deploy's own config.

The script runs in the runtime image, piped to ``python -``, so nothing but a live run executed its
``main()``: at the 2.4 window's close it failed on all four calibration trees before measuring
anything, because it asked the window deploy's ``AppConfig`` for a ``database()`` that arrived only
with #2457. It reads the database there now, the one accessor that requires it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "remeasure_quality.py"

#: The minimum that makes ``load_config()`` validate offline (as ``test_loader_secrets_seam.py``).
_ENV = {
    "SQUADOPS__AUTH__ENABLED": "false",
    "SQUADOPS__AUTH__KEYCLOAK__ADMIN__PASSWORD": "literal",
    "SQUADOPS__DB__URL": "postgresql://test:test@localhost:5432/test",
    "SQUADOPS__COMMS__RABBITMQ__URL": "amqp://test:test@localhost:5672/",
    "SQUADOPS__COMMS__REDIS__URL": "redis://localhost:6379/0",
    "SQUADOPS__LLM__PROVIDER": "ollama",
    "SQUADOPS__LLM__URL": "http://ollama:11434",
    "SQUADOPS__COMMS__QUEUE__PROVIDER": "rabbitmq",
    "SQUADOPS__COMMS__A2A__PROVIDER": "http",
    "SQUADOPS__TOOLS__FILESYSTEM__PROVIDER": "local",
    "SQUADOPS__CYCLES__REGISTRY_PROVIDER": "memory",
    "SQUADOPS__CYCLES__SQUAD_PROFILE_PROVIDER": "config",
    "SQUADOPS__CYCLES__PROJECT_REGISTRY_PROVIDER": "config",
    "SQUADOPS__PROMPTS__ASSET_SOURCE_PROVIDER": "filesystem",
    "SQUADOPS__TELEMETRY__BACKEND": "null",
    "SQUADOPS__SANDBOX__PROVIDER": "noop",
}


def _load():
    spec = importlib.util.spec_from_file_location("remeasure_quality", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["remeasure_quality"] = module
    spec.loader.exec_module(module)
    return module


class _Stop(Exception):
    pass


@pytest.fixture
def opened(monkeypatch):
    """The pool the script opens, read where it opens it; the run stops there."""
    for key, value in _ENV.items():
        monkeypatch.setenv(key, value)
    seen: dict = {}

    async def create_pool(url, **kwargs):
        seen.update(url=url, **kwargs)
        raise _Stop

    monkeypatch.setattr("adapters.persistence.pool.create_pool", create_pool)
    return seen


async def test_the_script_opens_the_deploys_database_read_only(opened):
    """Bug caught: the script asking the config for an attribute it doesn't have, so every
    re-measure fails before it starts (the 2.4 close), or opening a pool that can write."""
    with pytest.raises(_Stop):
        await _load().main("cyc_000000000000", 3)

    assert opened["url"] == _ENV["SQUADOPS__DB__URL"]
    assert opened["server_settings"] == {"default_transaction_read_only": "on"}


def test_no_cycle_named_is_a_usage_error_and_nothing_opens(opened, monkeypatch):
    """Edge: no cycle named is a usage error, and nothing is opened."""
    monkeypatch.setattr(sys, "argv", [str(_SCRIPT)])
    with pytest.raises(SystemExit, match="usage"):
        exec(compile(_SCRIPT.read_text(), str(_SCRIPT), "exec"), {"__name__": "__main__"})
    assert opened == {}
