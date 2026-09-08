"""The fault-injection hook — the instrument three lines carried as plan text (#1251).

Each test names the failure it catches. The one that matters most is
``test_every_declared_fault_is_reachable_from_a_wired_seam``: a fault whose seam does not
call the injector produces a *green diagnostic*, a cycle that reads as evidence the loop
handled a fault which never happened. That is the failure mode 1.7.1's R7 diagnostic
already had once, in the other direction (#1256).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from squadops.capabilities.handlers.fault_injection import (
    DECLARATION_KEY,
    FAULTS,
    INJECTED_TASKS,
    FaultScope,
    UnknownFault,
    UnreachableFault,
    declared_faults,
    inject,
    validate_declaration,
)

pytestmark = [pytest.mark.domain_capabilities]

_SRC = Path(__file__).resolve().parents[3] / "src" / "squadops"

_SUITE = """I'll author the suite now.

```jsx:frontend/src/__tests__/runs.test.jsx
import userEvent from '@testing-library/user-event'
test('creates a run', async () => {})
```
"""


def _inject(content, task_id, faults, **kwargs):
    return inject(
        content,
        handler_name="qa_test_handler",
        task_id=task_id,
        resolved_config={DECLARATION_KEY: faults},
        **kwargs,
    )


class TestTheFaultOnlyFiresWhereItIsDeclared:
    def test_a_cycle_declaring_nothing_gets_its_emission_back_unchanged(self):
        """The whole point: this runs on every emission of every ordinary cycle."""
        assert (
            inject(
                _SUITE,
                handler_name="qa_test_handler",
                task_id="task-run_x-m006-qa.test",
                resolved_config={},
            )
            is _SUITE
        )

    def test_a_fault_declared_for_another_task_leaves_this_emission_alone(self):
        assert _inject(_SUITE, "task-run_x-m000-development.develop", ["qa_suite_absent"]) == _SUITE

    def test_a_non_string_emission_is_returned_as_is_rather_than_transformed(self):
        assert _inject(None, "task-run_x-m006-qa.test", ["qa_suite_absent"]) is None


class TestAppliedOnceWithoutState:
    """The fault must not fire on the retry, or the loop can never be seen recovering —
    and 'once' must be read off the inputs, because the container remembers nothing across
    tasks and a per-process set would make a diagnostic's result depend on scheduling."""

    def test_a_first_attempt_takes_the_fault(self):
        out = _inject(_SUITE, "task-run_x-m006-qa.test", ["qa_suite_absent"])
        assert "```" not in out

    def test_the_retry_after_an_emission_failure_runs_clean(self):
        """For a FIRST_ATTEMPT fault. (This used ``qa_suite_absent`` until #1310 widened
        that fault's scope to every emission attempt — its retry case is in
        ``TestTheScopeOfOnce``.)"""
        out = _inject(
            _SUITE,
            "task-run_x-m006-qa.test",
            ["qa_suite_at_path_prefix"],
            inputs={"emission_retry_feedback": {"reason": "no_fenced_blocks"}},
        )
        assert out == _SUITE

    def test_the_first_repair_round_takes_the_fault_and_the_second_does_not(self):
        first = _inject(_SUITE, "repair-run_x-00-qa.test_repair", ["repair_prose_only"])
        second = _inject(_SUITE, "repair-run_x-01-qa.test_repair", ["repair_prose_only"])
        assert "```" not in first
        assert second == _SUITE

    def test_the_application_is_logged_loudly_enough_to_never_be_missed(self, caplog):
        with caplog.at_level("WARNING"):
            _inject(_SUITE, "task-run_x-m006-qa.test", ["qa_suite_absent"])
        record = next(r for r in caplog.records if "fault_injection: APPLIED" in r.message)
        assert record.levelname == "WARNING"
        assert "DIAGNOSTIC" in record.getMessage()
        assert "qa_suite_absent" in record.getMessage()


