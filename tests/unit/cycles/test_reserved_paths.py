"""The paths a product's owner reserves are never a cycle's to change (SIP-0112 H.35, #3155).

Declared in the product's Development Configuration and carried on its derived profile. Each
refusal is decided from the declaration and a path. The seams are entered as the live run reaches
them, over the blocking-gap tests' world (``test_blocking_gaps.py``), whose seams these share:
- the plan's authors are shown the entries, then both plan gates and an operator's plan at create
  refuse a task that names one;
- a change request whose footprint reaches one is refused at the proposal's rails
  (``test_product_change_request.py``);
- a run that changes one is refused at delivery (``test_source_backed_run.py``).

z_tower-ascension's shape is the example: the saved profile's schema, its save configuration and
its persistence service, which its own instructions put behind the owner's approval.
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest

from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.models import Run
from squadops.projects.derived_profile import ProfileInvalid, parse_profile
from squadops.projects.development_configuration import Check
from squadops.projects.profile_derivation import derive_profile
from squadops.projects.reserved_paths import naming, reached_by, reserved_among, reserving
from tests.fixtures.shared_contract.repository import recorded
from tests.unit.cycles.test_blocking_gaps import (
    _CONTEXT,
    _NPM,
    _creation_ports,
    _cycle,
    _envelope,
    _executor,
    _plan,
    _profile,
    _Registry,
    _Vault,
)
from tests.unit.projects.test_profile_derivation import _baseline, _configuration

#: What z_tower-ascension's owner reserves, in each of an entry's forms: a folder, a glob and a
#: file.
RESERVED = ("src/Server/Data", "**/SaveConfig.luau", "src/Shared/ProfileSchema.luau")
SCHEMA = "src/Shared/ProfileSchema.luau"


def _reserving(*entries: str):
    """Tally's recorded profile, with ``entries`` reserved by revision 1 of its configuration."""
    return dataclasses.replace(_profile(), reserved_paths=entries or RESERVED)


@pytest.mark.parametrize(
    ("path", "entry"),
    [
        ("src/Server/Data", "src/Server/Data"),
        ("src/Server/Data/PersistenceService.luau", "src/Server/Data"),
        ("src/Server/Data/migrations/v2.luau", "src/Server/Data"),
        ("src/Shared/SaveConfig.luau", "**/SaveConfig.luau"),
        ("src/Server/Config/SaveConfig.luau", "**/SaveConfig.luau"),
        # ``**/`` is any folders or none: the file at the root is reserved too.
        ("SaveConfig.luau", "**/SaveConfig.luau"),
        ("OtherSaveConfig.luau", None),
        (SCHEMA, SCHEMA),
        # A folder is itself and what is beneath it: a sibling whose name it opens is not.
        ("src/Server/DataStore.luau", None),
        ("src/Server/Database/Rows.luau", None),
        ("src/Shared/ProfileSchema.luau.bak", None),
        # Case is kept: another spelling is another file on the product's runner.
        ("src/shared/profileschema.luau", None),
        ("src/Client/UI/HUD.local.luau", None),
    ],
)
def test_an_entry_reserves_a_file_a_folder_with_what_is_beneath_it_or_what_its_glob_matches(
    path, entry
):
    """Bugs caught: a folder entry read as a prefix, so ``Data`` reserves ``DataStore``; a file
    under a reserved folder read as free; case folded, so the entry reserves a file the product
    doesn't have."""
    assert reserving(path, RESERVED) == entry


def test_a_bracketed_directory_is_itself_and_never_a_character_class():
    """#2512's rule, here: a Next.js dynamic route is a bracketed directory. Bug caught: the
    entry read as a class, so ``[run_id]`` reserves ``r`` and never itself."""
    reserved = ("app/runs/[run_id]/secret.ts", "app/[team]/*")

    assert reserved_among(
        ["app/runs/[run_id]/secret.ts", "app/runs/r/secret.ts", "app/[team]/page.tsx", "app/t/x"],
        reserved,
    ) == [
        ("app/runs/[run_id]/secret.ts", "app/runs/[run_id]/secret.ts"),
        ("app/[team]/page.tsx", "app/[team]/*"),
    ]


