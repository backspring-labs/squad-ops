"""A scenario criterion's declaration is the framework's file, and nobody else is asked about it
(#3173).

The framework lays each scenario criterion's declaration in the product's tree and adds its path
to the approved change request's footprint (#3044). Two things took that path for the squad's:
- a provider's rule about what a change may carry, asked at the creation of an increment's retry
  or repair, which refused the cycle (the 2.8 demonstration's full-path gate, ``cmp_c22ad50e1de0``);
- the plan's authors, who read it in the change request and the brief as a file to change that no
  task covered, and raised a blocking conflict the plan gate then stopped on.

Entered where a cycle's creation asks its tools' authorities (``product_view``, the one function
the creation's tool check calls), with the real Studio authority, and where the framing roles'
requests are rendered.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from adapters.remote_execution.game_dev_roblox_studio.eligibility import AUTHORITY
from squadops.campaigns.change_request import (
    PlacedCriterionFile,
    content_hash,
    stored_change_request,
    validate_proposal,
)
from squadops.campaigns.increment_tree import CHANGE_REQUEST_ARTIFACT_TYPE, approved_footprint
from squadops.cycles.models import ArtifactRef
from squadops.execution import product_view as product_view_module
from squadops.execution.product_view import product_view, squad_footprint
from tests.unit.campaigns.test_product_change_request import _context, _request
from tests.unit.cycles.test_added_module_test_luau import _renderer

SCENARIO_T1 = ".squadops/scenarios/criterion_T1.json"
SCENARIO_T2 = ".squadops/scenarios/criterion_T2.json"
#: A Script Sync product's tree, as the checkout seeds a run with it.
TREE = (
    "src/Client/UI/HUD.luau",
    "src/Server/Game.server.luau",
    "src/Shared/Rules.luau",
    "tests/run.luau",
    "tests/Rules.spec.luau",
    "docs/GAME_CONTEXT.md",
    SCENARIO_T1,
)


def _stored(*footprint: str) -> str:
    """A ruled change request whose footprint is ``footprint`` and whose one runner-placed
    criterion file is a spec, stored as the proposal stores it."""
    accepted = validate_proposal(_request(), _context()).change_request
    request = dataclasses.replace(
        accepted,
        footprint=footprint,
        criterion_files=(PlacedCriterionFile("R1", "tests/criterion_R1.spec.luau"),),
    )
    return stored_change_request(dataclasses.replace(request, content_hash=content_hash(request)))


class _Vault:
    def __init__(self, document: str) -> None:
        self.document = document

    async def retrieve(self, artifact_id):
        ref = ArtifactRef(
            artifact_id, "prj-tower", CHANGE_REQUEST_ARTIFACT_TYPE, "change_request.yaml",
            "h", len(self.document), "text/yaml", datetime(2026, 11, 17, tzinfo=UTC),
        )  # fmt: skip
        return ref, self.document.encode()


async def _view_of(monkeypatch, document: str | None):
    """The product a retry's creation shows its authorities: the real ``product_view``, over a
    checkout that holds ``TREE`` and a vault that holds the cycle's carried change request."""

    async def checkout_of(project_id, context, *, repository, registry):
        return SimpleNamespace(), SimpleNamespace()

    monkeypatch.setattr(product_view_module, "checkout_of", checkout_of)
    monkeypatch.setattr(
        product_view_module,
        "seeded_files",
        lambda tree, manifest: [(path, b"", "source", "text/plain") for path in TREE],
    )
    overrides = {"plan_artifact_refs": ["art_change"]} if document is not None else {}
    return await product_view(
        SimpleNamespace(project_id="prj-tower", pinned_commit="c" * 40),
        execution_overrides=overrides,
        repository=object(),
        registry=object(),
        vault=_Vault(document) if document is not None else None,
    )


async def _refused_by_the_studio_provider(view) -> list[tuple[str, str]]:
    rules = await AUTHORITY.broken_rules(None, project_id="prj-tower", config={}, product=view)
    return [(rule.rule, rule.why) for rule in rules]


