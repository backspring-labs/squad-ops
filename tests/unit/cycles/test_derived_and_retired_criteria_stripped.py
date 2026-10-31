"""What the planner may not author, replayed on the plans it actually authored (#1254/#1312).

Two strips, one seam. **Derived** (#1254): the framework binds `harness_boundary` on every
bound qa suite from the scaffold's own entry modules, and the planner authored it anyway on
25 of the last 40 stored plans' qa tasks — both 1.7.1 React shakeouts carried the row twice
on `backend/tests/test_runs.py`. **Retired** (#1312): `qa_handoff.md` is no longer required,
prompted for, or produced, and a criterion over it now evaluates `file_not_found` and
rejects a correct roll.

Replayed against the two shakeouts' stored plans rather than fixtures written here, so the
guard is measured against what a real planner emitted (the 5 and 6 handoff regexes are the
rows #1252 was filed from).
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from squadops.cycles.implementation_plan import ImplementationPlan, TypedCheck
from squadops.cycles.task_plan import _applicable_acceptance

pytestmark = [pytest.mark.domain_cycles]

_REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"
_PLANS = (
    "1-7-1-react-shakeout-1-implementation_plan.yaml",
    "1-7-1-react-shakeout-2-implementation_plan.yaml",
)


def _plan(name: str) -> ImplementationPlan:
    return ImplementationPlan.from_yaml((_REPLAYS / name).read_text(encoding="utf-8"))


def _typed(task) -> list[TypedCheck]:
    return [c for c in task.acceptance_criteria if isinstance(c, TypedCheck)]


@pytest.mark.parametrize("plan_name", _PLANS)
def test_the_authored_harness_boundary_is_dropped_and_the_rest_survives(plan_name, caplog):
    """The doubling #1254 measured: the planner's row plus the framework's injection, both
    evaluated, on the same file. Dropping the wrong one would remove the check entirely —
    so this also asserts what SURVIVES."""
    plan = _plan(plan_name)
    authored = [t for t in plan.tasks if any(c.check == "harness_boundary" for c in _typed(t))]
    assert authored, "the fixture is not a plan that authored the boundary"

    for task in authored:
        with caplog.at_level(logging.WARNING, logger="squadops.cycles.task_plan"):
            caplog.clear()
            kept = _applicable_acceptance(task)
        assert [
            c for c in kept if isinstance(c, TypedCheck) and c.check == "harness_boundary"
        ] == []
        assert any("derived_check_stripped" in r.message for r in caplog.records)
        # Everything the author IS entitled to write stays: its coverage floors and prose.
        authored_own = [
            c
            for c in _typed(task)
            if c.check not in {"harness_boundary"} and c.params.get("file") != "qa_handoff.md"
        ]
        assert [c for c in kept if isinstance(c, TypedCheck)] == authored_own
        assert [c for c in task.acceptance_criteria if isinstance(c, str)] == [
            c for c in kept if isinstance(c, str)
        ]


@pytest.mark.parametrize("plan_name", _PLANS)
def test_a_declared_handoff_keeps_its_criteria(plan_name, caplog):
    """#1312 retired the framework's REQUIREMENT, not the word.

    Both stored plans declare `qa_handoff.md` in the builder task's expected_artifacts,
    so the builder produces it and those 5 and 6 criteria are satisfiable. Stripping them
    here would delete real checks on a real deliverable — and the corpus every
    verification set runs on (`examples/03_group_run/prd.md`) still asks for a document
    by that name.
    """
    plan = _plan(plan_name)
    task = next(t for t in plan.tasks if t.task_type == "builder.assemble")
    assert "qa_handoff.md" in {str(a).split("/")[-1] for a in task.expected_artifacts}

    with caplog.at_level(logging.WARNING, logger="squadops.cycles.task_plan"):
        kept = _applicable_acceptance(task)

    handoff = [c for c in _typed(task) if c.params.get("file") == "qa_handoff.md"]
    assert len(handoff) >= 5
    assert [
        c for c in kept if isinstance(c, TypedCheck) and c.params.get("file") == "qa_handoff.md"
    ] == handoff
    assert not [r for r in caplog.records if "retired_artifact_criterion_stripped" in r.message]


def test_a_criterion_over_an_undeclared_handoff_is_dropped(caplog):
    """The transition case: nothing produces the file, so the check evaluates
    `file_not_found` and rejects a correct roll. The planner has a strong prior about this
    filename — 213 of 213 builder criteria in the last 40 stored plans named it — so a
    quieter prompt alone would not have been an answer."""
    task = SimpleNamespace(
        task_index=3,
        expected_artifacts=["Dockerfile", "README.md"],
        acceptance_criteria=[
            TypedCheck(
                check="regex_match",
                params={"file": "qa_handoff.md", "pattern": "## How to Test"},
                severity="error",
            ),
            TypedCheck(
                check="regex_match",
                params={"file": "README.md", "pattern": "## Configuration"},
                severity="error",
            ),
        ],
    )
    with caplog.at_level(logging.WARNING, logger="squadops.cycles.task_plan"):
        kept = _applicable_acceptance(task)

    assert [c.params["file"] for c in kept if isinstance(c, TypedCheck)] == ["README.md"]
    assert any("retired_artifact_criterion_stripped" in r.message for r in caplog.records)


def test_a_criterion_over_another_document_is_kept():
    """Over-stripping guard, and the reason the retired strip is keyed on the FILENAME
    rather than on `regex_match`: a README or runbook check is still the author's."""
    task = SimpleNamespace(
        task_index=4,
        expected_artifacts=["README.md"],
        acceptance_criteria=[
            TypedCheck(
                check="regex_match",
                params={"file": "README.md", "pattern": "## Configuration"},
                severity="error",
            ),
            "the package documents its configuration",
        ],
    )
    kept = _applicable_acceptance(task)
    assert len(kept) == 2