@pytest.mark.parametrize(
    ("footprint", "reached"),
    [
        (("src/Client/UI/**",), []),
        (("src/Server/DataStore.luau", "tests/**/*.spec.luau"), []),
        ((SCHEMA,), [(SCHEMA, SCHEMA)]),
        (("src/Server/Data/**",), [("src/Server/Data/**", "src/Server/Data")]),
        (("src/Shared/SaveConfig.luau",), [("src/Shared/SaveConfig.luau", "**/SaveConfig.luau")]),
        # A broad glob holds the reserved file, so it reaches it.
        (("src/**",), [("src/**", "src/Server/Data")]),
        (("src/Shared/**", "src/Client/**"), [("src/Shared/**", SCHEMA)]),
    ],
    ids=[
        "beside them",
        "a sibling by name",
        "the file itself",
        "inside a reserved folder",
        "a file a reserved glob matches",
        "a glob over everything",
        "a glob over one reserved file",
    ],
)
def test_a_footprint_reaches_a_reserved_path_it_names_or_holds(footprint, reached):
    """Bugs caught: a footprint of ``src/**`` let through over a reserved file inside it, so the
    build is licensed to change it; a narrow footprint beside a reserved path refused."""
    assert reached_by(footprint, RESERVED) == reached


def test_a_reserved_path_is_named_with_the_entry_that_reserves_it():
    assert naming([(SCHEMA, SCHEMA), ("src/Server/Data/P.luau", "src/Server/Data")]) == (
        "src/Shared/ProfileSchema.luau, src/Server/Data/P.luau (src/Server/Data)"
    )


# --- the declaration reaches the profile, and a stored profile reads it back ---------------------


def test_the_derived_profile_carries_what_its_configuration_reserves_and_reads_it_back():
    """Bugs caught: the entries declared and never derived, so every seam reads "nothing
    reserved"; or dropped between the stored document and the profile read from it."""
    checks = (Check("unit", ("python", "-m", "pytest")),)
    configuration = dataclasses.replace(_configuration(checks), reserved_paths=RESERVED)

    profile = derive_profile({"tally/report.py": b""}, configuration, _baseline(checks))

    assert profile.reserved_paths == RESERVED
    assert profile.to_document()["reserved_paths"] == list(RESERVED)
    assert parse_profile(profile.to_document()).reserved_paths == RESERVED


def test_a_profile_stored_before_the_declaration_reserves_nothing_and_is_written_as_it_was():
    """The edge: every baseline captured before H.35. Bug caught: a stored profile refused for
    the missing key, or written back with a key it never had, moving its digest."""
    stored = recorded("derived_profile", "valid")

    profile = parse_profile(stored)

    assert "reserved_paths" not in stored
    assert profile.reserved_paths == ()
    assert "reserved_paths" not in profile.to_document()


@pytest.mark.parametrize("value", ["src/Server/Data", [""], [3], {"a": 1}])
def test_a_stored_reservation_that_cant_be_read_is_refused_not_read_as_none(value):
    """Bug caught: a damaged record reading as "nothing is reserved", which licenses every
    change the owner reserved."""
    with pytest.raises(ProfileInvalid) as refused:
        parse_profile({**recorded("derived_profile", "valid"), "reserved_paths": value})

    assert refused.value.field == "reserved_paths"


# --- the plan: taught, then refused at both gates and at create ----------------------------------


async def _promotion_errors(plan: str, registry: _Registry):
    run = Run(
        "run_f", "cyc_gap", 1, "completed", "system", "cfg",
        workload_type="framing", artifact_refs=("art_plan",),
    )  # fmt: skip
    errors = await _executor(plan, registry)._reject_invalid_plan_before_workload_gate(
        run, _cycle(), "progress_plan_review"
    )
    return [e for e in errors if e.startswith("reserved_path")]


