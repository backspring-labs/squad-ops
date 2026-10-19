"""The console's memory view plugin (SIP-0110 Appendix A §3.11; #2182): what it registers, and that the page
calls only routes the runtime API serves."""

from __future__ import annotations

import importlib.util
import re
import tomllib
from pathlib import Path
from unittest.mock import MagicMock

_PLUGIN = Path(__file__).parents[3] / "console" / "continuum-plugins" / "squadops.memory"
_spec = importlib.util.spec_from_file_location("squadops_memory_plugin", _PLUGIN / "__init__.py")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

_PAGE = (_PLUGIN / "ui" / "src" / "MemoryPerspective.svelte").read_text(encoding="utf-8")


def _registered() -> list[dict]:
    ctx = MagicMock()
    contributions: list[dict] = []
    ctx.register_contribution.side_effect = lambda kind, data: contributions.append(
        {"type": kind, **data}
    )
    _module.register(ctx)
    return contributions


def test_the_nav_opens_the_panel_whose_component_the_page_defines():
    """Bug caught: a perspective that renders blank, because the registered component tag isn't
    the one the Svelte file defines, or the nav entry opening a perspective no panel fills; and
    the manifest and the registration disagreeing on either."""
    contributions = _registered()
    [nav] = [c for c in contributions if c["type"] == "nav"]
    [panel] = [c for c in contributions if c["type"] == "panel"]
    toml = tomllib.loads((_PLUGIN / "plugin.toml").read_text(encoding="utf-8"))["contributions"]
    defined = re.search(r'<svelte:options customElement="([^"]+)"', _PAGE).group(1)

    assert nav["target"]["panel_id"] == panel["perspective"] == "memory"
    assert panel["component"] == defined == toml["panel"][0]["component"]
    assert toml["nav"][0]["target"]["panel_id"] == nav["target"]["panel_id"]


def test_the_page_calls_only_routes_the_runtime_api_serves():
    """Bug caught: the view fetching a path the API never registered (a renamed route, a typo in a
    template literal), which the console shows only as a failed read."""
    from squadops.api.routes.cycles.projects import router as projects_router
    from squadops.api.routes.memory import memory_records_router

    served = {r.path for router in (memory_records_router, projects_router) for r in router.routes}
    called = {
        re.sub(r"\$\{[^}]+\}", "{x}", m.split("?")[0])
        for m in re.findall(r"`\$\{apiBase\}(/api/v1/[^`]*)`", _PAGE)
    }

    def matches(path: str, route: str) -> bool:
        return re.fullmatch(re.sub(r"\{[^}]+\}", r"[^/]+", route), path) is not None

    assert called, "the page names no API route: the pattern no longer reads it"
    assert {p for p in called if not any(matches(p, r) for r in served)} == set()
