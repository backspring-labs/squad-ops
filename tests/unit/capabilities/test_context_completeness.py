"""Context completeness: an agent is shown every fact its judging checks depend on.

Seven defects in the 1.6 line were one shape — correct machinery wired to fewer paths
than it claims, so an agent is judged against a constraint it was never shown: the sole
plan author never given the contract (#846), the developer never told what the frozen
files export (#861) or how to call them (#863), the suite author importing a package
``package.json`` does not declare (roll 9), the builder failing plan-authored regex
checks its prompt never carried (roll 9), the repair re-inventing the exact name the
initial author was corrected on (roll 7). Each was individually cheap and each was found
by a two-hour roll.

This file is the instrument that makes the NEXT omission a test failure instead:

1. **The context decision is total.** Every task type the planner can dispatch is either
   in ``CONTEXT_CONTRACTS`` or in ``DECLARED_NO_CONTEXT`` — an absent entry stops being
   readable as either "needs nothing" or "nobody decided", which is the ambiguity #846
   grew in.
2. **The judged-fact → surface mapping holds** for the task types with typed judges.
3. **The facts actually render** — a declared surface that no handler puts into a prompt
   is #846's shape one layer down (the ``VerificationContract.lint()`` lesson from #849:
   a guard with no production caller).

The registry-membership half follows ``test_stack_inventory.py`` (2a); the render half
follows the fill-only wiring tests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.context_assembly import (
    CONTEXT_CONTRACTS,
    DECLARED_NO_CONTEXT,
    REPAIR_CONTEXT_CONTRACT,
    SURFACE_DOM_TESTID,
    SURFACE_FROZEN,
    SURFACE_TESTID,
    get_context_contract,
    manifest_surface_fragments,
)
from squadops.cycles.task_plan import (
    BUILD_TASK_STEPS,
    BUILDER_ASSEMBLY_TASK_STEPS,
    CORRECTION_TASK_STEPS,
    CYCLE_TASK_STEPS,
    IMPLEMENTATION_TASK_STEPS,
    REFINEMENT_TASK_STEPS,
    REPAIR_TASK_TYPES,
    WRAPUP_TASK_STEPS,
    build_planning_steps,
)
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_capabilities]

_TEMPLATES = (
    Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts" / "request_templates"
)


def _dispatched_task_types() -> set[str]:
    """Every task type the planner can put on an envelope, from the step lists it uses.

    Derived from the same constants ``generate_task_plan`` selects from — never re-typed
    (#559) — so a new step list entry lands in this set without this file changing.
    The framing sequence is built with every contributor and authored mode on, which is
    its maximal shape (proposers + ``development.author_manifest`` included).
    """
    steps = (
        CYCLE_TASK_STEPS
        + BUILD_TASK_STEPS
        + BUILDER_ASSEMBLY_TASK_STEPS
        + IMPLEMENTATION_TASK_STEPS
        + REFINEMENT_TASK_STEPS
        + CORRECTION_TASK_STEPS
        + WRAPUP_TASK_STEPS
        + build_planning_steps(["development", "qa", "strategy"], authors_manifest=True)
    )
    return {task_type for task_type, _role in steps} | set(REPAIR_TASK_TYPES)


# --- 1. the context decision is total ------------------------------------------ #


def test_every_dispatched_task_type_has_a_recorded_context_decision():
    """No task type may fall to the empty contract silently.

    Repair task types are dispatched by the correction runner under
    ``REPAIR_CONTEXT_CONTRACT`` — their curated context is declared there, so they are
    exempt from the registry requirement but still enumerated (a NEW repair type would
    land in this set and be accounted for the same way).
    """
    undecided = (
        _dispatched_task_types() - set(CONTEXT_CONTRACTS) - DECLARED_NO_CONTEXT - REPAIR_TASK_TYPES
    )
    assert not undecided, (
        f"task types dispatched with no recorded context decision: {sorted(undecided)}. "
        "Add a CONTEXT_CONTRACTS entry, or add to DECLARED_NO_CONTEXT with the reason."
    )


def test_a_task_type_is_declared_exactly_once():
    both = set(CONTEXT_CONTRACTS) & DECLARED_NO_CONTEXT
    assert not both, f"in CONTEXT_CONTRACTS and DECLARED_NO_CONTEXT at once: {sorted(both)}"


def test_declared_no_context_carries_no_stale_entries():
    """A member that nothing dispatches is a claim about a task type that does not
    exist — exactly the drift this file polices in the other direction."""
    stale = DECLARED_NO_CONTEXT - _dispatched_task_types()
    assert not stale, f"DECLARED_NO_CONTEXT entries no step list dispatches: {sorted(stale)}"


# --- 2. the judged-fact → surface mapping -------------------------------------- #
#
# One row per (judge, fact) pair with live roll evidence. These are pins: each names
# the roll that failed without it, and reverting the surface re-opens that roll.


def test_the_suite_author_sees_the_tree_it_imports_from():
    """qa.test is judged by ``tests_pass``, which requires its imports to resolve.

    Roll 9 (cyc_a92eaa4f4052): `import request from 'supertest'` against a package.json
    declaring no such package. V2 (cyc_dd3855f353c0, #787): `from .store import reset`
    against a module reachable only as `backend.store`. The frozen index carries both
    facts; the suite author's prompt-scoped artifact view is cut to its own package
    prefix and cannot substitute."""
    contract = get_context_contract("qa.test")
    assert SURFACE_FROZEN in contract.manifest_surfaces
    # judged by contract_assertions_match → the behavioral surface stays bound too
    assert contract.bind_behavioral_surface


def test_the_repair_sees_what_the_initial_author_was_corrected_with():
    """Roll 7 (cyc_0e301961f099): #861 gave the initial dev the frozen index; the
    repair re-invented `runStore` because it was blind identically, and the chain
    terminated as plan_defect on a defect no repair could see."""
    assert SURFACE_FROZEN in REPAIR_CONTEXT_CONTRACT.manifest_surfaces
    # #667's anchor surface must survive alongside, not be displaced
    assert SURFACE_TESTID in REPAIR_CONTEXT_CONTRACT.manifest_surfaces
    assert SURFACE_DOM_TESTID in REPAIR_CONTEXT_CONTRACT.manifest_surfaces


def test_the_initial_developer_keeps_its_four_surfaces():
    """#588 / pf-45 / #659 / #861 — each surface names the roll that failed without it."""
    contract = get_context_contract("development.develop")
    assert SURFACE_FROZEN in contract.manifest_surfaces
    assert len(contract.manifest_surfaces) >= 4


def test_the_sole_author_keeps_the_criteria_index():
    """#846's fix: `governance.merge_plan` authors the whole plan on every CRP without
    contributors, and binds criteria it can only bind if shown the index."""
    assert get_context_contract("governance.merge_plan").bind_criteria_index


# --- 3. the facts actually render ----------------------------------------------- #


def test_the_frozen_surface_reaches_qa_test_inputs_with_the_dependency_set():
    """The full chain for roll 9's failure: registry declares → fragments derive →
    the package.json line names the closed dependency set."""
    fragments = manifest_surface_fragments(
        get_context_contract("qa.test"), manifest_for_stack("nextjs_ts")
    )
    assert "frozen_surface" in fragments
    package_line = next(line for line in fragments["frozen_surface"] if "`package.json`" in line)
    assert "dependencies" in package_line
    assert "next" in package_line
    assert "vitest" in package_line
    assert "supertest" not in package_line


async def test_qa_frozen_section_renders_lines_and_gates_on_presence():
    from squadops.capabilities.handlers.cycle.qa_test import QATestHandler

    handler = QATestHandler()
    context = MagicMock()
    renderer = MagicMock()
    renderer.render = AsyncMock(return_value=MagicMock(content="FROZEN BLOCK"))
    context.ports.request_renderer = renderer

    lines = [
        "- `package.json` — dependencies next, react",
        "- `lib/store.ts` — functions all(table)",
    ]
    out = await handler._frozen_surface_section(context, {"frozen_surface": lines})
    assert out == "FROZEN BLOCK"
    renderer.render.assert_awaited_once_with(
        "request.qa_test_frozen_surface_appendix",
        {"frozen_lines": "\n".join(lines)},
    )

    renderer.render.reset_mock()
    assert await handler._frozen_surface_section(context, {}) == ""
    renderer.render.assert_not_awaited()


async def test_the_builder_prompt_carries_the_plan_authored_checks():
    """Roll 9's exact shape: five regex_match checks on qa_handoff.md, two of them
    sections the profile lists as optional. The builder's prompt carried none of them
    — nor its own task description — and failed typed acceptance on the two it was
    never shown. Asserted on the fallback prompt (the complete composed text)."""
    from squadops.capabilities.handlers.cycle.builder import BuilderAssembleHandler

    handler = BuilderAssembleHandler()
    context = MagicMock()
    context.ports.request_renderer = None

    inputs = {
        "subtask_focus": "Assemble QA Handoff & Startup Docs",
        "subtask_description": "Produce qa_handoff.md documenting the build.",
        "acceptance_criteria": [
            {
                "check": "regex_match",
                "file": "qa_handoff.md",
                "pattern": "## Implemented Scope",
                "count_min": 1,
                "description": "Contains Implemented Scope section",
            },
            {
                "check": "regex_match",
                "file": "qa_handoff.md",
                "pattern": "## Known Limitations",
                "count_min": 1,
                "description": "Contains Known Limitations section",
            },
            "Verify all dev artifacts are integrated.",
        ],
    }
    _rendered, prompt = await handler._build_assembly_prompt(
        context, "PRD TEXT", None, {"app/page.tsx": "code"}, {}, inputs
    )

    assert "Assemble QA Handoff & Startup Docs" in prompt
    assert "Produce qa_handoff.md documenting the build." in prompt
    assert "## Implemented Scope" in prompt
    assert "## Known Limitations" in prompt
    assert "Verify all dev artifacts are integrated." in prompt
    # typed checks render through the authoritative block, not dict-repr soup
    assert "Contract Expectations" in prompt
    assert "{'check'" not in prompt and '{"check"' not in prompt


async def test_the_builder_renderer_path_binds_the_same_blocks():
    from squadops.capabilities.handlers.cycle.builder import BuilderAssembleHandler

    handler = BuilderAssembleHandler()
    context = MagicMock()
    renderer = MagicMock()
    renderer.render = AsyncMock(return_value=MagicMock(content="RENDERED"))
    context.ports.request_renderer = renderer

    inputs = {
        "subtask_focus": "Assemble QA Handoff",
        "acceptance_criteria": [
            {"check": "regex_match", "file": "qa_handoff.md", "pattern": "## Implemented Scope"}
        ],
    }
    await handler._build_assembly_prompt(context, "PRD", None, {"a.py": "x"}, {}, inputs)

    (template_id, variables) = renderer.render.await_args.args
    assert template_id == "request.builder_assemble.build_assemble"
    assert "Assemble QA Handoff" in variables["task_section"]
    assert "## Implemented Scope" in variables["contract_expectations"]


async def test_dev_repair_fill_only_carries_the_frozen_block():
    """The registry pin alone is #849's shape — declared, read by nothing. This is the
    render half: the dev repair's fill-only appendix must receive the frozen block from
    the threaded lines, or roll 7's repair is blind again with the surface 'wired'."""
    from squadops.capabilities.handlers.impl.repair_handlers import (
        DevelopmentCorrectionRepairHandler,
    )

    handler = DevelopmentCorrectionRepairHandler()
    context = MagicMock()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="BLOCK")
    context.ports.request_renderer = renderer

    inputs = {
        "resolved_config": {"build_profile": "fullstack_fastapi_react"},
        "frozen_surface": ["- `backend/store.py` — import as `backend.store`; functions reset()"],
    }
    await handler._render_fill_only_section(context, inputs)

    fill_only_call = next(
        c
        for c in renderer.render.await_args_list
        if c.args[0] == "request.development_develop_fill_only_appendix"
    )
    assert "frozen_surface" in fill_only_call.args[1]
    frozen_call = next(
        c
        for c in renderer.render.await_args_list
        if c.args[0] == "request.development_develop_frozen_surface_appendix"
    )
    assert "backend.store" in frozen_call.args[1]["frozen_lines"]


async def test_qa_repair_renders_the_frozen_surface_through_the_qa_appendix():
    """Roll 9's failure repaired blind would re-import the phantom package; the qa
    re-authoring repair gets the same closed-set block the initial suite author gets."""
    from squadops.capabilities.handlers.impl.repair_handlers import (
        DevelopmentCorrectionRepairHandler,
        QATestRepairHandler,
    )

    handler = QATestRepairHandler()
    context = MagicMock()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="QA FROZEN BLOCK")
    context.ports.request_renderer = renderer

    lines = ["- `package.json` — dependencies next, react"]
    out = await handler._render_qa_frozen_surface_section(context, {"frozen_surface": lines})
    assert out == "QA FROZEN BLOCK"
    (template_id, variables) = renderer.render.await_args.args
    assert template_id == "request.qa_test_frozen_surface_appendix"
    assert "package.json" in variables["frozen_lines"]

    # role gate: the dev repair's flavor rides inside fill_only_section instead
    renderer.render.reset_mock()
    dev = DevelopmentCorrectionRepairHandler()
    assert await dev._render_qa_frozen_surface_section(context, {"frozen_surface": lines}) == ""
    renderer.render.assert_not_awaited()