class TestTheTransformsReproduceTheShapesTheyName:
    def test_the_contentless_shape_keeps_the_models_own_preamble(self):
        """#1268's shape is a sentence of intent, not empty output — a transform that
        substituted prose of ours would hand the handler an emission no roll produced."""
        out = _inject(_SUITE, "task-run_x-m006-qa.test", ["qa_suite_absent"])
        assert out == "I'll author the suite now."

    def test_an_emission_that_is_nothing_but_a_fence_still_yields_a_sentence(self):
        out = _inject("```jsx:a.jsx\nx\n```\n", "task-run_x-m006-qa.test", ["qa_suite_absent"])
        assert out and "```" not in out

    def test_the_path_prefix_shape_addresses_the_fence_under_a_literal_path_segment(self):
        out = _inject(_SUITE, "task-run_x-m006-qa.test", ["qa_suite_at_path_prefix"])
        assert "```jsx:path/frontend/src/__tests__/runs.test.jsx" in out
        assert "test('creates a run'" in out, "only the address changes, never the body"

    def test_an_unaddressed_fence_is_left_alone_by_the_path_prefix_shape(self):
        """A bare fence addresses no file, so prefixing it would invent an address the
        model never gave — and the readout that reads `path/` would then be reading us."""
        content = "here:\n```\nplain\n```\n"
        assert _inject(content, "task-run_x-m006-qa.test", ["qa_suite_at_path_prefix"]) == content

    def test_the_own_frame_shape_is_roll_4s_one_line_import_edit(self):
        out = _inject(_SUITE, "task-run_x-m006-qa.test", ["qa_suite_own_frame_failure"])
        assert "import userEvent from '@testing-library/react'" in out
        assert "@testing-library/user-event" not in out

    def test_an_emission_with_no_such_import_is_left_unchanged_rather_than_mangled(self):
        """Reported as applied-but-unchanged rather than silently mangling an emission it
        cannot break: the diagnostic's record then shows the fault did not bite."""
        content = "```py:backend/tests/test_runs.py\ndef test_x(): pass\n```\n"
        out = _inject(content, "task-run_x-m006-qa.test", ["qa_suite_own_frame_failure"])
        assert out == content


class TestTheDeclarationIsRefusedRatherThanIgnored:
    def test_an_unknown_fault_name_is_refused_and_the_known_ones_are_listed(self):
        with pytest.raises(UnknownFault) as exc:
            validate_declaration({DECLARATION_KEY: ["qa_suite_absent", "no_such_fault"]})
        assert "no_such_fault" in str(exc.value)
        assert "qa_suite_absent" in str(exc.value)

    def test_a_fault_whose_seam_is_unwired_is_refused_at_declaration_time(self, monkeypatch):
        """The failure this exists for: a fault that can never fire produces a green
        diagnostic, which reads as the loop handling a fault that never happened."""
        from squadops.capabilities.handlers import fault_injection as fi

        monkeypatch.setattr(fi, "INJECTED_TASKS", frozenset({"development.develop"}))
        with pytest.raises(UnreachableFault) as exc:
            fi.validate_declaration({DECLARATION_KEY: ["qa_suite_absent"]})
        assert "qa.test" in str(exc.value)

    def test_a_valid_declaration_returns_its_names_in_order(self):
        assert validate_declaration(
            {DECLARATION_KEY: ["repair_prose_only", "qa_suite_absent"]}
        ) == ("repair_prose_only", "qa_suite_absent")

    def test_a_single_name_is_accepted_as_well_as_a_list(self):
        assert declared_faults({DECLARATION_KEY: "qa_suite_absent"}) == ("qa_suite_absent",)

    def test_no_declaration_at_all_is_not_an_error(self):
        assert validate_declaration(None) == ()
        assert validate_declaration({}) == ()


def _calls_inject(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"inject", "inject_fault"}
        for node in ast.walk(tree)
    )


def test_every_declared_fault_is_reachable_from_a_wired_seam():
    """Every task in ``INJECTED_TASKS`` has a handler seam that actually calls the injector.

    `INJECTED_TASKS` is what turns an unwired fault into a create-time refusal, so a stale
    entry in it would restore the silent no-op it exists to prevent — the declaration would
    validate and the fault would never fire.
    """
    wired = [
        path for path in (_SRC / "capabilities" / "handlers").rglob("*.py") if _calls_inject(path)
    ]
    assert wired, "no handler calls the injector — every fault declaration is a no-op"

    from squadops.tasks.task_types import TaskType

    capabilities: set[str] = set()
    for path in wired:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("_task_type = "):
                declared = stripped.split("=", 1)[1].strip().strip("\"'")
                # #559: handlers declare the member, not the string.
                if declared.startswith("TaskType."):
                    declared = TaskType[declared.removeprefix("TaskType.")].value
                capabilities.add(declared)
    # cycle/base.py is the shared seam for every _CycleTaskHandler subclass, so a
    # capability declared in a module that inherits it is wired too.
    from squadops.capabilities.handlers.impl import repair_handlers

    capabilities |= {
        getattr(obj, "_task_type")
        for obj in vars(repair_handlers).values()
        if isinstance(obj, type) and getattr(obj, "_task_type", None)
    }
    missing = sorted(INJECTED_TASKS - capabilities)
    assert not missing, (
        f"INJECTED_TASKS claims {missing} are wired, but no handler module that calls the "
        "injector declares them — a fault for those tasks would validate and never fire"
    )


def test_every_fault_names_the_roll_it_came_from_and_the_prediction_it_exercises():
    """A fault with no provenance is a synthetic defect dressed as a real one. The record
    of a diagnostic cites `found_in`; the pre-registration cites `exercises`."""
    for name, fault in FAULTS.items():
        assert fault.found_in.strip(), f"{name} names no roll"
        assert "#" in fault.found_in, f"{name}'s provenance cites no issue"
        assert fault.exercises.strip(), f"{name} names no prediction"
        assert fault.task in INJECTED_TASKS, f"{name} targets an unwired task"


