"""An increment's criterion file is the qa task's, at the merge and in the proposers' prompts
(SIP-0093 §15b, SIP-0109 §24cr, #2795).

#2795: a multi-role increment framing's development and qa proposers both listed the criteria's own
test files in their tasks' ``expected_artifacts``. The merge kept both claims, the plan validator
refused the dual claim (#673), and every re-roll did the same. The proposals here are invented
changes to the shared fixture's Tally, shaped like that pair: a develop task that writes the
product file and two criterion files, a develop task that writes only the third criterion file,
and two qa tasks that write all three.
"""

from __future__ import annotations

import dataclasses

import pytest

from squadops.campaigns.change_request import stored_change_request, validate_proposal
from squadops.campaigns.increment_tree import increment_criterion_files
from squadops.capabilities.handlers._plan_merger import (
    emit_merge_decisions_yaml,
    emit_plan_yaml,
    merge_proposals,
)
from squadops.cycles.acceptance_check_spec import check_subject_paths
from squadops.cycles.implementation_plan import ImplementationPlan, TypedCheck
from squadops.cycles.merge_decisions import MergeDecisions
from squadops.cycles.models import Run
from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief
from squadops.cycles.proposed_role_tasks import ProposedRoleTasks
from tests.unit.campaigns.test_product_change_request import _context, _request

pytestmark = [pytest.mark.domain_capabilities]

R1, R2, R3 = (f"checks/check_criterion_R{i}.py" for i in (1, 2, 3))


def _criterion(i: int, observable: str) -> dict:
    return {
        "id": f"R{i}",
        "statement": f"The report's criterion {i} holds",
        "surface_kind": "package",
        "surface": "tally.report",
        "observable": observable,
    }


#: Tally's request with three criteria, as the rails accepted and stored it: each criterion's test
#: is placed at ``checks/check_criterion_R<n>.py``.
_VERDICT = validate_proposal(
    _request(
        criteria=[
            _criterion(1, "render([3, 4])'s last line is 'total 7'"),
            _criterion(2, "render([])'s last line is 'total 0'"),
            _criterion(3, "render([2, -2])'s last line is 'total 0'"),
        ]
    ),
    _context(),
)
STORED = stored_change_request(_VERDICT.change_request)

_BRIEF_YAML = """\
version: 1
brief_id: brief-tally-001
objective_summary: |
  The report ends in a line that totals its amounts.
accepted_stack:
  backend: "Python package"
must_cover_requirements:
  - "render's last line is the total of its amounts"
scope_cuts: []
risk_areas: []
"""


def _dev_yaml(r3_depends_on: str = '["dev:Report total line"]', total_depends_on: str = "[]"):
    return f"""\
version: 1
proposal_id: prop-dev-tally
source_brief_id: brief-tally-001
proposing_role: development
scope_statement: |
  The total line in tally/report.py, and the criteria's tests.
tasks:
  - task_type: development.develop
    role: dev
    focus: "Report total line"
    description: |
      Append the total line to render(); write the R1 and R2 criterion tests.
    expected_artifacts:
      - "tally/report.py"
      - "{R1}"
      - "{R2}"
    acceptance_criteria:
      - check: command_exit_zero
        argv: [python, -m, py_compile, tally/report.py]
        severity: error
      - check: command_exit_zero
        argv: [python, -m, py_compile, {R1}]
        severity: error
      - check: function_defined
        file: {R2}
        name_prefix: test_
        min_count: 1
        severity: error
      - "The total line sums every amount."
    depends_on_focus: {total_depends_on}
  - task_type: development.develop
    role: dev
    focus: "Criterion test R3"
    description: |
      Write the R3 criterion test.
    expected_artifacts:
      - "{R3}"
    acceptance_criteria:
      - check: command_exit_zero
        argv: [python, -m, py_compile, {R3}]
        severity: error
    depends_on_focus: {r3_depends_on}
"""


#: A development proposal that claims no criterion file: the product file alone.
_DEV_PRODUCT_ONLY = """\
version: 1
proposal_id: prop-dev-tally
source_brief_id: brief-tally-001
proposing_role: development
scope_statement: |
  The total line in tally/report.py.
tasks:
  - task_type: development.develop
    role: dev
    focus: "Report total line"
    description: |
      Append the total line to render().
    expected_artifacts:
      - "tally/report.py"
    acceptance_criteria:
      - check: command_exit_zero
        argv: [python, -m, py_compile, tally/report.py]
        severity: error
    depends_on_focus: []
"""