def test_the_developer_is_shown_the_criteria_it_is_judged_by():
    """The one cell of the 2026-08-11 matrix that was WRONG when re-measured: the
    develop envelope resolves its ``criteria_refs`` into ``acceptance_criteria``
    (task_plan) and the handler renders them as the Contract Expectations block. Pinned
    here so the working path cannot regress into the predicted defect."""
    from squadops.cycles.contract_expectations import expectation_lines

    resolved = [
        {
            "check": "endpoint_defined",
            "params": {"path": "/api/runs", "methods_paths": [["POST", "/api/runs"]]},
        }
    ]
    lines = expectation_lines(resolved)
    assert lines, "resolved contract criteria must render as expectation lines"
    assert any("endpoint_defined" in line or "/api/runs" in line for line in lines)


# --- the appendix assets exist and carry the load-bearing prose ------------------ #


def test_qa_frozen_appendix_asset_is_well_formed():
    text = (_TEMPLATES / "request.qa_test_frozen_surface_appendix.md").read_text(encoding="utf-8")
    assert "template_id: request.qa_test_frozen_surface_appendix" in text
    assert "{{frozen_lines}}" in text
    # the two facts roll 9 and #787 each lacked, stated as rules
    assert "closed set of installed packages" in text
    assert "import as" in text
    # the file's own imports must be marked as description, not guidance (#787)
    assert "its own imports" in text


