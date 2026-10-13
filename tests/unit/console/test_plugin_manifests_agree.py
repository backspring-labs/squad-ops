"""Each console plugin declares its contributions twice: ``plugin.toml`` and ``register()``.

Bug caught: the two drifting apart, so the perspective's layout depends on which one the shell
reads. The Systems plugin's had swapped two panels' priorities (#2204b found it adding a third).
"""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PLUGINS = Path(__file__).resolve().parents[3] / "console" / "continuum-plugins"


def _key(kind: str, data: dict) -> tuple:
    return (
        kind,
        data.get("component") or data.get("label") or data.get("id"),
        data.get("priority"),
    )


def _registered(plugin: Path) -> list[tuple]:
    spec = importlib.util.spec_from_file_location(f"agree_{plugin.name}", plugin / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    got: list[tuple] = []
    ctx = MagicMock()
    ctx.register_contribution.side_effect = lambda kind, data: got.append(_key(kind, data))
    module.register(ctx)
    return sorted(got)


def _declared(plugin: Path) -> list[tuple]:
    manifest = tomllib.loads((plugin / "plugin.toml").read_text(encoding="utf-8"))
    return sorted(
        _key(kind, data)
        for kind, items in manifest.get("contributions", {}).items()
        for data in items
    )


@pytest.mark.parametrize("plugin", sorted(_PLUGINS.glob("squadops.*")), ids=lambda p: p.name)
def test_the_manifest_and_register_declare_the_same_contributions(plugin):
    assert _registered(plugin) == _declared(plugin)