def _qa_yaml(
    first_files: tuple[str, ...] = (R1, R2), r3_depends_on: str = '["dev:Report total line"]'
) -> str:
    listed = "\n".join(f'      - "{f}"' for f in first_files)
    return f"""\
version: 1
proposal_id: prop-qa-tally
source_brief_id: brief-tally-001
proposing_role: qa
scope_statement: |
  Each criterion's own test.
tasks:
  - task_type: qa.test
    role: qa
    focus: "Criterion tests R1 and R2"
    description: |
      One test per criterion, each in its own file.
    expected_artifacts:
{listed}
    acceptance_criteria:
      - check: function_defined
        file: {first_files[0]}
        name_prefix: test_
        min_count: 1
        severity: error
    depends_on_focus:
      - "dev:Report total line"
  - task_type: qa.test
    role: qa
    focus: "Criterion test R3"
    description: |
      The R3 test, in its own file.
    expected_artifacts:
      - "{R3}"
    acceptance_criteria: []
    depends_on_focus: {r3_depends_on}
"""


#: The operator note for the issue's shape: the develop task that wrote only R3's file is dropped.
_R3_DROPPED = (
    "Task dropped: development-proposed development.develop task 'Criterion test R3' "
    "(dev:criterion test r3), since every file it named is a criterion file that canonical "
    "task(s) 2 write (SIP-0093 §15b). Its description, prose criteria and criteria_refs are not "
    "carried: if it described product work, no task writes that work."
)


_GUIDANCE_YAML = """\
version: 1
guidance_id: guid-tally-001
source_brief_id: brief-tally-001
proposing_role: strategy
priority_guidance:
  - area: report
    priority: high
    rationale: "The total line is the whole change."
must_not_skip:
  - "the total line"
"""


def _increment_cycle(**overrides):
    """Tally's increment cycle on the defaults of the profile a repository-backed Campaign's
    increments run (``campaign-increment-source``): its framing runs the three proposers."""
    from squadops.contracts.cycle_request_profiles import load_profile
    from tests.unit.campaigns.test_product_increment_seams import _cycle

    defaults = dict(load_profile("campaign-increment-source").defaults)
    return dataclasses.replace(_cycle(**overrides), applied_defaults=defaults)


def _merge(dev: str | None, qa: str | None, criterion_files=(R1, R2, R3)):
    return merge_proposals(
        brief=PlanAuthoringBrief.from_yaml(_BRIEF_YAML),
        dev_proposal=ProposedRoleTasks.from_yaml(dev) if dev else None,
        qa_proposal=ProposedRoleTasks.from_yaml(qa) if qa else None,
        strategy_guidance=None,
        project_id="prj-tally",
        cycle_id="cyc_inc",
        prd_hash="abc",
        configured_contributors=["development", "qa"],
        missing_proposals=[],
        criterion_files=criterion_files,
    )


def _artifacts(plan: ImplementationPlan) -> list[list[str]]:
    return [list(t.expected_artifacts) for t in plan.tasks]


def _outcome(role: str, content: str) -> dict:
    return {
        "proposal_outcome": {"status": "success", "proposing_role": role, "yaml_content": content}
    }


# --- the wiring: plan composition, the merge handler, the framing gate ---------------------------