def test_builder_template_declares_the_new_blocks():
    text = (_TEMPLATES / "request.builder_assemble.build_assemble.md").read_text(encoding="utf-8")
    assert "{{task_section}}" in text
    assert "{{contract_expectations}}" in text
    # the instruction that plan-named sections are required on top of the profile's
    assert "required for THIS task" in text


# --- #1029: the developer is shown the success-body floor it is judged against ------


def _reference_manifest():
    from squadops.capabilities.scaffold import InterfaceManifest

    return InterfaceManifest.from_yaml(
        (
            Path(__file__).resolve().parents[3]
            / "examples"
            / "03_group_run"
            / "interface_manifest.yaml"
        ).read_text()
    )


def test_the_developer_contract_declares_the_response_surface():
    """This file's own defect class, one more instance. The frozen shell spine asserts
    the success body's floor; `development.develop` carried the error contract, the
    model surface, the testids and the frozen index, and nothing about response shape —
    so the author was judged against a fact it was never shown."""
    from squadops.capabilities.context_assembly import SURFACE_RESPONSE

    assert SURFACE_RESPONSE in CONTEXT_CONTRACTS["development.develop"].manifest_surfaces


def test_the_response_surface_renders_the_facts_the_shells_assert():
    """The registry entry is worthless if the derivation produces nothing — a declared
    surface that renders empty is #846's shape one layer down."""
    from squadops.capabilities.context_assembly import (
        SURFACE_RESPONSE,
        manifest_surface_fragments,
    )

    fragments = manifest_surface_fragments(
        CONTEXT_CONTRACTS["development.develop"], _reference_manifest()
    )
    lines = fragments[SURFACE_RESPONSE]
    assert len(lines) == 5
    create = next(line for line in lines if line.startswith("`POST /runs`"))
    assert "`id`" in create and "`title`" in create
    assert "each `participants` element carries" in create