class TestTheFaultReachesTheHandlerTheLiveCycleCalls:
    """Wiring, not transform: entered at ``handle()`` — the call the executor makes.

    A transform test proves the transform. What has to be true for a diagnostic to be
    worth running is that a fault declared on the cycle actually changes what the handler
    banks, and the paired control is the same call with the declaration removed.
    """

    def _context(self, task_id, emission):
        from unittest.mock import AsyncMock, MagicMock

        from squadops.llm.models import ChatMessage

        ctx = MagicMock()
        ctx.task_id = task_id
        chat = AsyncMock(return_value=ChatMessage(role="assistant", content=emission))
        ctx.ports.llm.chat = chat
        ctx.ports.llm.chat_stream_with_usage = chat
        assembled = MagicMock()
        assembled.content = "system prompt"
        ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
        ctx.ports.request_renderer = None
        ctx.ports.llm_observability = None
        ctx.correlation_context = None
        return ctx

    async def _repair(self, declaration):
        from squadops.capabilities.handlers.impl.repair_handlers import QATestRepairHandler

        emission = (
            "Here is the repaired suite.\n\n"
            "```python:backend/tests/test_runs.py\n"
            "def test_ok(client):\n    assert True\n"
            "```\n"
        )
        handler = QATestRepairHandler()
        inputs = {"prd": "a prd", "resolved_config": dict(declaration)}
        result = await handler.handle(
            self._context("repair-run_x-00-qa.test_repair", emission), inputs
        )
        return [a["name"] for a in (result.outputs or {}).get("artifacts", [])]

    async def test_without_a_declaration_the_repair_banks_the_suite_it_emitted(self):
        assert "backend/tests/test_runs.py" in await self._repair({})

    async def test_with_the_declaration_the_same_emission_reaches_the_handler_prose_only(self):
        """The #1273 shape, produced on demand: the repair emits intent and no file, so the
        loop must refund the round rather than verify it."""
        names = await self._repair({DECLARATION_KEY: ["repair_prose_only"]})
        assert "backend/tests/test_runs.py" not in names


class TestTheDeclarationSurvivesTheWireItArrivesOn:
    """#1298: `execution_overrides` reaches a cycle through `cycles create --set k=v`, whose
    values are strings with no coercion. A declaration of two faults has no other way to
    arrive, so a comma-separated string is the list — without it the chained diagnostic
    could not be launched at all."""

    def test_two_faults_arrive_as_one_comma_string(self):
        assert declared_faults(
            {DECLARATION_KEY: "qa_suite_own_frame_failure,repair_prose_only"}
        ) == ("qa_suite_own_frame_failure", "repair_prose_only")

    def test_the_comma_form_validates_the_same_as_a_list(self):
        comma = validate_declaration({DECLARATION_KEY: "qa_suite_absent,repair_prose_only"})
        listed = validate_declaration({DECLARATION_KEY: ["qa_suite_absent", "repair_prose_only"]})
        assert comma == listed

    def test_surrounding_whitespace_is_not_part_of_a_name(self):
        assert declared_faults({DECLARATION_KEY: " qa_suite_absent , repair_prose_only "}) == (
            "qa_suite_absent",
            "repair_prose_only",
        )

    def test_an_empty_segment_is_dropped_rather_than_becoming_a_nameless_fault(self):
        """A trailing comma is a typo, not a declaration of nothing — and an empty name
        would be refused as unknown, failing the cycle for the wrong reason."""
        assert declared_faults({DECLARATION_KEY: "qa_suite_absent,"}) == ("qa_suite_absent",)
        assert declared_faults({DECLARATION_KEY: ","}) == ()

    def test_a_single_name_still_arrives_whole(self):
        assert declared_faults({DECLARATION_KEY: "qa_suite_absent"}) == ("qa_suite_absent",)


