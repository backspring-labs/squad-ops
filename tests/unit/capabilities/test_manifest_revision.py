"""An answered question reaches the author as a revision (#811).

The gate could ask and could not be answered: `RETURNED_FOR_REVISION` stopped the sequence
and revision needed a manual retry run. A system that asks a question and cannot act on the
reply is the rubber stamp M4 replaced, wearing a better costume.

Bug classes guarded:

- the reviewer's notes never reaching the author, leaving a revision run that re-authors
  blind — the fay-6 new-dice failure with an audit trail;
- **the prior manifest not reaching the author**, which is the same failure one level
  subtler: given only a note, the author re-derives the whole design, so decisions the
  reviewer accepted come back different and they must read it all again (§5c.6's
  "revise, don't re-roll");
- a manifest author being shown the *plan* re-roll appendix — a rejected plan they did not
  write, describing rules that do not apply to them;
- the revision context escaping the declared input contract, which would make it
  contamination rather than capability;
- a first-roll authoring run rendering a revision appendix it has no reason to see.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.planning import DevelopmentAuthorManifestHandler
from squadops.cycles.manifest_authoring import AUTHORING_INPUT_CONTRACT
from squadops.cycles.task_plan import inject_contract_inputs  # noqa: F401  (import guard)

pytestmark = [pytest.mark.domain_capabilities]

_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "authored_v4"
    / "interface_manifest_roll2.yaml"
).read_text(encoding="utf-8")


def _renderer() -> Any:
    renderer = AsyncMock()

    async def _render(template_id: str, variables: dict[str, Any]):
        rendered = MagicMock()
        rendered.content = f"[{template_id}] {variables}"
        rendered.template_id = template_id
        rendered.template_version = "1"
        rendered.render_hash = "cafe"
        return rendered

    renderer.render.side_effect = _render
    return renderer


async def _section(inputs: dict[str, Any]) -> tuple[str, Any]:
    handler = DevelopmentAuthorManifestHandler()
    renderer = _renderer()
    section = await handler._revision_context_section(renderer, inputs)
    return section, renderer


async def test_the_reviewers_notes_reach_the_author():
    section, renderer = await _section(
        {"rejection_reasons": ["drop the pagination assumption and ask instead"]}
    )

    assert "drop the pagination assumption" in section
    template_ids = [c.args[0] for c in renderer.render.call_args_list]
    assert template_ids == ["request.manifest_revision_request_appendix"]


async def test_the_design_being_revised_is_shown_to_the_author():
    """The difference between a revision and a re-roll. Without the prior manifest the
    author re-derives everything, so decisions the reviewer accepted come back changed."""
    section, renderer = await _section(
        {"rejection_reasons": ["resolve the expansion question"], "prior_manifest_yaml": _MANIFEST}
    )

    variables = renderer.render.call_args_list[0].args[1]
    assert "prior_manifest" in variables
    assert "kind: interface_manifest" in variables["prior_manifest"]
    assert "expansion-gating" in variables["prior_manifest"], (
        "the author must see the unresolved decision the reviewer is answering"
    )


async def test_notes_without_a_prior_manifest_still_revise():
    """A seeded cycle, or a manifest that failed to load, still gets the reviewer's words —
    degraded, not silent."""
    section, renderer = await _section({"rejection_reasons": ["narrow the scope"]})

    assert "prior_manifest" not in renderer.render.call_args_list[0].args[1]
    assert "narrow the scope" in section


async def test_a_first_roll_renders_no_revision_appendix():
    """Nothing was returned, so there is nothing to revise — a first-roll prompt must be
    byte-identical to one from before this existed."""
    section, renderer = await _section({})

    assert section == ""
    renderer.render.assert_not_awaited()


async def test_the_manifest_author_never_sees_the_plan_reroll_appendix():
    """The inherited planning-base version renders `request.plan_reroll_rejection_appendix`,
    which shows a rejected *plan* — a document this author did not write, under rules that do
    not apply to it."""
    _, renderer = await _section({"rejection_reasons": ["revise"]})

    assert "request.plan_reroll_rejection_appendix" not in [
        c.args[0] for c in renderer.render.call_args_list
    ]


def test_the_revision_context_is_inside_the_declared_input_contract():
    """§5c.1: an undeclared input is contamination by definition. The prior manifest is
    in-cycle — this cycle's own prior output — so it belongs in the contract, declared."""
    assert "prior_manifest_yaml" in AUTHORING_INPUT_CONTRACT
    assert "rejection_reasons" in AUTHORING_INPUT_CONTRACT


def test_the_injector_threads_the_prior_manifest_onto_the_envelope():
    """The executor puts it on the forwarding rail; the composer has to carry it to the
    authoring task or the appendix renders without it."""
    from squadops.capabilities.context_assembly import get_context_contract
    from squadops.cycles.task_plan import _inject_rejection_context

    assert get_context_contract("development.author_manifest").plan_rejection_context

    inputs: dict[str, Any] = {}
    _inject_rejection_context(
        inputs,
        {"rejection_reasons": ["revise"], "prior_manifest_yaml": _MANIFEST},
        "development.author_manifest",
    )

    assert inputs["rejection_reasons"] == ["revise"]
    assert inputs["prior_manifest_yaml"] == _MANIFEST


def test_a_task_type_outside_the_registry_gets_no_revision_context():
    """Who receives rejection context is the registry's declaration (#663 S3), not the
    injector's opinion — the merger is deliberately excluded."""
    from squadops.cycles.task_plan import _inject_rejection_context

    inputs: dict[str, Any] = {}
    _inject_rejection_context(
        inputs,
        {"rejection_reasons": ["revise"], "prior_manifest_yaml": _MANIFEST},
        "governance.merge_plan",
    )

    assert inputs == {}
