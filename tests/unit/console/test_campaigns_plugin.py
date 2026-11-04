"""The console's Campaigns plugin (#2834; the 2.6 plan's Track G and D13): what it registers, that it
writes nothing, and that its reads are routes the runtime API serves."""

from __future__ import annotations

import importlib.util
import re
import tomllib
from pathlib import Path
from unittest.mock import MagicMock

_PLUGIN = Path(__file__).parents[3] / "console" / "continuum-plugins" / "squadops.campaigns"
_spec = importlib.util.spec_from_file_location("squadops_campaigns_plugin", _PLUGIN / "__init__.py")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

_SRC = _PLUGIN / "ui" / "src"
_PAGE = (_SRC / "CampaignsPerspective.svelte").read_text(encoding="utf-8")
_READS = (_SRC / "campaigns.js").read_text(encoding="utf-8")


def _registered() -> list[dict]:
    ctx = MagicMock()
    contributions: list[dict] = []
    ctx.register_contribution.side_effect = lambda kind, data: contributions.append(
        {"type": kind, **data}
    )
    _module.register(ctx)
    return contributions


def test_the_nav_opens_the_perspective_whose_component_the_page_defines():
    """Bug caught: a perspective that renders blank, because the registered tag isn't the one the
    Svelte file defines, the nav opening a perspective no panel fills, or one the console never
    registers at boot (the shell opens nothing for it)."""
    import main as console_main

    contributions = _registered()
    [nav] = [c for c in contributions if c["type"] == "nav"]
    [panel] = [c for c in contributions if c["type"] == "panel"]
    toml = tomllib.loads((_PLUGIN / "plugin.toml").read_text(encoding="utf-8"))["contributions"]
    defined = re.search(r'<svelte:options customElement="([^"]+)"', _PAGE).group(1)

    assert nav["target"]["panel_id"] == panel["perspective"] == "campaigns"
    assert panel["component"] == defined == toml["panel"][0]["component"]
    assert "campaigns" in {p[0] for p in console_main.CUSTOM_PERSPECTIVES}


def test_it_is_read_only_no_command_and_no_write():
    """D13: read-only in 2.6. Bug caught: a control (launch, rule, pause, resume, abort) slipping
    in, as a command contribution that enters the bus and the palette, or as a direct write."""
    contributions = _registered()
    toml = tomllib.loads((_PLUGIN / "plugin.toml").read_text(encoding="utf-8"))["contributions"]

    assert sorted(c["type"] for c in contributions) == ["nav", "panel"]
    assert "command" not in toml
    sources = [p.read_text(encoding="utf-8") for p in _SRC.glob("*") if p.suffix in (".js", ".svelte")]
    writes = [s for s in sources if re.search(r"method:\s*['\"](POST|PUT|PATCH|DELETE)", s)]
    assert writes == []
    assert all("executeCommand" not in s for s in sources)


def test_the_reads_are_routes_the_runtime_api_serves():
    """Bug caught: the view reading a path the API never registered (a renamed route, a typo in a
    template literal), which the console shows only as a failed read."""
    from squadops.api.routes.campaigns.campaigns import router as campaigns_router
    from squadops.api.routes.cycles.projects import router as projects_router

    served = {
        r.path
        for router in (campaigns_router, projects_router)
        for r in router.routes
        if "GET" in getattr(r, "methods", set())
    }
    templates = re.findall(r"`(\$\{(?:apiBase|base)\}[^`]*)`", _READS)
    called = set()
    for t in templates:
        path = t.split("?")[0]
        path = path.replace("${base}", "/api/v1/campaigns/{x}").replace("${apiBase}", "")
        called.add(re.sub(r"\$\{[^}]+\}", "{x}", path))

    def matches(path: str, route: str) -> bool:
        return re.fullmatch(re.sub(r"\{[^}]+\}", r"[^/]+", route), path) is not None

    assert {"/api/v1/projects", "/api/v1/campaigns", "/api/v1/campaigns/{x}/ledger"} <= called
    assert {p for p in called if not any(matches(p, r) for r in served)} == set()