async def test_the_issues_shape_merges_to_one_owner_per_criterion_file_and_passes_the_gate():
    """Entered where the live cycle enters: ``generate_task_plan`` (framing), which composes the
    merge's envelope; ``GovernanceMergePlanHandler.handle``, the lead's merge on those inputs and
    the two proposals; and ``_reject_invalid_plan_before_workload_gate``, the framing gate that
    refused both of #2795's framings. Bugs caught: the criterion files never handed to the merge,
    so the dual claim is kept and refused again; the drop made but the develop task's checks on
    the dropped files kept, so the task fails ``file_not_found`` at its evaluation; a develop task
    left with no file kept in the plan; the drop unrecorded in ``merge_decisions``."""
    from squadops.capabilities.handlers.planning_tasks import GovernanceMergePlanHandler
    from squadops.cycles.task_plan import generate_task_plan
    from tests.unit.campaigns.test_product_increment_seams import _executor, _GateVault, _profile
    from tests.unit.capabilities.test_merge_plan_handler import _make_merger_context

    framing = Run("run_f", "cyc_inc", 2, "running", "system", "cfg", workload_type="framing")
    envelopes = generate_task_plan(_increment_cycle(), framing, _profile(), change_request=STORED)
    [merge] = [e for e in envelopes if e.task_type == "governance.merge_plan"]
    assert merge.inputs["increment_criterion_files"] == [
        {"criterion_id": "R1", "path": R1},
        {"criterion_id": "R2", "path": R2},
        {"criterion_id": "R3", "path": R3},
    ]
    assert [e.task_type for e in envelopes if "increment_criterion_files" in e.inputs] == [
        "governance.merge_plan"
    ]

    inputs = {
        **merge.inputs,
        "prior_outputs": {
            "lead": {"brief_outcome": {"status": "success", "yaml_content": _BRIEF_YAML}},
            "dev": _outcome("development", _dev_yaml()),
            "qa": _outcome("qa", _qa_yaml()),
            "strat": _outcome("strategy", _GUIDANCE_YAML),
        },
    }
    result = await GovernanceMergePlanHandler().handle(_make_merger_context(), inputs)

    assert result.success, result.error
    plan_yaml = result.outputs["artifacts"][0]["content"]
    plan = ImplementationPlan.from_yaml(plan_yaml)
    decisions = MergeDecisions.from_yaml(result.outputs["artifacts"][1]["content"])
    assert _artifacts(plan) == [["tally/report.py"], [R1, R2], [R3]]
    assert [t.depends_on for t in plan.tasks] == [[], [0], [0]]
    develop = plan.tasks[0]
    assert [
        (c.check, dict(c.params)) for c in develop.acceptance_criteria if isinstance(c, TypedCheck)
    ] == [("command_exit_zero", {"argv": ["python", "-m", "py_compile", "tally/report.py"]})]
    assert "The total line sums every amount." in develop.acceptance_criteria
    assert [(c.merge_action, c.source_proposal_task_keys, c.proposed_by) for c in decisions.canonical_tasks] == [
        ("modified", ["dev:report total line"], ["development"]),
        ("accepted", ["qa:criterion tests r1 and r2"], ["qa"]),
        ("merged", ["qa:criterion test r3", "dev:criterion test r3"], ["qa", "development"]),
    ]  # fmt: skip
    assert decisions.canonical_tasks[0].reason.endswith(
        f"Modified by SIP-0093 §15b: the criterion files {R1}, {R2} are written by qa task(s) "
        "qa:criterion tests r1 and r2, which claim them too, so they left this task's "
        "expected_artifacts, with the 2 typed check(s) it held on them."
    )
    assert decisions.canonical_tasks[2].reason.endswith(
        "It takes the place of development-proposed development.develop task "
        "'dev:criterion test r3' (SIP-0093 §15b): every file that task named is a criterion "
        f"file a qa task writes ({R3}), so the merge dropped it."
    )
    assert decisions.operator_notes == _R3_DROPPED
    assert plan.validate_unique_expected_artifacts() == []
    assert plan.validate_increment_criterion_files(increment_criterion_files(STORED, "")) == []

    run = Run(
        "run_f", "cyc_inc", 2, "completed", "system", "cfg",
        workload_type="framing", artifact_refs=("art_plan",),
    )  # fmt: skip
    errors = await _executor(
        _GateVault(plan_yaml, STORED)
    )._reject_invalid_plan_before_workload_gate(
        run, _increment_cycle(plan_artifact_refs=["art_cr"]), "progress_plan_review"
    )

    assert errors == []


async def test_without_the_rule_the_pair_is_the_dual_claim_the_gate_refused():
    """The control, through the same framing gate: the pair merged as before #2795 (no criterion
    files) keeps all three dual claims and every proposed task as accepted, and the gate refuses
    each. Bug caught: a fixture, or a gate harness, that no longer reproduces #2795, so the wiring
    test above passes for a reason other than the rule."""
    from tests.unit.campaigns.test_product_increment_seams import _executor, _GateVault

    plan, decisions = _merge(_dev_yaml(), _qa_yaml(), criterion_files=())
    run = Run(
        "run_f", "cyc_inc", 2, "completed", "system", "cfg",
        workload_type="framing", artifact_refs=("art_plan",),
    )  # fmt: skip
    errors = await _executor(
        _GateVault(emit_plan_yaml(plan), STORED)
    )._reject_invalid_plan_before_workload_gate(
        run, _increment_cycle(plan_artifact_refs=["art_cr"]), "progress_plan_review"
    )

    assert _artifacts(plan) == [["tally/report.py", R1, R2], [R3], [R1, R2], [R3]]
    assert {c.merge_action for c in decisions.canonical_tasks} == {"accepted"}
    dual = [e for e in errors if "both declare expected artifact" in e]
    assert [e.split(" both declare ")[1].split(" — ")[0] for e in dual] == [
        f"expected artifact '{R1}'",
        f"expected artifact '{R2}'",
        f"expected artifact '{R3}'",
    ]
    assert len(errors) == 3, errors