class TestThePythonFaultSurvivesTheEmissionSeamAndDiesAtItsOwnFrame:
    """#1352: the pytest shape must pass the emission seam's static checks — a name the
    module never binds is exactly what ``undefined_names`` (#689) refuses, and the handler's
    self-eval then removed the fault before the suite ever ran (``cyc_375bdea6e140``) — and
    it must still fail at the suite's own frame with a shape ``_OWN_FRAME_SHAPES["pytest"]``
    declares. Both halves, or the fault reaches no seam and the record says so."""

    _SUITE = "```python:tests/test_runs.py\ndef test_creates_a_run():\n    assert True\n```\n"

    def _injected_module(self) -> str:
        out = _inject(self._SUITE, "task-run_x-m004-qa.test", ["qa_suite_own_frame_failure"])
        assert out != self._SUITE, "the fault did not bite the pytest suite"
        return out.split("```python:tests/test_runs.py\n", 1)[1].split("```", 1)[0]

    async def test_the_injected_suite_passes_the_undefined_names_check_the_seam_runs(
        self, tmp_path
    ):
        """Bug caught: the NameError shape. The framework's own check, on the injected file."""
        from squadops.cycles.acceptance_checks import UndefinedNamesCheck

        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_runs.py").write_text(self._injected_module())
        outcome = await UndefinedNamesCheck().evaluate({"file": "tests/test_runs.py"}, tmp_path)
        assert outcome.status == "passed", outcome
        # The paired control — the shape this replaced — is exactly what the check refuses.
        (tmp_path / "tests" / "test_runs.py").write_text(
            "def test_creates_a_run():\n    __squadops_injected_fault__()\n"
        )
        refused = await UndefinedNamesCheck().evaluate({"file": "tests/test_runs.py"}, tmp_path)
        assert refused.status == "failed"
        assert "__squadops_injected_fault__" in refused.reason

    def test_the_injected_case_raises_the_declared_own_frame_shape_at_its_own_frame(self, tmp_path):
        """Bug caught: a static-clean fault that dies in a callee's frame, or in a shape the
        runner does not declare — routed to the dev chain, L7 unexercised again."""
        import traceback

        from squadops.capabilities.handlers.test_runner import suite_defects

        path = tmp_path / "test_runs.py"
        path.write_text(self._injected_module())
        namespace: dict = {}
        exec(compile(path.read_text(), str(path), "exec"), namespace)  # noqa: S102
        with pytest.raises(TypeError) as excinfo:
            namespace["test_creates_a_run"]()
        innermost = traceback.extract_tb(excinfo.value.__traceback__)[-1]
        assert innermost.filename == str(path)
        assert "__squadops_injected_fault__" in str(excinfo.value)
        row = {
            "file": str(path),
            "title": "creates a run",
            "exception": "TypeError",
            "messages": [str(excinfo.value)],
            "frames": [{"file": str(path), "line": innermost.lineno}],
        }
        assert len(suite_defects([row], [], "pytest")) == 1


def test_the_drivers_fault_normaliser_agrees_with_the_frameworks():
    """The driver keeps its own copy on purpose — it must refuse a counting roll even
    against a deploy whose framework predates this module (`driver:76-78`) — so the two are
    held to each other here. A divergence would mean the driver's refusal and the agent's
    application disagree about what was declared, which is how a diagnostic reports a fault
    it did not run.
    """
    import sys

    sys.path.insert(0, str(_SRC.parents[1] / "scripts" / "dev"))
    from verification_set_driver import declared_fault_names

    cases = [
        None,
        {},
        {DECLARATION_KEY: ""},
        {DECLARATION_KEY: "qa_suite_absent"},
        {DECLARATION_KEY: "qa_suite_absent,repair_prose_only"},
        {DECLARATION_KEY: " qa_suite_absent , repair_prose_only "},
        {DECLARATION_KEY: "qa_suite_absent,"},
        {DECLARATION_KEY: ","},
        {DECLARATION_KEY: ["qa_suite_absent", "repair_prose_only"]},
        {DECLARATION_KEY: ("qa_suite_absent",)},
    ]
    for case in cases:
        assert declared_fault_names(case) == declared_faults(case), f"disagree on {case!r}"


#: Two emissions a real qa.test could produce. The second is the one the first live
#: diagnostic actually emitted (`cyc_b7c5da74eb5b`): a vitest suite importing nothing from
#: `@testing-library/user-event`. Every declared fault must bite on BOTH.
_EMISSIONS = {
    "with the user-event import": _SUITE,
    "without it": (
        "I'll author the suite.\n\n"
        "```jsx:frontend/src/__tests__/runs.test.jsx\n"
        "import { render, screen } from '@testing-library/react'\n"
        "import RunsListView from '../views/RunsListView'\n\n"
        "test('renders the runs list', async () => {\n"
        "  render(<RunsListView runs={[]} />)\n"
        "  expect(screen.getByTestId('runs-list')).toBeInTheDocument()\n"
        "})\n"
        "```\n"
    ),
    # #1304: the shape two consecutive live diagnostics actually met. The qa task the
    # planner scheduled first was the BACKEND suite, and a vitest transform cannot bite a
    # Python file — so L7 went unexercised twice while the fault reported itself applied.
    "a pytest suite": (
        "Here is the backend suite.\n\n"
        "```python:backend/tests/test_runs.py\n"
        "import pytest\n"
        "from fastapi.testclient import TestClient\n\n\n"
        "def test_leave_run_happy_path(client):\n"
        '    """The participant leaves and the roster shrinks."""\n'
        "    resp = client.post('/runs/1/leave', json={'name': 'ada'})\n"
        "    assert resp.status_code == 200\n"
        "```\n"
    ),
}