def test_the_brief_and_the_shell_pin_the_same_shape():
    """The design's load-bearing invariant, and the reason this is one derivation.

    Bug caught: the brief and the spine drifting apart. Two independent renderings of
    "what the response must contain" is two answers, and the failure mode is the exact
    one #1029 describes — an app built to one description, judged against another —
    reintroduced inside the fix for it. Every field the shell asserts for an endpoint
    must be named in that endpoint's brief line.
    """
    import re

    from squadops.capabilities.context_assembly import (
        SURFACE_RESPONSE,
        manifest_surface_fragments,
    )
    from squadops.capabilities.verification_scaffold_emission import emit_verification_scaffold
    from tests.unit.capabilities._stack_fixtures import manifest_for_stack

    manifest = manifest_for_stack("nextjs_ts")
    brief = " ".join(
        manifest_surface_fragments(CONTEXT_CONTRACTS["development.develop"], manifest)[
            SURFACE_RESPONSE
        ]
    )
    asserted: set[str] = set()
    for f in emit_verification_scaffold(manifest).files:
        for match in re.finditer(r"for \(const k of \[([^\]]+)\]\)", f["content"]):
            asserted |= {token.strip().strip('"') for token in match.group(1).split(",")}
    assert asserted, "no shell pinned any field — this test would pass vacuously"
    missing = sorted(name for name in asserted if f"`{name}`" not in brief)
    assert not missing, f"the shells assert {missing}, which the developer's brief never names"