async def test_a_retrys_creation_asks_its_provider_about_the_squads_footprint_alone(monkeypatch):
    """The bug (#3173): the retry of an increment with a scenario criterion refused at creation
    by ``footprint_scripts_only``, naming the declaration the framework itself placed. Entered at
    ``product_view`` with the change request a retry carries, and judged by the Studio provider's
    own authority."""
    document = _stored("src/Client/UI/HUD.luau", "tests/criterion_R1.spec.luau", SCENARIO_T1)

    view = await _view_of(monkeypatch, document)

    assert approved_footprint(document)[-1] == SCENARIO_T1
    assert view.footprint == ("src/Client/UI/HUD.luau", "tests/criterion_R1.spec.luau")
    assert SCENARIO_T1 in view.paths  # the tree is shown whole: only the footprint is the squad's
    assert await _refused_by_the_studio_provider(view) == []


@pytest.mark.parametrize(
    ("entry", "rule_says"),
    [
        ("tests/run.luau", "the product's test runner or its support"),
        ("docs/GAME_CONTEXT.md", "outside what a change may carry"),
        (".squadops/notes.json", "outside what a change may carry"),
        ("src/Client/UI/Hud.rbxm", "outside what a change may carry"),
    ],
    ids=["the test runner", "a document", "another file beside the scenarios", "a model"],
)
async def test_everything_else_in_the_footprint_is_still_the_providers_to_refuse(
    monkeypatch, entry, rule_says
):
    """The edge the exemption must not widen. Bug caught: every path under the framework's
    folder, or every non-script, let through with the scenario declarations, so a change could
    carry what the provider can't place."""
    document = _stored("src/Client/UI/HUD.luau", "tests/criterion_R1.spec.luau", SCENARIO_T1, entry)

    view = await _view_of(monkeypatch, document)

    assert view.footprint[-1] == entry
    [(rule, why)] = await _refused_by_the_studio_provider(view)
    assert rule == "footprint_scripts_only"
    assert why.startswith(f"{entry} is ") and rule_says in why


async def test_an_increments_first_cycle_still_has_no_footprint_to_show(monkeypatch):
    """Bug caught: a cycle with no change request yet shown an empty footprint, which reads as
    a change that touches nothing rather than one not ruled yet."""
    view = await _view_of(monkeypatch, None)

    assert view.footprint is None
    assert await _refused_by_the_studio_provider(view) == []


def test_only_the_scenario_declarations_leave_the_footprint_and_their_order_is_kept():
    document = _stored(
        SCENARIO_T2, "src/Client/UI/HUD.luau", SCENARIO_T1, "tests/criterion_R1.spec.luau"
    )

    assert squad_footprint(document) == ("src/Client/UI/HUD.luau", "tests/criterion_R1.spec.luau")


# --- the framing roles are told which footprint files the framework writes -----------------------


async def _brief_section(document: str) -> str:
    from squadops.capabilities.handlers.planning.brief import (
        GovernancePreparePlanAuthoringBriefHandler,
    )

    return await GovernancePreparePlanAuthoringBriefHandler()._increment_section(
        _renderer(), {"increment_change_request": document}
    )


async def test_the_briefs_author_is_told_the_scenario_declarations_are_the_frameworks():
    """Entered at the brief author's increment section, with the real renderer. Bug caught
    (#3173): the brief listing the scenario declarations among the files the increment changes,
    so both proposers raise a blocking conflict that no task covers them, and the plan gate
    stops for a person on every increment with a scenario criterion."""
    document = _stored(
        "src/Client/UI/HUD.luau", "tests/criterion_R1.spec.luau", SCENARIO_T1, SCENARIO_T2
    )

    section = await _brief_section(document)

    assert "### Files in the footprint that the framework writes itself" in section
    assert section.rstrip().endswith(f"- `{SCENARIO_T1}`\n- `{SCENARIO_T2}`")
    assert "Plan no task for it" in section
    assert "no conflict with the brief" in " ".join(section.split())
    # After the change request it describes, never before it.
    assert section.index("### The approved change request") < section.index(
        "### Files in the footprint that the framework writes itself"
    )


