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
        out = _inject(
            _SUITE,
            "task-run_x-m006-qa.test",
            ["qa_suite_absent"],
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
        out = _inject(_SUITE, "task-run_x-m006-qa.test", ["qa_suite_vitest_own_frame_type_error"])
        assert "import userEvent from '@testing-library/react'" in out
        assert "@testing-library/user-event" not in out

    def test_an_emission_with_no_such_import_is_left_unchanged_rather_than_mangled(self):
        """Reported as applied-but-unchanged rather than silently mangling an emission it
        cannot break: the diagnostic's record then shows the fault did not bite."""
        content = "```py:backend/tests/test_runs.py\ndef test_x(): pass\n```\n"
        out = _inject(content, "task-run_x-m006-qa.test", ["qa_suite_vitest_own_frame_type_error"])
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

    capabilities: set[str] = set()
    for path in wired:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("_capability_id = "):
                capabilities.add(stripped.split("=", 1)[1].strip().strip("\"'"))
    # cycle/base.py is the shared seam for every _CycleTaskHandler subclass, so a
    # capability declared in a module that inherits it is wired too.
    from squadops.capabilities.handlers.impl import repair_handlers

    capabilities |= {
        getattr(obj, "_capability_id")
        for obj in vars(repair_handlers).values()
        if isinstance(obj, type) and getattr(obj, "_capability_id", None)
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
            {DECLARATION_KEY: "qa_suite_vitest_own_frame_type_error,repair_prose_only"}
        ) == ("qa_suite_vitest_own_frame_type_error", "repair_prose_only")

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