# --- the edges -----------------------------------------------------------------------------------


def test_with_no_qa_proposal_the_develop_tasks_keep_every_criterion_file():
    """Bug caught: a criterion file dropped from the only task that claims it, leaving it unclaimed,
    so the build never writes the test the increment is judged by."""
    plan, decisions = _merge(_dev_yaml(), None)

    assert _artifacts(plan) == [["tally/report.py", R1, R2], [R3]]
    assert [c.merge_action for c in decisions.canonical_tasks] == ["accepted", "accepted"]
    assert len(plan.tasks[0].acceptance_criteria) == 4


def test_a_criterion_file_the_qa_proposal_misses_stays_with_the_develop_task():
    """The qa proposal claims R1 but not R2. Bugs caught: R2 dropped with R1, unclaimed; or the
    develop task's check on R2 dropped though the task still writes R2."""
    plan, decisions = _merge(_dev_yaml(), _qa_yaml(first_files=(R1,)))

    assert _artifacts(plan) == [["tally/report.py", R2], [R1], [R3]]
    assert [
        dict(c.params) for c in plan.tasks[0].acceptance_criteria if isinstance(c, TypedCheck)
    ] == [
        {"argv": ["python", "-m", "py_compile", "tally/report.py"]},
        {"file": R2, "name_prefix": "test_", "min_count": 1},
    ]
    assert decisions.canonical_tasks[0].merge_action == "modified"
    assert f"the criterion files {R1} are written by" in decisions.canonical_tasks[0].reason
    assert plan.validate_unique_expected_artifacts() == []


def test_a_dual_claim_on_a_file_that_is_no_criterions_is_left_for_the_validator_to_refuse():
    """Only a criterion file has an owner the issue establishes. Bug caught: the rule widened to
    any file a qa task claims, so a qa task silently takes a product file (or a dev task's own
    test) from the task that writes it."""
    qa = _qa_yaml(first_files=(R1, R2, "tally/report.py"))

    plan, _ = _merge(_dev_yaml(), qa)

    assert _artifacts(plan) == [["tally/report.py"], [R1, R2, "tally/report.py"], [R3]]
    [refusal] = plan.validate_unique_expected_artifacts()
    assert refusal.startswith(
        "Tasks 0 (Report total line) and 1 (Criterion tests R1 and R2) both declare expected "
        "artifact 'tally/report.py'"
    )


def test_an_increment_with_no_dual_claim_merges_byte_for_byte_as_with_no_criterion_files():
    """The criterion files are claimed by qa alone. Bug caught: the rule rewriting a plan it has
    nothing to resolve in (a task re-indexed, a provenance or a check changed), so every increment
    plan moves, not only #2795's."""
    with_files = _merge(_DEV_PRODUCT_ONLY, _qa_yaml())
    plain = _merge(_DEV_PRODUCT_ONLY, _qa_yaml(), criterion_files=())

    assert emit_plan_yaml(with_files[0]) == emit_plan_yaml(plain[0])
    assert emit_merge_decisions_yaml(with_files[1]) == emit_merge_decisions_yaml(plain[1])
    assert _artifacts(with_files[0]) == [["tally/report.py"], [R1, R2], [R3]]


#: Two develop tasks that each write only a criterion file, the second depending on the first.
_DEV_CHAIN = f"""\
version: 1
proposal_id: prop-dev-tally
source_brief_id: brief-tally-001
proposing_role: development
scope_statement: |
  The total line, and the R2 and R3 criterion tests in turn.
tasks:
  - task_type: development.develop
    role: dev
    focus: "Report total line"
    description: |
      Append the total line to render(); write the R1 criterion test.
    expected_artifacts: ["tally/report.py", "{R1}"]
    depends_on_focus: []
  - task_type: development.develop
    role: dev
    focus: "Criterion test R2"
    description: |
      Write the R2 criterion test.
    expected_artifacts: ["{R2}"]
    depends_on_focus: ["dev:Report total line"]
  - task_type: development.develop
    role: dev
    focus: "Criterion test R3"
    description: |
      Write the R3 criterion test.
    expected_artifacts: ["{R3}"]
    depends_on_focus: ["dev:Criterion test R2"]
"""


