"""On a product, a ``qa.test`` task names a file one of the product's runners collects
(SIP-0112 H.4 point 3, #3182).

A suite no runner collects is run by nothing. The rule is read from the runner's collection
contract (its roots and its file-name pattern) and the path. The seams are the ones the
reserved-paths rule is entered at, over the same world (``test_blocking_gaps.py``): the plan's
authors are shown what each runner collects, then both plan gates and an operator's plan at
create refuse a ``qa.test`` naming anything else.

Tally's recorded profile is the example: one runner, ``unittest``, collecting ``check_*.py``
under ``checks``.
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest
import yaml

from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.models import Run
from tests.unit.cycles.test_blocking_gaps import (
    _CONTEXT,
    _creation_ports,
    _cycle,
    _envelope,
    _executor,
    _profile,
    _Registry,
    _Vault,
)

COLLECTS = "unittest: a file named check_*.py under checks"


def _plan(*tasks: tuple[str, str]) -> str:
    """A plan of ``(task type, expected artifact)`` tasks."""
    return yaml.safe_dump(
        {
            "version": 1,
            "project_id": "prj-tally",
            "cycle_id": "cyc_gap",
            "prd_hash": "abc",
            "summary": {"total_dev_tasks": 0, "total_qa_tasks": len(tasks)},
            "tasks": [
                {
                    "task_index": i,
                    "task_type": task_type,
                    "role": "qa" if task_type == "qa.test" else "dev",
                    "focus": f"write {artifact}",
                    "description": "write it",
                    "expected_artifacts": [artifact],
                    "acceptance_criteria": [],
                }
                for i, (task_type, artifact) in enumerate(tasks)
            ],
        }
    )


def _refusal(index: int, artifact: str) -> str:
    return (
        f"qa_suite_not_collected: Task {index} (write {artifact}): qa.test declares "
        f"{artifact!r}, which no test runner of this product collects, so nothing would run it. "
        f"This product's runners collect: {COLLECTS}. Name a test file one of them collects, and "
        "leave product source to a development task."
    )


@pytest.mark.parametrize(
    ("artifact", "collected"),
    [
        ("checks/check_totals.py", True),
        # A root holds what is beneath it.
        ("checks/ledger/check_rounding.py", True),
        # The two cases the issue measured: a source file and a note.
        ("tally/count.py", False),
        ("docs/notes.md", False),
        # Named as a test, and outside every root: the runner never looks there.
        ("tests/check_totals.py", False),
        # Under the root, and not a name the runner takes: a helper, never collected.
        ("checks/helpers.py", False),
        # A test-like extension proves nothing: the pattern is the runner's own.
        ("checks/test_totals.py", False),
    ],
)
def test_a_qa_test_file_is_held_to_what_a_runner_collects(artifact, collected):
    """Bugs caught: the rule read from the file's extension, so any ``.py`` passes; a root read
    as a prefix of the name; a test-named file accepted wherever it is."""
    plan = ImplementationPlan.from_yaml(_plan(("qa.test", artifact)))

    errors = plan.validate_qa_suite_collected(_profile())

    assert errors == ([] if collected else [_refusal(0, artifact)])


def test_only_a_qa_test_is_held_and_each_of_its_files_is_named():
    """Bugs caught: a development task refused for writing source; a task naming two files
    reported for the first alone."""
    plan = ImplementationPlan.from_yaml(
        _plan(("development.develop", "tally/count.py"), ("qa.test", "checks/check_totals.py"))
    )
    qa = dataclasses.replace(
        plan.tasks[1],
        expected_artifacts=["checks/check_totals.py", "tally/count.py", "docs/notes.md"],
    )
    plan = dataclasses.replace(plan, tasks=[plan.tasks[0], qa])

    errors = plan.validate_qa_suite_collected(_profile())

    assert [e.split(": qa.test declares ")[1].split(",")[0] for e in errors] == [
        "'tally/count.py'",
        "'docs/notes.md'",
    ]


@pytest.mark.parametrize(
    "profile",
    [None, dataclasses.replace(_profile(), runners=())],
    ids=["no profile", "a product whose profile names no runner"],
)
def test_a_product_with_no_runner_on_record_is_not_held_to_one(profile):
    """Bug caught: every ``qa.test`` on such a product refused, where the missing runner is the
    profile's own gap to report."""
    plan = ImplementationPlan.from_yaml(_plan(("qa.test", "tally/count.py")))

    assert plan.validate_qa_suite_collected(profile) == []


async def test_the_promotion_seam_refuses_a_qa_test_naming_a_source_file():
    """Entered at the inter-workload gate, so the framing re-rolls told what the runner
    collects. Bug caught (#3182): the plan passing every gate, and the task shown the whole
    product to write a suite nothing runs."""
    run = Run(
        "run_f", "cyc_gap", 1, "completed", "system", "cfg",
        workload_type="framing", artifact_refs=("art_plan",),
    )  # fmt: skip
    plan = _plan(("qa.test", "checks/check_totals.py"), ("qa.test", "tally/count.py"))

    errors = await _executor(plan, _Registry(_profile()))._reject_invalid_plan_before_workload_gate(
        run, _cycle(), "progress_plan_review"
    )

    assert [e for e in errors if e.startswith("qa_suite_not_collected")] == [
        _refusal(1, "tally/count.py")
    ]


