"""Every framing stage is told which stack the cycle builds, and that it outranks the PRD (#838).

VS (`cyc_afa934886acd`) framed for 75 minutes and designed the wrong application. **Nothing
had misbehaved.** The group_run PRD names its stack in prose — *"a coherent, runnable
full-stack vertical slice (FastAPI + React)"*, twice — the research stage summarised it
(fastapi 3, react 4, next 0), the design stage designed it, and the manifest author inherited
it through `prior_outputs`, a declared input. Every stage obediently followed the requirements,
which disagreed with the cycle's configuration and won for being the louder input.

So the fix is not "tell the design stage the stack". It is a **precedence rule** — the stack
the cycle configures outranks anything the PRD says about architecture — stated on the shared
planning base so every framing stage inherits it. Telling only the design stage would leave
the contamination path open one step upstream, in research.

Bug classes guarded:

- **the precedence going unstated**, leaving a PRD that names a stack to win by volume;
- **only the design stage being told.** Research frames the design stage's inputs and
  objective framing frames both, so a fix applied to one stage is reopened by the one before
  it;
- **the section rendering for a cycle that has no stack.** Free-form generation cycles
  (`python_cli`, `react_app`) have no stack decided for them, and asserting one is a fiction —
  the #762 lesson that a false-positiving net is worse than the gap it closes;
- **a registered stack with no narrative rendering an authoritative-looking empty heading**,
  which teaches nothing while looking like instruction;
- the section landing *before* the PRD, where a precedence rule reads as preamble rather than
  as the thing that overrides what follows;
- prose drifting into Python (#448) — the rule and the narrative are managed assets.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.planning.framing import (
    DataResearchContextHandler,
    DevelopmentDesignPlanHandler,
    StrategyFrameObjectiveHandler,
)
from squadops.capabilities.stack_narratives import stack_narrative

pytestmark = [pytest.mark.domain_capabilities]


def _renderer() -> Any:
    renderer = AsyncMock()

    async def _render(template_id: str, variables: dict[str, Any]):
        rendered = MagicMock()
        rendered.content = f"[{template_id}] {variables}"
        return rendered

    renderer.render.side_effect = _render
    return renderer


async def _section(handler, config: dict | None) -> str:
    return await handler._target_stack_section(_renderer(), {"resolved_config": config})


# --------------------------------------------------------------------------- #
# Every framing stage, not just the design one
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "handler_cls",
    [DataResearchContextHandler, StrategyFrameObjectiveHandler, DevelopmentDesignPlanHandler],
)
async def test_every_framing_stage_is_told_the_stack(handler_cls):
    """Research summarised the PRD's FastAPI mention before the design stage ever ran. A fix
    applied only to `development.design_plan` is reopened by the stage before it."""
    section = await _section(handler_cls(), {"build_profile": "nextjs_ts"})

    assert "request.target_stack_section" in section
    assert "nextjs_ts" in section


async def test_the_narrative_travels_with_the_stack_name():
    """A stack name alone teaches nothing — `nextjs_ts` does not tell a designer that route
    handlers live at `app/api/<path>/route.ts`."""
    section = await _section(DevelopmentDesignPlanHandler(), {"build_profile": "nextjs_ts"})

    assert "route.ts" in section
    assert "page.tsx" in section


# --------------------------------------------------------------------------- #
# It must not fire where no stack was decided
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "config",
    [None, {}, {"dev_capability": "python_cli"}, {"build_profile": "not_a_registered_stack"}],
)
async def test_no_section_when_the_cycle_has_no_stack(config):
    """A free-form generation cycle has no stack decided for it. Asserting one would be a
    fiction, and a net that false-positives on a working configuration is worse than the gap
    it closes (#762)."""
    assert await _section(DevelopmentDesignPlanHandler(), config) == ""


async def test_a_registered_stack_with_no_narrative_renders_nothing(monkeypatch):
    """Silence beats an authoritative-looking empty section — a heading with no content reads
    as instruction while teaching nothing."""
    monkeypatch.setattr("squadops.capabilities.stack_narratives.stack_narrative", lambda s: "")

    assert await _section(DevelopmentDesignPlanHandler(), {"build_profile": "nextjs_ts"}) == ""


# --------------------------------------------------------------------------- #
# The precedence rule itself
# --------------------------------------------------------------------------- #


def test_the_asset_states_that_the_stack_outranks_the_prd():
    """The whole point. Without this sentence the section is a hint that a PRD naming a
    different stack twice will out-argue."""
    from pathlib import Path

    asset = (
        Path(__file__).resolve().parents[3]
        / "src/squadops/prompts/request_templates/request.target_stack_section.md"
    ).read_text(encoding="utf-8")

    assert "wins" in asset and "PRD" in asset
    assert "{{stack}}" in asset and "{{stack_narrative}}" in asset


def test_the_section_is_placed_after_the_prd_it_overrides():
    """A precedence rule read before the thing it overrides is preamble. The template must
    render the PRD first, then the stack that outranks it."""
    from pathlib import Path

    template = (
        Path(__file__).resolve().parents[3]
        / "src/squadops/prompts/request_templates/request.planning_task_base.md"
    ).read_text(encoding="utf-8")

    assert template.index("{{prd}}") < template.index("{{target_stack_section}}")
    assert "target_stack_section" in template.split("---")[1], "must be a declared variable"


def test_both_registered_stacks_have_a_narrative():
    """A stack whose narrative is missing silently loses its section — the failure is a
    quieter design, not an error, so it is pinned here."""
    from squadops.capabilities.scaffold import _STACKS

    for name in _STACKS:
        assert stack_narrative(name), f"stack {name!r} has no profile narrative"


def test_narrative_lookup_is_tolerant_where_registration_is_loud():
    """`_narrative` raises at import for a BUILD_PROFILES entry missing its file — a
    registration error. This answers a different question at prompt-assembly time, about a
    stack that may legitimately not have one, and must not kill a framing stage."""
    assert stack_narrative("definitely_not_a_stack") == ""