@pytest.mark.parametrize(
    ("dev", "qa", "depends_on", "dropped"),
    [
        # The qa task that takes R3's place depended on the dropped task, which depended on the
        # backend task: it ends depending on the backend task.
        (_dev_yaml(), _qa_yaml(r3_depends_on='["dev:Criterion test R3"]'), [[], [0], [0]], 1),
        # The backend task depended on the dropped task (tests first), which needed nothing.
        (
            _dev_yaml(r3_depends_on="[]", total_depends_on='["dev:Criterion test R3"]'),
            _qa_yaml(),
            [[], [0], [0]],
            1,
        ),
        # A dropped task that depended on another dropped task: followed through both.
        (_DEV_CHAIN, _qa_yaml(r3_depends_on='["dev:Criterion test R3"]'), [[], [0], [0]], 2),
        # The dropped task depended on the very qa task that takes its place (an order the
        # proposal broke): the re-pointed edge would make that task depend on itself.
        (
            _dev_yaml(r3_depends_on='["qa:Criterion test R3"]'),
            _qa_yaml(r3_depends_on='["dev:Criterion test R3"]'),
            [[], [0], []],
            1,
        ),
    ],
    ids=[
        "a qa task, through to the backend task",
        "a develop task, to nothing it needed",
        "through a chain of dropped tasks",
        "never onto the task itself",
    ],
)
def test_an_edge_to_a_dropped_develop_task_is_re_pointed_to_that_tasks_own_dependencies(
    dev, qa, depends_on, dropped
):
    """Bugs caught: the edge moved onto the qa task that took the dropped task's files, which puts a
    develop task before its qa dependency (#578's order check refuses the plan) or a qa task on
    itself; the edge dropped, so the dropped task's own dependency is lost; a chain of dropped tasks
    followed one step only; or a note other than the dropped tasks' own (one naming a task as
    depending on itself)."""
    plan, decisions = _merge(dev, qa)

    assert [t.depends_on for t in plan.tasks] == depends_on
    reparsed = ImplementationPlan.from_yaml(emit_plan_yaml(plan))
    assert [t.depends_on for t in reparsed.tasks] == depends_on
    notes = decisions.operator_notes.splitlines()
    assert len(notes) == dropped
    assert all(n.startswith("Task dropped: ") for n in notes)


def test_a_dropped_tasks_unresolved_dependency_is_noted_on_the_task_its_edge_was_re_pointed_from():
    """The dropped task depended on a focus no proposal produced. Bug caught: the gap lost with the
    task, so the gate's reader isn't told the qa task's dependency resolved to nothing."""
    dev = _dev_yaml(r3_depends_on='["dev:Database migration"]')

    plan, decisions = _merge(dev, _qa_yaml(r3_depends_on='["dev:Criterion test R3"]'))

    assert [t.depends_on for t in plan.tasks] == [[], [0], []]
    assert decisions.operator_notes == (
        f"{_R3_DROPPED}\nUnresolved cross-proposal dependency: canonical task 2 depended on "
        "'dev:criterion test r3', which the merge dropped (SIP-0093 §15b), and that task's own "
        "dependency 'dev:database migration' names no task a proposer produced. Operator review "
        "required (gap_fill candidate)."
    )


# --- the merge requires the criterion files on an increment ---------------------------------------


@pytest.mark.parametrize(
    ("extra", "succeeds"),
    [
        ({}, True),
        ({"increment_change_request": STORED}, False),
        ({"increment_change_request": STORED, "increment_criterion_files": "R1"}, False),
        ({"increment_change_request": STORED, "increment_criterion_files": []}, True),
    ],
    ids=["no increment", "an increment, no list", "an increment, a list unread", "no criteria"],
)
async def test_an_increments_merge_requires_its_criterion_files(extra, succeeds):
    """Entered at ``GovernanceMergePlanHandler.handle``. Bugs caught: an increment's merge given no
    criterion files (a composer that didn't hand them) merging the dual claim the gate refuses,
    silently; or a cycle that isn't an increment, or an increment with no new criterion, refused
    for a list it has no use for."""
    from squadops.capabilities.handlers.planning_tasks import GovernanceMergePlanHandler
    from tests.unit.capabilities.test_merge_plan_handler import _make_merger_context

    inputs = {
        "resolved_config": {"plan_authoring_contributors": ["development", "qa"]},
        "prior_outputs": {
            "lead": {"brief_outcome": {"status": "success", "yaml_content": _BRIEF_YAML}},
            "dev": _outcome("development", _dev_yaml()),
            "qa": _outcome("qa", _qa_yaml()),
        },
        **extra,
    }

    result = await GovernanceMergePlanHandler().handle(_make_merger_context(), inputs)

    assert result.success is succeeds
    if not succeeds:
        assert result.error.startswith(
            "governance.merge_plan of an increment requires increment_criterion_files (#2795)"
        )