async def test_an_increment_with_no_scenario_criterion_is_sent_the_section_it_always_was():
    """The edge every increment on every other stack is. Bug caught: an empty section, or a
    blank line where it would stand, changing those increments' framing prompts."""
    document = _stored("src/Client/UI/HUD.luau", "tests/criterion_R1.spec.luau")
    with_one = _stored("src/Client/UI/HUD.luau", "tests/criterion_R1.spec.luau", SCENARIO_T1)

    section = await _brief_section(document)

    assert "the framework writes itself" not in section
    assert section.rstrip().endswith("```")
    assert (await _brief_section(with_one)).startswith(
        section.replace(document.strip(), with_one.strip()).rstrip()
    )


async def test_a_document_that_is_no_change_request_names_no_framework_file():
    """Bug caught: a framing section crashing on a change request it only describes; the gates
    that hold a plan to it are where an unreadable one is refused."""
    for document in ("criteria: []\n", "- not\n- a mapping\n", "footprint: just words\n"):
        assert "the framework writes itself" not in await _brief_section(document)


async def test_every_plan_author_is_told_a_scenario_criterions_file_is_no_conflict():
    """Entered at the proposers' and the merger's increment surfaces, with the real renderer.
    Bug caught: the proposers, who are shown the brief and not the change request, still reading
    the brief's mention of the declaration as a file no task covers."""
    from squadops.capabilities.handlers._plan_authoring import contract_surface_sections
    from squadops.capabilities.handlers.planning.propose import QaProposePlanTasksHandler

    inputs = {"increment_scenario_criteria_index": "- T1: The HUD shows how many lives are left"}

    for text in (
        await QaProposePlanTasksHandler()._increment_sections(_renderer(), inputs),
        await contract_surface_sections(_renderer(), inputs),
    ):
        assert "## The criteria this increment's scenarios check" in text
        assert "declaration file, which the framework writes itself" in text
        assert "no conflict with\nthe brief, so raise none about it." in text
        assert text.rstrip().endswith("- T1: The HUD shows how many lives are left")


def test_a_plan_refused_for_a_file_outside_the_footprint_is_told_the_files_a_task_may_plan():
    """The demonstration's second gate attempt (``run_791e229e17e9``): the refusal told the
    re-rolled framing to "plan only" a list holding both scenario declarations. Bug caught: a
    re-roll planning a task for a declaration because the gate's own words listed it, to be
    refused again by ``validate_increment_scenario_files``."""
    import yaml

    from squadops.cycles.implementation_plan import ImplementationPlan

    plan = ImplementationPlan.from_yaml(
        yaml.safe_dump(
            {
                "version": 1,
                "project_id": "prj-tower",
                "cycle_id": "cyc_x",
                "prd_hash": "h",
                "summary": {"total_dev_tasks": 0, "total_qa_tasks": 1},
                "tasks": [
                    {
                        "task_index": 0,
                        "task_type": "qa.test",
                        "role": "qa",
                        "focus": "LivesLabel format and creation spec",
                        "description": "d",
                        "expected_artifacts": ["tests/Client/UI/LivesLabel.spec.luau"],
                        "acceptance_criteria": [],
                    }
                ],
            }
        )
    )
    footprint = ("src/Client/UI/**", "src/Client/Controllers/**", SCENARIO_T1, SCENARIO_T2)

    [error] = plan.validate_increment_footprint(footprint)

    assert error.endswith(
        "plan only the files the change touches: src/Client/UI/**, src/Client/Controllers/**"
    )
    assert ".squadops" not in error
    # A task that does name a declaration is still inside the footprint, and is the other
    # validator's to refuse.
    inside = ImplementationPlan.from_yaml(
        yaml.safe_dump(
            {
                "version": 1,
                "project_id": "prj-tower",
                "cycle_id": "cyc_x",
                "prd_hash": "h",
                "summary": {"total_dev_tasks": 1, "total_qa_tasks": 0},
                "tasks": [
                    {
                        "task_index": 0,
                        "task_type": "development.develop",
                        "role": "dev",
                        "focus": "the scenario file",
                        "description": "d",
                        "expected_artifacts": [SCENARIO_T1],
                        "acceptance_criteria": [],
                    }
                ],
            }
        )
    )
    assert inside.validate_increment_footprint(footprint) == []
    [refused] = inside.validate_increment_scenario_files({SCENARIO_T1: "T1"})
    assert "The framework writes it" in refused