def test_a_derived_check_over_a_file_the_framework_would_not_inject_it_on_is_still_dropped():
    """The rule is about WHO owns the check, not about where it would land. A
    `harness_boundary` authored on a file outside the qa namespace is not extra coverage
    the framework missed — its `entry_modules` are a guess at the scaffold's declaration,
    and a guess that happens to sit somewhere the framework does not look is worse, not
    better."""
    task = SimpleNamespace(
        task_index=7,
        expected_artifacts=["backend/helpers.py"],
        acceptance_criteria=[
            TypedCheck(
                check="harness_boundary",
                params={"file": "backend/helpers.py", "entry_modules": ["app.main"]},
                severity="error",
            )
        ],
    )
    assert _applicable_acceptance(task) == []


# ---------------------------------------------------------------------------
# #2572: an authored import of the app entry module, where the boundary is bound
# ---------------------------------------------------------------------------

#: The 2.4 window's campaign 1, increment 2 (cyc_898dc802e89b): its approved plan, and the
#: contract and manifest its implementation run loaded. Task 1's qa suite authored
#: `import_present: backend.main`, which the bound boundary forbids; the run ended
#: `contested_check`.
_WINDOW = "2-4-0-window-c1-increment-2-{}.yaml"
_T6 = "backend/tests/criteria/test_T6.py"
_ENTRY = ["backend.main", "app.main", "main"]


def _window_qa_criteria(caplog) -> list:
    """Entered where the live cycle is: ``generate_task_plan`` on the implementation run, with
    what that run loaded. Returns the acceptance criteria dispatched with the T6 suite."""
    from squadops.cycles.models import Run
    from squadops.cycles.task_plan import generate_task_plan
    from squadops.cycles.verification_contract import VerificationContract
    from squadops.stacks.scaffold import InterfaceManifest
    from tests.unit.cycles.test_increment_evaluation_wiring import PROFILE, _cycle

    def read(kind: str) -> str:
        return (_REPLAYS / _WINDOW.format(kind)).read_text(encoding="utf-8")

    run = Run("run_i", "cyc_inc", 3, "running", "system", "cfg", workload_type="implementation")
    with caplog.at_level(logging.WARNING, logger="squadops.cycles.task_plan"):
        envelopes = generate_task_plan(
            _cycle(False),
            run,
            PROFILE,
            plan=ImplementationPlan.from_yaml(read("implementation_plan")),
            contract=VerificationContract.from_yaml(read("verification_contract")),
            interface_manifest=InterfaceManifest.from_yaml(read("interface_manifest")),
        )
    [qa] = [e for e in envelopes if _T6 in e.inputs.get("expected_artifacts", [])]
    return qa.inputs["acceptance_criteria"]