#: Three shapes the failure analyzer actually emits (test_impl_handlers): a bare object, an
#: object behind a think block, an object inside a fence after a preamble. The analyzer
#: fault must bite on all three and leave what surrounds the object alone.
_ANALYSIS_OBJECT = (
    "{\n"
    '  "classification": "work_product",\n'
    '  "analysis_summary": "The leave handler returns 200 for an unknown run.",\n'
    '  "contributing_factors": ["no lookup before the mutation"],\n'
    '  "implicated_files": ["backend/routes.py"]\n'
    "}"
)
_ANALYSES = {
    "a bare object": _ANALYSIS_OBJECT,
    "behind a think block": "<think>the evidence names routes.py</think>\n" + _ANALYSIS_OBJECT,
    "fenced after a preamble": "Here is the analysis.\n\n```json\n" + _ANALYSIS_OBJECT + "\n```\n",
}


def _representative_cases():
    """Every fault against every representative emission OF ITS OWN TASK: a suite for the
    qa and develop faults, a builder emission for the builder's (the suites carry fences
    too), an analysis for the analyzer's — a fence-stripping transform proves nothing on
    JSON and a JSON transform nothing on a suite."""
    from squadops.tasks.task_types import TaskType

    cases = []
    for name in sorted(FAULTS):
        shapes = _ANALYSES if FAULTS[name].task == TaskType.DATA_ANALYZE_FAILURE else _EMISSIONS
        cases += [
            pytest.param(name, shape, shapes[shape], id=f"{name}-{shape}")
            for shape in sorted(shapes)
        ]
    return cases


@pytest.mark.parametrize(("name", "shape", "content"), _representative_cases())
def test_every_declared_fault_actually_changes_a_representative_emission(name, shape, content):
    """A fault that returns its input is inert, and `inject` used to log it as APPLIED
    anyway — so the cycle ran on as an ordinary green one while the record said a fault had
    been injected (#1300).

    The suite already tested each transform against an emission chosen to suit it, which is
    exactly why an emission that did NOT suit it was never a failure: roll-4's import swap
    had nothing to swap on a suite that imports no `userEvent`, and its fallback existed
    only as a comment. This is the derived form — every fault, every representative shape.
    """
    assert FAULTS[name].transform(content) != content, (
        f"{name} returned its input unchanged on an emission {shape} — a fault that cannot "
        "bite makes its diagnostic prove nothing"
    )


class TestAnInertFaultIsNamedAsInertRatherThanApplied:
    def test_the_import_swap_falls_back_when_there_is_no_import_to_swap(self):
        """Roll 4's shape reproduced without inventing an import: a call to a non-function
        property of `expect`, which every vitest suite binds."""
        out = _inject(
            _EMISSIONS["without it"],
            "task-run_x-m006-qa.test",
            ["qa_suite_own_frame_failure"],
        )
        assert "expect.__squadops_injected_fault__();" in out
        assert "test('renders the runs list'" in out, "the case itself is untouched"
        assert out.index("__squadops_injected_fault__") < out.index("render(<RunsListView")

    def test_the_swap_is_still_preferred_when_the_import_is_there(self):
        """The faithful transform first — the fallback is for the case it cannot reach."""
        out = _inject(_SUITE, "task-run_x-m006-qa.test", ["qa_suite_own_frame_failure"])
        assert "@testing-library/react" in out
        assert "__squadops_injected_fault__" not in out

    def test_the_injected_call_is_read_as_an_own_frame_defect_so_it_routes_to_qa(self):
        """The whole point of the shape. If the injected failure were attributed to the
        application, the diagnostic would exercise the dev chain and L7 would go unread."""
        from squadops.capabilities.handlers.test_runner import suite_defects

        rows = [
            {
                "file": "frontend/src/__tests__/runs.test.jsx",
                "title": "renders the runs list",
                "exception": "TypeError",
                "messages": ["TypeError: expect.__squadops_injected_fault__ is not a function"],
                "frames": [{"file": "frontend/src/__tests__/runs.test.jsx", "line": 6}],
            }
        ]
        assert len(suite_defects(rows, [], "vitest")) == 1

    def test_an_emission_with_no_case_to_break_is_reported_as_not_biting(self, caplog):
        """Still possible — a prose-only or fence-only emission has no test body. It must
        say so instead of claiming an exercise."""
        content = "```py:backend/tests/test_runs.py\ndef test_x(): pass\n```\n"
        with caplog.at_level("WARNING"):
            out = _inject(content, "task-run_x-m006-qa.test", ["qa_suite_own_frame_failure"])
        assert out == content
        record = next(r for r in caplog.records if "DID NOT BITE" in r.getMessage())
        assert "PROVES NOTHING" in record.getMessage()
        assert "APPLIED" not in record.getMessage()

    def test_a_fault_that_bites_still_says_applied(self, caplog):
        with caplog.at_level("WARNING"):
            _inject(_SUITE, "task-run_x-m006-qa.test", ["qa_suite_absent"])
        messages = [r.getMessage() for r in caplog.records]
        assert any("fault_injection: APPLIED" in m for m in messages)
        assert not any("DID NOT BITE" in m for m in messages)