async def test_dev_response_section_renders_lines_and_gates_on_presence():
    """A surface nothing renders into a prompt is a declaration, not a fact the agent
    sees — the third failure this file exists to catch."""
    from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler

    handler = DevelopmentDevelopHandler()
    renderer = MagicMock()
    renderer.render = AsyncMock(return_value=MagicMock(content="RESPONSE BLOCK"))

    lines = ["`POST /runs` returns `RunEvent` — the response body carries `id`"]
    out = await handler._response_surface_section(renderer, {"response_surface": lines})
    assert out == "RESPONSE BLOCK"
    renderer.render.assert_awaited_once_with(
        "request.development_develop_response_surface_appendix",
        {"response_lines": f"- {lines[0]}"},
    )

    renderer.render.reset_mock()
    assert await handler._response_surface_section(renderer, {}) == ""
    assert await handler._response_surface_section(renderer, {"response_surface": ["  "]}) == ""
    renderer.render.assert_not_awaited()


async def test_every_dev_surface_reaches_the_fill_only_prompt():
    """The render half, generically — for all five dev surfaces, not just the newest.

    Bug caught: a surface that is declared, derived, threaded onto the envelope, turned
    into a section by its own handler method... and then never added to the template's
    variables. Every step passes its own test and the agent still never sees the fact —
    which is this file's whole subject, and a gap that existed for all four earlier
    surfaces too (mutating the assignment away left the suite green).

    Asserted on the variables the template is rendered with, because that dict is the
    last point where a fact can be silently dropped.
    """
    from squadops.capabilities.context_assembly import (
        CONTEXT_CONTRACTS as _CONTRACTS,
    )
    from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler

    handler = DevelopmentDevelopHandler()
    handler._resolved_config = {"build_profile": "nextjs_ts"}
    renderer = MagicMock()
    renderer.render = AsyncMock(side_effect=lambda tid, v: MagicMock(content=f"[{tid}]"))

    surfaces = _CONTRACTS["development.develop"].manifest_surfaces
    inputs = {surface: [f"line for {surface}"] for surface in surfaces}
    await handler._fill_only_section(renderer, inputs)

    fill_call = next(
        call for call in renderer.render.await_args_list if "fill_only_appendix" in call.args[0]
    )
    variables = fill_call.args[1]
    missing = sorted(s for s in surfaces if s not in variables)
    assert not missing, (
        f"{missing} are declared on development.develop and rendered into a section, but "
        f"never reach the fill-only template's variables — the agent never sees them"
    )