# --- what a check reads --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("check", "params", "paths"),
    [
        ("function_defined", {"file": R1, "name_prefix": "test_"}, {R1}),
        ("frontend_compiles", {"file": "web/a.jsx", "project_dir": "web"}, {"web/a.jsx", "web"}),
        ("command_exit_zero", {"argv": ["python", "-m", "py_compile", R1]}, {R1}),
        ("command_exit_zero", {"argv": ["pytest", R1]}, set()),
        ("command_exit_zero", {"argv": "python -m py_compile x.py"}, set()),
        ("count_at_least", {"glob": "checks/*.py", "min_count": 2}, {"checks/*.py"}),
        ("no_such_check", {"file": R1}, set()),
    ],
    ids=["a file", "two path params", "a safelisted command", "a refused command",
         "an argv that isn't a list", "a glob", "an unknown check"],
)  # fmt: skip
def test_a_checks_subject_paths_are_its_path_params_and_its_commands_file(check, params, paths):
    """Bugs caught: a command check's file missed, so a develop task keeps a check on a criterion
    file it no longer writes; or a refused command read as naming a file."""
    assert check_subject_paths(check, params) == frozenset(paths)


# --- the prompts, by role ------------------------------------------------------------------------


_DEV_RULE = (
    "Leave these files out of your tasks' `expected_artifacts`, and plan no task that writes"
)
_QA_RULE = "Plan a qa task whose `expected_artifacts` include each of these files."


@pytest.mark.parametrize(
    ("task_type", "shown", "not_shown"),
    [
        ("development.propose_plan_tasks", _DEV_RULE, _QA_RULE),
        ("qa.propose_plan_tasks", _QA_RULE, _DEV_RULE),
    ],
    ids=["development", "qa"],
)
async def test_each_proposer_is_told_who_writes_the_criterion_files(task_type, shown, not_shown):
    """Entered at ``generate_task_plan`` (framing), whose proposer envelopes carry the criterion
    index, then each proposer's real ``handle()`` on the shipped templates. Bugs caught: the
    development proposer told the qa author's instruction, so it writes the files into its
    develop tasks (#2795); the qa proposer told the development text, so no qa task writes them
    and the gate refuses the plan for an unwritten criterion."""
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.capabilities.handlers.planning_tasks import (
        DevelopmentProposePlanTasksHandler,
        QaProposePlanTasksHandler,
    )
    from squadops.cycles.task_plan import generate_task_plan
    from squadops.prompts.renderer import RequestTemplateRenderer
    from tests.unit.campaigns.test_product_increment_seams import _profile
    from tests.unit.capabilities.test_propose_plan_tasks import (
        _DEV_PROPOSAL_RESPONSE,
        _make_context,
        _seeded_inputs,
    )

    framing = Run("run_f", "cyc_inc", 2, "running", "system", "cfg", workload_type="framing")
    [envelope] = [
        e
        for e in generate_task_plan(_increment_cycle(), framing, _profile(), change_request=STORED)
        if e.task_type == task_type
    ]
    handler = {
        "development.propose_plan_tasks": DevelopmentProposePlanTasksHandler,
        "qa.propose_plan_tasks": QaProposePlanTasksHandler,
    }[task_type]()
    context = _make_context(_DEV_PROPOSAL_RESPONSE)
    context.ports.request_renderer = RequestTemplateRenderer(
        create_prompt_asset_source("filesystem")
    )

    await handler.handle(context, {**envelope.inputs, **_seeded_inputs()})

    messages = context.ports.llm.chat_stream_with_usage.call_args.args[0]
    prompt = "\n".join(str(m.content) for m in messages)
    assert shown in prompt
    assert not_shown not in prompt
    assert f"- R3 (package `tally.report`): `{R3}`" in prompt