class TestTheOwnFrameFaultReadsTheEmissionsLanguage:
    """#1304: the fault targets a capability, and a capability is not a runner.

    A cycle's plan may schedule a backend pytest suite on the qa task that runs first, and
    a vitest shape cannot bite a Python file. Two consecutive live diagnostics went that
    way — `cyc_06747fde42f2` bit only because a frontend task also happened to exist, and
    `cyc_ef8b997de07a` had a single pytest qa task and exercised nothing. Whether a
    prediction is exercised must not depend on what the planner scheduled.
    """

    def test_a_python_suite_takes_an_argument_binding_error_in_its_own_first_case(self):
        """#1352: a keyword the callee does not take — not a name the module never binds,
        which the emission seam's ``undefined_names`` check refuses before the suite runs
        (``TestThePythonFaultSurvivesTheEmissionSeamAndDiesAtItsOwnFrame`` executes it)."""
        out = _inject(
            _EMISSIONS["a pytest suite"], "task-run_x-m005-qa.test", ["qa_suite_own_frame_failure"]
        )
        assert "textwrap.dedent(__squadops_injected_fault__=True)" in out
        assert "def test_leave_run_happy_path(client):" in out, "the signature is untouched"
        # inside the body, not at module level — a module-level error is a collection
        # error, which is a different shape and routes differently
        body = out.split("def test_leave_run_happy_path(client):", 1)[1]
        injected = body.index("textwrap.dedent(")
        assert body[:injected].rsplit("\n", 1)[-1] == "    "

    def test_a_javascript_suite_still_takes_the_javascript_shape(self):
        out = _inject(
            _EMISSIONS["without it"], "task-run_x-m006-qa.test", ["qa_suite_own_frame_failure"]
        )
        assert "expect.__squadops_injected_fault__();" in out
        assert "# #1251 injected fault" not in out, "no Python comment in a JSX file"

    def test_the_faithful_import_swap_is_still_preferred(self):
        out = _inject(_SUITE, "task-run_x-m006-qa.test", ["qa_suite_own_frame_failure"])
        assert "@testing-library/react" in out
        assert "__squadops_injected_fault__" not in out


class TestAReDispatchIsNotAFirstAttempt:
    """#1304: `prior_attempts` is the general marker.

    A re-dispatch from the correction loop carried neither `emission_retry_feedback` nor a
    repair attempt index, so the fault re-applied to every repaired emission and the loop
    could never be seen recovering — which is the whole thing a diagnostic watches.
    Observed on `cyc_06747fde42f2`: the same task id took the fault twice with a full
    correction round in between.
    """

    def test_a_correction_re_dispatch_runs_clean(self):
        out = _inject(
            _SUITE,
            "task-run_x-m006-qa.test",
            ["qa_suite_own_frame_failure"],
            inputs={"prior_attempts": 1},
        )
        assert out == _SUITE

    def test_the_first_attempt_still_takes_it(self):
        out = _inject(_SUITE, "task-run_x-m006-qa.test", ["qa_suite_own_frame_failure"], inputs={})
        assert out != _SUITE

    def test_a_zero_count_is_a_first_attempt_not_a_re_dispatch(self):
        """The stamp counts handled outcomes, so 0 and absent mean the same thing. Reading
        0 as truthy-adjacent would disable the fault everywhere."""
        out = _inject(
            _SUITE,
            "task-run_x-m006-qa.test",
            ["qa_suite_own_frame_failure"],
            inputs={"prior_attempts": 0},
        )
        assert out != _SUITE

    def test_the_emission_retry_marker_still_works_on_its_own(self):
        """Kept as an independent marker — #566's retry sets it and nothing else."""
        out = _inject(
            _SUITE,
            "task-run_x-m006-qa.test",
            ["qa_suite_own_frame_failure"],
            inputs={"emission_retry_feedback": {"reason": "no_fenced_blocks"}},
        )
        assert out == _SUITE