# --- #1060: the repair sees every fact the initial author was judged against --------


def test_repair_threads_every_surface_the_developer_gets():
    """The class fix, and the reason it is a test rather than a comment.

    Bug caught: `REPAIR_CONTEXT_CONTRACT` was THREE surfaces short of what the repair
    mixin already renders. `_render_fill_only_section` builds an error-contract block
    and a model-surface block, and its own comment claims "parity with develop's four
    surfaces" — neither key was ever threaded, so both rendered EMPTY from the day they
    were written. A comment asking for parity is what produced two inert renderers.

    The third was `response_surface`, and it cost a roll: `cyc_87c12c7f199e` had
    #1029's frozen-spine floor report the same shape defect on all FOUR rounds while
    every repair re-emitted `string[]` against a manifest declaring
    `list[Participant]`. The agent retrying a shape defect was the only one never shown
    the shape.

    Each of the repair's surfaces was added retroactively after a roll died on it —
    #667 the anchors, roll 7 the frozen index, #902 the stack appendix. This stops the
    next one being discovered the same way.
    """
    from squadops.capabilities.context_assembly import (
        REPAIR_CONTEXT_CONTRACT,
        manifest_surface_fragments,
    )

    manifest = _reference_manifest()
    dev = set(manifest_surface_fragments(CONTEXT_CONTRACTS["development.develop"], manifest))
    repair = set(manifest_surface_fragments(REPAIR_CONTEXT_CONTRACT, manifest))
    assert dev, "the developer surfaces must be non-empty or this passes vacuously"
    missing = sorted(dev - repair)
    assert not missing, (
        f"{missing} reach the initial author and not the repair. A repair blind to a "
        f"fact the contract judges can only re-emit the defect (#861/#667/#1060)."
    )


async def test_every_threaded_repair_surface_has_a_renderer():
    """The other half: a surface declared and never rendered is the same defect facing
    the other way — threaded onto the envelope, and never put in a prompt.

    Asserted on the variables the fill-only template is rendered with, because that dict
    is the last place a fact can be silently dropped — the step that has been missed six
    times in this codebase.
    """
    from unittest.mock import AsyncMock, MagicMock

    from squadops.capabilities.context_assembly import (
        REPAIR_CONTEXT_CONTRACT,
        manifest_surface_fragments,
    )
    from squadops.capabilities.handlers.impl.repair_handlers import (
        DevelopmentCorrectionRepairHandler,
    )

    manifest = _reference_manifest()
    surfaces = manifest_surface_fragments(REPAIR_CONTEXT_CONTRACT, manifest)

    handler = DevelopmentCorrectionRepairHandler()
    context = MagicMock()
    renderer = MagicMock()
    renderer.render = AsyncMock(side_effect=lambda tid, v: MagicMock(content=f"[{tid}]"))
    context.ports.request_renderer = renderer

    await handler._render_fill_only_section(
        context,
        {
            **surfaces,
            "resolved_config": {"build_profile": "nextjs_ts", "dev_capability": "nextjs_ts"},
        },
    )
    fill_call = next(
        c for c in renderer.render.await_args_list if "fill_only_appendix" in c.args[0]
    )
    variables = fill_call.args[1]
    # dom_testid is the qa-keyed twin of testid; the dev appendix renders one of them.
    # frozen_client_surface (#668) is qa-directed — what the suite's mock of the client
    # must honour — and is rendered by the qa repair's `_render_client_surface_section`
    # (test_repair_dom_anchor); the view author has the client's own source in the frozen
    # tree and its call in every view stub.
    expected = {s for s in surfaces if s not in ("dom_testid_surface", "frozen_client_surface")}
    missing = sorted(s for s in expected if s not in variables)
    assert not missing, f"{missing} ride the repair envelope but reach no prompt"