def test_the_window_suites_entry_module_import_is_dropped_and_its_boundary_kept(caplog):
    """Bug caught: the two rows dispatched together again, so no suite can pass both and the
    increment's run ends `contested_check`, as cyc_898dc802e89b's did. Dropping the boundary
    instead would let a suite build its own app, so this asserts which row survives, and that
    the author's other rows all do."""
    plan = ImplementationPlan.from_yaml(
        (_REPLAYS / _WINDOW.format("implementation_plan")).read_text(encoding="utf-8")
    )
    [authored] = [t for t in plan.tasks if _T6 in t.expected_artifacts]
    assert ("import_present", "backend.main") in {
        (c.check, c.params.get("module")) for c in _typed(authored)
    }, "the fixture is not the plan that authored the import"

    dispatched = _window_qa_criteria(caplog)

    typed = [(c.check, c.params.get("file")) for c in dispatched if isinstance(c, TypedCheck)]
    assert ("harness_boundary", _T6) in typed
    assert ("import_present", _T6) not in typed
    assert ("function_defined", _T6) in typed
    assert [c for c in dispatched if isinstance(c, str)] == [
        c for c in authored.acceptance_criteria if isinstance(c, str)
    ]
    assert any(
        "entry_module_import_stripped" in r.message and "backend.main" in r.message
        for r in caplog.records
    )


def _boundary(file: str = _T6) -> TypedCheck:
    return TypedCheck(
        check="harness_boundary",
        params={"file": file, "entry_modules": _ENTRY},
        id=f"scaffold-harness:{file}",
    )


@pytest.mark.parametrize(
    ("params", "harness", "dropped"),
    [
        ({"file": _T6, "module": "backend.main"}, [_boundary()], True),
        ({"file": _T6, "module": "backend.main", "symbol": "app"}, [_boundary()], True),
        # The boundary reads `from .main import x` as module `main`, and #441 reads a dotless
        # spec as relative: each asks for an import the boundary refuses.
        ({"file": _T6, "module": ".main", "symbol": "app"}, [_boundary()], True),
        ({"file": _T6, "module": "main"}, [_boundary()], True),
        ({"file": _T6, "module": ".backend.main"}, [_boundary()], True),
        # `from . import main` satisfies a one-segment relative spec, and the boundary reads no
        # module from it, so the row can pass beside the boundary.
        ({"file": _T6, "module": ".main"}, [_boundary()], False),
        ({"file": _T6, "module": "..main"}, [_boundary()], False),
        ({"file": _T6, "module": "backend.main.routes"}, [_boundary()], True),
        ({"file": f"./{_T6}", "module": "backend.main"}, [_boundary()], True),
        # A module whose name only starts like an entry module is not inside one.
        ({"file": _T6, "module": "backend.mainframe"}, [_boundary()], False),
        ({"file": _T6, "module": "backend.store"}, [_boundary()], False),
        # No boundary on this file, or none at all (author mode): nothing contradicts the row.
        ({"file": _T6, "module": "backend.main"}, [_boundary("backend/tests/other.py")], False),
        ({"file": _T6, "module": "backend.main"}, [], False),
    ],
)
def test_an_import_is_dropped_only_where_the_bound_boundary_refuses_it(params, harness, dropped):
    """Bug caught: a strip too wide (a module merely prefixed like an entry module, a relative spec
    `from . import main` satisfies, a file the boundary isn't bound on, an author-mode suite)
    deletes a check nothing contradicts; one too narrow (a relative or dotless spec, a submodule,
    a path spelled `./`) leaves the pair."""
    from squadops.cycles.task_plan import _without_entry_module_imports

    authored = TypedCheck(check="import_present", params=params, severity="error")
    kept = _without_entry_module_imports([authored, "prose stays"], harness)
    assert kept == (["prose stays"] if dropped else [authored, "prose stays"])