class TestTheScopeOfOnce:
    """#1310: which recovery a fault exists to watch differs per fault. Under one global
    first-attempt rule the absent-suite fault bit on attempt 1, the emission retry emitted
    a good suite, the task succeeded, and correction — the seam L2 names — was never
    entered (`cyc_e38566bb7b5d`, "correction rounds: 0"). The diagnostic fired and proved
    nothing about what it names."""

    _RETRY = {"emission_retry_feedback": {"signature": "unextractable"}, "prior_attempts": 1}
    _CORRECTION_REDISPATCH = {"prior_attempts": 1}

    def test_the_absent_suite_fault_also_takes_the_emission_retry(self):
        """Bug caught: the retry recovering before correction — the fault must ride every
        emission attempt so the task exhausts its retries and fails into the loop."""
        out = _inject(_SUITE, "task-run_x-m006-qa.test", ["qa_suite_absent"], inputs=self._RETRY)
        assert "```" not in out

    def test_a_correction_re_dispatch_of_the_target_runs_clean_under_either_scope(self):
        """The re-take after correction IS the recovery, whatever the scope — a fault that
        re-broke it would manufacture a red the loop could never be seen recovering from
        (#1304's shape, one level up)."""
        for name in ("qa_suite_absent", "qa_suite_at_path_prefix"):
            out = _inject(
                _SUITE, "task-run_x-m006-qa.test", [name], inputs=self._CORRECTION_REDISPATCH
            )
            assert out == _SUITE, name

    def test_first_attempt_faults_still_run_clean_on_the_emission_retry(self):
        """The two faults whose recovery is a repair or a re-take keep today's rule."""
        for name in ("qa_suite_at_path_prefix", "qa_suite_own_frame_failure"):
            out = _inject(_SUITE, "task-run_x-m006-qa.test", [name], inputs=self._RETRY)
            assert out == _SUITE, name

    def test_the_repair_task_is_never_in_scope_for_a_qa_test_fault(self):
        """Never the repair: the capability suffix differs, so the absent-suite fault cannot
        strip the very repair that supplies the suite."""
        out = _inject(
            _SUITE, "repair-run_x-00-qa.test_repair", ["qa_suite_absent"], inputs=self._RETRY
        )
        assert out == _SUITE

    def test_every_fault_declares_its_scope_and_only_the_absent_suite_widens_it(self):
        """Scope is a declaration read from the fault, so a record can say which attempts
        a diagnostic faulted; widening is deliberate and named."""
        widened = {n for n, f in FAULTS.items() if f.scope is FaultScope.ALL_EMISSION_ATTEMPTS}
        assert widened == {"qa_suite_absent"}

    def test_the_application_log_names_the_scope(self, caplog):
        with caplog.at_level("WARNING"):
            _inject(_SUITE, "task-run_x-m006-qa.test", ["qa_suite_absent"], inputs=self._RETRY)
        record = next(r for r in caplog.records if "fault_injection: APPLIED" in r.message)
        assert "scope=all_emission_attempts" in record.getMessage()


class TestTheAnalyzerFaultClaimsAFileNoTreeHas:
    """1.7.4 plan §3.1 (#968, A1): the claim is refutable by the cheapest source check
    there is, and the object around it stays the analyzer's own."""

    def _faulted(self, content):
        return _inject(
            content, "corr-run_x-00-data.analyze_failure", ["analyzer_false_source_claim"]
        )

    def test_the_claim_leads_the_prose_and_the_file_leads_the_structured_half(self):
        import json

        from squadops.capabilities.handlers.fault_injection import INJECTED_CLAIM_FILE
        from squadops.capabilities.handlers.impl.analyze_failure import FailureAnalysis

        out = json.loads(self._faulted(_ANALYSIS_OBJECT))
        assert out["classification"] == "work_product", "the object must still validate"
        assert out["analysis_summary"].startswith(f"The defect is in `{INJECTED_CLAIM_FILE}`")
        assert out["analysis_summary"].endswith("returns 200 for an unknown run.")
        assert out["implicated_files"] == [INJECTED_CLAIM_FILE, "backend/routes.py"]
        assert out["contributing_factors"][-1] == "no lookup before the mutation"
        FailureAnalysis.model_validate(out)

    def test_what_surrounds_the_object_is_kept_so_the_extractor_sees_its_own_shape(self):
        out = self._faulted(_ANALYSES["fenced after a preamble"])
        assert out.startswith("Here is the analysis.\n\n```json\n")
        assert out.endswith("\n```\n")
        assert "__squadops_injected_fault__" in out
        out = self._faulted(_ANALYSES["behind a think block"])
        assert out.startswith("<think>the evidence names routes.py</think>\n")

    def test_no_object_is_left_unchanged_and_named_inert(self, caplog):
        """A transform that invented an object would hand the handler an emission no
        analyzer produced; unchanged is reported as DID NOT BITE (#1300)."""
        with caplog.at_level("WARNING"):
            assert self._faulted("no analysis here") == "no analysis here"
        assert "DID NOT BITE" in caplog.text

    def test_only_round_zero_takes_it(self):
        """The correction task id carries the round; round 1's analysis must run clean so
        the diagnostic watches the decision made on the claim, not a loop that never
        stops being lied to."""
        assert self._faulted(_ANALYSIS_OBJECT) != _ANALYSIS_OBJECT
        assert (
            _inject(
                _ANALYSIS_OBJECT,
                "corr-run_x-01-data.analyze_failure",
                ["analyzer_false_source_claim"],
            )
            == _ANALYSIS_OBJECT
        )


class TestTheContentlessBuilderShape:
    _BUILDER = (
        "I'll assemble the package now.\n\n"
        "```dockerfile:Dockerfile\nFROM python:3.12-slim\n```\n\n"
        "```text:requirements.txt\nfastapi\n```\n"
    )

    def test_it_keeps_the_builders_own_preamble_and_nothing_else(self):
        """#1364's shape: 160 tokens, no fence — the builder's own sentence of intent."""
        out = _inject(
            self._BUILDER, "task-run_x-m005-builder.assemble", ["builder_emission_contentless"]
        )
        assert out == "I'll assemble the package now."

    def test_a_qa_task_is_not_its_target(self):
        assert (
            _inject(self._BUILDER, "task-run_x-m006-qa.test", ["builder_emission_contentless"])
            == self._BUILDER
        )