async def test_the_promotion_seam_rejects_a_plan_naming_a_reserved_path_whatever_it_argues():
    """Entered at the inter-workload gate, so the framing re-rolls told which path. Bug caught
    (#3155): a task that renames a saved field planned and built because its description says
    the task's criteria need it, where the owner reserved the schema."""
    plan = _plan("src/Client/UI/HUD.local.luau", SCHEMA, "src/Server/Data/PersistenceService.luau")
    registry = _Registry(_reserving())

    errors = await _promotion_errors(plan, registry)

    assert errors == [
        "reserved_path: Task 1 (change src/Shared/ProfileSchema.luau) declares "
        "src/Shared/ProfileSchema.luau, which the product's owner reserves from a cycle's change "
        "(its Development Configuration, revision 1, technical.reserved_paths). No task writes "
        "there: plan the change without it, or leave the work to the owner.",
        "reserved_path: Task 2 (change src/Server/Data/PersistenceService.luau) declares "
        "src/Server/Data/PersistenceService.luau (src/Server/Data), which the product's owner "
        "reserves from a cycle's change (its Development Configuration, revision 1, "
        "technical.reserved_paths). No task writes there: plan the change without it, or leave "
        "the work to the owner.",
    ]
    assert registry.asked == [
        (
            "prj-tally",
            (_CONTEXT.development_baseline_commit, _CONTEXT.development_configuration_revision),
        )
    ]


@pytest.mark.parametrize(
    ("profile", "plan"),
    [
        (_reserving(), _plan("src/Client/UI/HUD.local.luau", "src/Server/DataStore.luau")),
        (_profile(), _plan(SCHEMA)),
        (None, _plan(SCHEMA)),
    ],
    ids=["a plan beside the reserved paths", "a product that reserves none", "no profile"],
)
async def test_a_plan_clear_of_them_or_a_product_reserving_none_passes(profile, plan):
    """Bug caught: every plan on a product refused once it declares one reserved path, or a
    product with no declaration held to somebody else's."""
    assert await _promotion_errors(plan, _Registry(profile)) == []


async def test_the_dispatch_seam_fails_the_run_naming_the_path_and_its_validator():
    """Entered at the in-run plan gate (the #718/#719 rule: both seams). Bug caught: an
    operator's plan, which no framing gate reads, reaching implementation with a reserved path
    among its tasks' files."""
    from squadops.execution.execution_errors import _ExecutionError

    dev = MagicMock(role="dev", serves_roles=("dev",), enabled=True)
    squad = MagicMock(profile_id="full", agents=[dev])
    executor = _executor(_plan(SCHEMA), _Registry(_reserving()))

    with pytest.raises(_ExecutionError) as raised:
        await executor._reject_unsatisfiable_plan_at_gate(
            [("art_plan", executor._artifact_vault.ref)], squad, ["progress_plan_review"], _cycle()
        )

    assert "declares src/Shared/ProfileSchema.luau, which the product's owner reserves" in str(
        raised.value
    )
    assert raised.value.terminal.refused_validators == ("validate_reserved_paths",)


@pytest.fixture
def noop_sandbox(monkeypatch):
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


@pytest.mark.parametrize(
    ("planned", "refused"),
    [
        ((SCHEMA,), "declares src/Shared/ProfileSchema.luau, which the product's owner reserves"),
        (("src/Client/UI/HUD.local.luau",), None),
    ],
    ids=["an operator's plan naming one", "an operator's plan beside them"],
)
async def test_an_operators_plan_naming_a_reserved_path_is_refused_at_create(
    noop_sandbox, planned, refused
):
    """Entered at ``prepare_cycle``, which the create route and the Campaign launcher share. Bug
    caught: a plan an operator hands in, which no proposer was shown the reservation for,
    created and run to a refusal at delivery hours later."""
    from squadops.api.cycle_schemas import CycleCreateRequest
    from squadops.api.routes.cycles.cycles import prepare_cycle
    from squadops.cycles.models import ProjectStateConflictError

    ports = _creation_ports(_reserving(), _Vault(_plan(*planned)))
    body = CycleCreateRequest(
        squad_profile_id="full", execution_overrides={"plan_artifact_refs": ["art_plan"]}
    )

    if refused:
        with pytest.raises(ProjectStateConflictError, match=refused):
            await prepare_cycle(ports, "prj-tally", body)
        return
    prepared = await prepare_cycle(ports, "prj-tally", body)
    assert prepared.cycle.source_context == _CONTEXT


