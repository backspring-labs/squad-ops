"""A repair must be told the same things the initial build was told.

The correction loop regenerates code. If it regenerates against different guidance than
the agent that wrote the code originally, it does not repair — it rewrites, and it
rewrites toward whatever its own prompt says.

That is a repeat class, and the repair path has now lost this argument four times:

* #667 — the appendix's ``testid_surface`` slot rendered empty on every repair, so
  repairs regenerated views blind to the anchor contract the first fill honoured;
* #861 — the initial dev got the frozen-file index and the repair stayed blind, so it
  re-invented ``runStore`` against a module exporting ``reset, all, insert, find`` and
  the chain terminated as a plan defect on a defect no repair could see;
* **#902 (this file)** — the per-stack fill-only template fixed the develop path while
  the repair path kept rendering the hardcoded stack-#1 asset;
* the error contract and model surface, which the repair never received at all.

The #902 instance is the expensive one because the guidance is not merely absent, it is
*wrong*: stack #1's appendix states that its client helper prefixes ``/api``. A
``nextjs_ts`` repair believed it and rewrote ``api('/api/runs')`` back to
``api('/runs')`` — roll 1's dead-UI defect, reintroduced by the correction loop on a
cycle whose initial dev output was correct (diagnostic ``cyc_831dfe6ac551``).
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.domain_capabilities]

_REPO = Path(__file__).resolve().parents[3]
_REPAIR = _REPO / "src/squadops/capabilities/handlers/impl/repair_handlers.py"
_DEVELOP = _REPO / "src/squadops/capabilities/handlers/cycle/develop.py"

#: The stack-#1 asset. Nothing may render it by name — it belongs to a capability.
_HARDCODED = "request.development_develop_fill_only_appendix"


def _rendered_template_ids(handler_cls, resolved_config: dict) -> list[str]:
    """Template ids the repair path asks the renderer for, for one resolved config."""
    import asyncio

    asked: list[str] = []

    async def _render(template_id, variables=None):
        asked.append(template_id)
        return MagicMock(content=f"<<{template_id}>>")

    ctx = MagicMock()
    ctx.ports.request_renderer = MagicMock()
    ctx.ports.request_renderer.render = AsyncMock(side_effect=_render)

    handler = handler_cls()
    inputs = {
        "resolved_config": resolved_config,
        "error_contract": ["ApiError(code, message)"],
        "model_surface": ["Run.pace_target: str"],
        "frozen_surface": ["lib/store.ts exports reset, all"],
    }
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        handler._render_fill_only_section(ctx, inputs)
    )
    return asked


def _dev_repair_handler():
    from squadops.capabilities.handlers.impl.repair_handlers import (
        DevelopmentCorrectionRepairHandler,
    )

    return DevelopmentCorrectionRepairHandler


def test_the_repair_renders_the_stacks_own_appendix_not_a_hardcoded_one():
    """Bug caught: a nextjs_ts repair is handed stack #1's client-seam semantics.

    The wrong appendix states that the helper prefixes ``/api``. The repair believes it
    and strips the prefix the initial dev correctly wrote — producing an app whose every
    UI call 404s, from a correction round, on a cycle that was fine before it.
    """
    asked = _rendered_template_ids(
        _dev_repair_handler(),
        {"build_profile": "nextjs_ts", "dev_capability": "nextjs_ts"},
    )

    assert asked, "the repair rendered no fill-only appendix at all"
    assert _HARDCODED not in asked, (
        f"the repair rendered the hardcoded stack-#1 appendix {_HARDCODED!r} for a "
        f"nextjs_ts task — that asset says the client helper prefixes /api, which is "
        f"false for this stack and is how the dead-UI defect returns"
    )
    # Positive form, not just the absence of the wrong one: asserting "not stack #1"
    # would pass against a change that rendered nothing stack-specific at all.
    assert "request.development_develop_fill_only_appendix_nextjs_ts" in asked, (
        f"the repair did not render nextjs_ts's own appendix; it asked for {asked}"
    )


def test_the_repair_receives_the_error_contract_and_model_surface():
    """Bug caught: the repair is blind to the surfaces the initial build could see.

    A repair asked to fix "500s from incorrect model field names" was the one agent in
    the chain that could not see the model's field names.
    """
    asked = _rendered_template_ids(
        _dev_repair_handler(),
        {"build_profile": "nextjs_ts", "dev_capability": "nextjs_ts"},
    )

    assert "request.development_develop_error_contract_appendix" in asked
    assert "request.development_develop_model_surface_appendix" in asked


def test_a_capability_with_no_template_gets_no_appendix():
    """Bug caught: a stack with no declared guidance is handed another stack's.

    #818's rule — wrong guidance is worse than none. `python_cli`, `python_api` and
    `react_app` all declare an empty `fill_only_template`; the capability check is what
    makes them render nothing, and it is the single authority for this.

    Note what this does NOT cover: removing the `is_scaffoldable_stack` early return
    leaves this passing, because the capability check already produces the same outcome.
    That guard is now redundant rather than load-bearing. It is left in place as a cheap
    early exit, but no test claims it is doing work — deleting it should be a deliberate
    simplification, not something a green suite silently permits.
    """
    asked = _rendered_template_ids(_dev_repair_handler(), {"build_profile": "not_a_stack"})

    assert asked == [], f"a capability with no declared template was handed {asked}"


def test_no_handler_names_the_fill_only_asset_directly():
    """Bug caught: the next hardcoded template id.

    The asset belongs to a `DevelopmentCapability`; any module naming it by string has
    pinned one stack's guidance into a path that serves all of them. Structural, because
    the failure is silent — the wrong appendix renders perfectly.
    """
    #: The capability registry is where the asset is DECLARED — stack #1 names its own
    #: template there, which is the whole mechanism. Every other mention is a stack
    #: pinned into shared code.
    declaration_site = "src/squadops/capabilities/dev_capabilities.py"

    offenders = []
    for path in sorted((_REPO / "src").rglob("*.py")):
        rel = str(path.relative_to(_REPO))
        if rel == declaration_site:
            continue
        text = path.read_text(encoding="utf-8")
        if _HARDCODED not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Constant) and node.value == _HARDCODED:
                offenders.append(f"{rel}:{node.lineno}")

    assert offenders == [], (
        f"{_HARDCODED!r} is named directly at {offenders} — resolve it through the "
        f"capability's fill_only_template so each stack gets its own"
    )


def test_the_declaration_site_still_declares_it():
    """The tripwire for the exemption above. If stack #1 stopped declaring its template,
    the sweep would pass vacuously while the mechanism it protects had been removed."""
    from squadops.capabilities.dev_capabilities import get_capability

    assert get_capability("fullstack_fastapi_react").fill_only_template == _HARDCODED


def test_both_paths_resolve_the_template_the_same_way():
    """Bug caught: the two paths drift again through a different resolution rule.

    develop resolves capability -> fill_only_template. If the repair resolved from, say,
    `build_profile` alone, the two would agree only while both config keys happen to
    match — which they do today, and which is exactly how this survived.
    """
    for path in (_REPAIR, _DEVELOP):
        source = path.read_text(encoding="utf-8")
        assert "effective_capability_name" in source, (
            f"{path.name} no longer resolves the capability the shared way"
        )
        assert "capability.fill_only_template" in source, (
            f"{path.name} no longer renders the capability's own template"
        )