class TestTheNewSeamsReachTheHandlersTheLiveCycleCalls:
    """Wiring, not transform (#1251): entered at ``handle()``, the call the executor makes,
    with the paired control — the same emission and no declaration."""

    def _context(self, task_id, emission):
        from unittest.mock import AsyncMock, MagicMock

        from squadops.llm.models import ChatMessage

        ctx = MagicMock()
        ctx.task_id = task_id
        chat = AsyncMock(return_value=ChatMessage(role="assistant", content=emission))
        ctx.ports.llm.chat = chat
        ctx.ports.llm.chat_stream_with_usage = chat
        ctx.ports.llm.default_model = "test-model"
        assembled = MagicMock()
        assembled.content = "system prompt"
        assembled.assembly_hash = "sha256:test"
        ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
        ctx.ports.prompt_service.assemble = MagicMock(return_value=assembled)
        ctx.ports.prompt_service.assemble_task_only = MagicMock(return_value=assembled)
        ctx.ports.request_renderer = None
        ctx.ports.llm_observability = None
        ctx.correlation_context = None
        return ctx

    async def _builder(self, declaration):
        from squadops.capabilities.handlers.cycle_tasks import BuilderAssembleHandler

        emission = (
            "Assembling.\n\n"
            "```python:my_app/__main__.py\nfrom .main import main\nmain()\n```\n\n"
            '```dockerfile:Dockerfile\nFROM python:3.12-slim\nCMD ["python", "-m", "my_app"]\n```\n\n'
            "```text:requirements.txt\n# none\n```\n\n"
            "```markdown:qa_handoff.md\n## How to Run\npython -m my_app\n\n"
            "## How to Test\npytest tests/\n\n## Expected Behavior\nPrints hello\n```\n"
        )
        inputs = {
            "prd": "Build something.",
            "artifact_contents": {"my_app/main.py": "def main():\n    print('hello')"},
            "resolved_config": {"build_profile": "python_cli_builder", **declaration},
        }
        return await BuilderAssembleHandler().handle(
            self._context("task-run_x-m005-builder.assemble", emission), inputs
        )

    async def test_without_a_declaration_the_builder_banks_its_files(self):
        result = await self._builder({})
        assert result.success is True
        assert "Dockerfile" in [a["name"] for a in result.outputs["artifacts"]]

    async def test_with_the_declaration_the_same_emission_reaches_the_builder_contentless(self):
        """#1364 on demand: the attempt fails at the emission seam as a semantic failure —
        today with NO ``emission_failure`` marker, which is why the executor never aims a
        retry for the builder and the attempt goes straight to correction. That absence is
        the #1372 gap this fault exists to exercise; the develop handler's same path banks
        the marker (test_build_handlers), and pack row 3 gives the builder one."""
        result = await self._builder({DECLARATION_KEY: ["builder_emission_contentless"]})
        assert result.success is False
        assert result.error == "No valid fenced code blocks found"
        assert result.outputs.get("outcome_class") == "semantic_failure"
        assert "emission_failure" not in result.outputs, "#1372 has landed — update this test"

    async def _analyzer(self, declaration, task_id="corr-run_x-00-data.analyze_failure"):
        from squadops.capabilities.handlers.impl.analyze_failure import DataAnalyzeFailureHandler

        inputs = {
            "prd": "test",
            "failure_evidence": {"error": "leave returned 200 for an unknown run"},
            "resolved_config": dict(declaration),
        }
        return await DataAnalyzeFailureHandler().handle(
            self._context(task_id, _ANALYSIS_OBJECT), inputs
        )

    async def test_without_a_declaration_the_analysis_is_the_models_own(self):
        result = await self._analyzer({})
        assert result.success is True
        assert result.outputs["implicated_files"] == ["backend/routes.py"]
        assert "__squadops_injected_fault__" not in result.outputs["analysis_summary"]

    async def test_with_the_declaration_the_banked_analysis_carries_the_refuted_claim(self):
        from squadops.capabilities.handlers.fault_injection import INJECTED_CLAIM_FILE

        result = await self._analyzer({DECLARATION_KEY: ["analyzer_false_source_claim"]})
        assert result.success is True, "the object still validates — the claim is in the prose"
        assert result.outputs["implicated_files"][0] == INJECTED_CLAIM_FILE
        assert result.outputs["analysis_summary"].startswith("The defect is in")

    async def test_round_one_runs_clean(self):
        result = await self._analyzer(
            {DECLARATION_KEY: ["analyzer_false_source_claim"]},
            task_id="corr-run_x-01-data.analyze_failure",
        )
        assert result.outputs["implicated_files"] == ["backend/routes.py"]