async def test_the_dispatch_seam_fails_the_run_naming_the_file_and_its_validator():
    """Entered at the in-run plan gate (the #718/#719 rule: both seams). Bug caught: an
    operator's plan, which no framing gate reads, reaching its ``qa.test`` unrefused."""
    from squadops.execution.execution_errors import _ExecutionError

    qa = MagicMock(role="qa", serves_roles=("qa",), enabled=True)
    squad = MagicMock(profile_id="full", agents=[qa])
    executor = _executor(_plan(("qa.test", "docs/notes.md")), _Registry(_profile()))

    with pytest.raises(_ExecutionError) as raised:
        await executor._reject_unsatisfiable_plan_at_gate(
            [("art_plan", executor._artifact_vault.ref)], squad, ["progress_plan_review"], _cycle()
        )

    assert "qa.test declares 'docs/notes.md', which no test runner of this product collects" in str(
        raised.value
    )
    assert "validate_qa_suite_collected" in raised.value.terminal.refused_validators


@pytest.fixture
def noop_sandbox(monkeypatch):
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


@pytest.mark.parametrize(
    ("artifact", "refused"),
    [
        ("tally/count.py", "qa.test declares 'tally/count.py', which no test runner"),
        ("checks/check_totals.py", None),
    ],
    ids=["an operator's plan naming a source file", "an operator's plan naming a collected test"],
)
async def test_an_operators_plan_is_held_to_the_runners_at_create(noop_sandbox, artifact, refused):
    """Entered at ``prepare_cycle``, which the create route and the Campaign launcher share."""
    from squadops.api.cycle_schemas import CycleCreateRequest
    from squadops.api.routes.cycles.cycles import prepare_cycle
    from squadops.cycles.models import ProjectStateConflictError

    ports = _creation_ports(_profile(), _Vault(_plan(("qa.test", artifact))))
    body = CycleCreateRequest(
        squad_profile_id="full", execution_overrides={"plan_artifact_refs": ["art_plan"]}
    )

    if refused:
        with pytest.raises(ProjectStateConflictError, match=refused):
            await prepare_cycle(ports, "prj-tally", body)
        return
    prepared = await prepare_cycle(ports, "prj-tally", body)
    assert prepared.cycle.source_context == _CONTEXT


@pytest.mark.parametrize(
    ("profile", "shown"),
    [(_profile(), True), (dataclasses.replace(_profile(), runners=()), False)],
    ids=["a product with a runner", "a product whose profile names none"],
)
async def test_the_plan_authors_are_shown_what_each_runner_collects_before_a_gate_refuses(
    profile, shown
):
    """Teach, then enforce (#686), entered at the plan step ``RunProvisioning.prepare`` applies.
    Bugs caught: an author refused at the gate for a rule it was never shown; a developer's
    task handed the plan authors' index; a product with no runner given an empty one."""
    from squadops.execution.blocked_paths import TEST_RUNNERS_INPUT, with_blocked_paths

    executor = _executor(_plan(("qa.test", "checks/check_totals.py")), _Registry(profile))
    envelopes = [_envelope("governance.merge_plan"), _envelope("development.develop")]

    author, developer = await with_blocked_paths(
        executor._derived_profile_for, envelopes, cycle=_cycle()
    )

    assert (TEST_RUNNERS_INPUT in author.inputs) is shown
    assert TEST_RUNNERS_INPUT not in developer.inputs
    if shown:
        assert author.inputs[TEST_RUNNERS_INPUT] == (
            "- `unittest`: a file named `check_*.py` under `checks`"
        )


@pytest.mark.parametrize("author", ["merger", "proposer"])
async def test_both_plan_author_paths_render_what_the_runners_collect(author):
    """#448, #846: the prose is the asset's, and both authoring paths render it. Bug caught: the
    index reaching one path, so the merger authoring alone plans an uncollected suite unwarned."""
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.capabilities.handlers._plan_authoring import contract_surface_sections
    from squadops.capabilities.handlers.planning.propose import DevelopmentProposePlanTasksHandler
    from squadops.execution.blocked_paths import TEST_RUNNERS_INPUT, runner_collection_index
    from squadops.prompts.renderer import RequestTemplateRenderer

    renderer = RequestTemplateRenderer(create_prompt_asset_source("filesystem"))
    inputs = {TEST_RUNNERS_INPUT: runner_collection_index(_profile())}

    if author == "merger":
        text = await contract_surface_sections(renderer, inputs)
    else:
        text = await DevelopmentProposePlanTasksHandler()._increment_sections(renderer, inputs)

    assert (
        "## Where this product's tests live: a `qa.test` task names a file a runner collects"
        in text
    )
    assert text.rstrip().endswith("- `unittest`: a file named `check_*.py` under `checks`")