def test_the_rule_is_the_plans_own_and_reads_each_task():
    """The validator itself, for the two edges its seams don't show. Bug caught: a task naming
    two files reported for the first alone; a plan read against a profile that isn't there."""
    plan = ImplementationPlan.from_yaml(_plan("src/Client/UI/HUD.local.luau"))
    task = dataclasses.replace(
        plan.tasks[0], expected_artifacts=[SCHEMA, "src/Shared/SaveConfig.luau", "README.md"]
    )
    plan = dataclasses.replace(plan, tasks=[task])

    [error] = plan.validate_reserved_paths(_reserving())

    assert (
        "declares src/Shared/ProfileSchema.luau, src/Shared/SaveConfig.luau (**/SaveConfig.luau),"
    ) in error
    assert "README.md" not in error
    assert plan.validate_reserved_paths(None) == []


@pytest.mark.parametrize(
    ("profile", "blocked", "reserved"),
    [
        (_reserving(), False, True),
        (dataclasses.replace(_profile(_NPM), reserved_paths=RESERVED), True, True),
        (_profile(_NPM), True, False),
        (_profile(), False, False),
    ],
    ids=["reserved alone", "a gap and a reservation", "a gap alone", "neither"],
)
async def test_the_plan_authors_are_shown_the_reserved_paths_before_a_gate_refuses(
    profile, blocked, reserved
):
    """Teach, then enforce (#686), entered at the plan step ``RunProvisioning.prepare`` applies.
    Bugs caught: an author refused at the gate for a path it was never shown; the reservation
    shown only where a blocking gap is too; a product reserving none given a key it never had."""
    from squadops.execution.blocked_paths import (
        BLOCKED_PATHS_INPUT,
        RESERVED_PATHS_INPUT,
        with_blocked_paths,
    )

    executor = _executor(_plan("src/Client/UI/HUD.local.luau"), _Registry(profile))
    envelopes = [_envelope("governance.merge_plan"), _envelope("development.develop")]

    author, developer = await with_blocked_paths(
        executor._derived_profile_for, envelopes, cycle=_cycle()
    )

    assert (BLOCKED_PATHS_INPUT in author.inputs) is blocked
    assert (RESERVED_PATHS_INPUT in author.inputs) is reserved
    assert RESERVED_PATHS_INPUT not in developer.inputs
    if reserved:
        assert author.inputs[RESERVED_PATHS_INPUT] == (
            "- `src/Server/Data`\n- `**/SaveConfig.luau`\n- `src/Shared/ProfileSchema.luau`"
        )


@pytest.mark.parametrize("author", ["merger", "proposer"])
async def test_both_plan_author_paths_render_the_reserved_paths_through_the_managed_asset(author):
    """#448, #846: the prose is the asset's, and both authoring paths render it. Bug caught: the
    index reaching one path, so the merger authoring alone plans a reserved file unwarned."""
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.capabilities.handlers._plan_authoring import contract_surface_sections
    from squadops.capabilities.handlers.planning.propose import DevelopmentProposePlanTasksHandler
    from squadops.execution.blocked_paths import RESERVED_PATHS_INPUT, reserved_paths_index
    from squadops.prompts.renderer import RequestTemplateRenderer

    renderer = RequestTemplateRenderer(create_prompt_asset_source("filesystem"))
    inputs = {RESERVED_PATHS_INPUT: reserved_paths_index(_reserving())}

    if author == "merger":
        text = await contract_surface_sections(renderer, inputs)
    else:
        text = await DevelopmentProposePlanTasksHandler()._increment_sections(renderer, inputs)

    assert "## Paths this product's owner reserves: plan no task there" in text
    assert text.rstrip().endswith(
        "- `src/Server/Data`\n- `**/SaveConfig.luau`\n- `src/Shared/ProfileSchema.luau`"
    )
    assert "Where this product's checks can't run" not in text
