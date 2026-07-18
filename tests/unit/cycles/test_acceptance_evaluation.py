"""Shared typed-acceptance evaluation seam (#419/#420).

``split_acceptance_criteria`` owns wire-shape coercion: ``TaskEnvelope.to_dict()``
flattens ``TypedCheck`` to plain dicts (``dataclasses.asdict``) and the agent
side never rehydrates, so any consumer filtering on ``isinstance(TypedCheck)``
loses its typed contract after dispatch — the #420 silent-skip defect. The
round-trip test here is the regression pin for that bug.
"""

from __future__ import annotations

import json

import pytest

from squadops.cycles.acceptance_evaluation import (
    evaluate_criterion,
    split_acceptance_criteria,
)
from squadops.cycles.implementation_plan import TypedCheck
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_capabilities]


def _envelope(criteria: list) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="t1",
        agent_id="a1",
        cycle_id="c1",
        pulse_id="p1",
        project_id="pr1",
        task_type="builder.assemble",
        correlation_id="x",
        causation_id="y",
        trace_id="z",
        span_id="s",
        inputs={"acceptance_criteria": criteria},
    )


class TestWireShapeCoercion:
    """The #420 regression: criteria must survive the A2A JSON round-trip."""

    def test_envelope_round_trip_recovers_typed_checks(self):
        criterion = TypedCheck(
            check="regex_match",
            params={"file": "frontend/package.json", "pattern": "vite"},
            severity="error",
            description="frontend manifest",
        )
        wire = json.loads(json.dumps(_envelope([criterion, "prose note"]).to_dict()))
        back = TaskEnvelope.from_dict(wire)

        # The wire shape is dicts — the exact input the handlers receive.
        raw = back.inputs["acceptance_criteria"]
        assert [type(c).__name__ for c in raw] == ["dict", "str"]

        split = split_acceptance_criteria(raw)
        assert len(split.typed) == 1
        recovered = split.typed[0]
        assert recovered.check == "regex_match"
        assert recovered.params == {"file": "frontend/package.json", "pattern": "vite"}
        assert recovered.severity == "error"
        assert split.prose == ("prose note",)
        assert split.unparseable == ()

    def test_round_trip_preserves_fingerprint(self):
        # RC-9b error counters key on fingerprint; a round-tripped criterion
        # must share the counter of its in-process original.
        criterion = TypedCheck(
            check="count_at_least", params={"glob": "tests/test_*.py", "min_count": 3}
        )
        wire = json.loads(json.dumps(_envelope([criterion]).to_dict()))
        split = split_acceptance_criteria(
            TaskEnvelope.from_dict(wire).inputs["acceptance_criteria"]
        )
        assert split.typed[0].fingerprint() == criterion.fingerprint()


class TestSplitPartitioning:
    def test_typed_instances_pass_through(self):
        criterion = TypedCheck(check="regex_match", params={"file": "a.py", "pattern": "x"})
        split = split_acceptance_criteria([criterion])
        assert split.typed == (criterion,)
        assert split.prose == ()
        assert split.unparseable == ()

    def test_dict_missing_check_key_is_unparseable(self):
        row = {"severity": "error", "file": "a.py"}
        split = split_acceptance_criteria([row])
        assert split.typed == ()
        assert split.unparseable == (row,)

    def test_unknown_check_name_is_unparseable(self):
        row = {"check": "no_such_check", "file": "a.py"}
        split = split_acceptance_criteria([row])
        assert split.typed == ()
        assert split.unparseable == (row,)

    def test_non_string_non_mapping_is_unparseable(self):
        split = split_acceptance_criteria([42])
        assert split.unparseable == (42,)

    @pytest.mark.parametrize("criteria", [None, [], ()])
    def test_empty_inputs_yield_empty_split(self, criteria):
        split = split_acceptance_criteria(criteria)
        assert split == split_acceptance_criteria([])
        assert split.typed == () and split.prose == () and split.unparseable == ()


class TestEvaluateCriterionGates:
    async def test_typed_acceptance_disabled_skips(self, tmp_path):
        criterion = TypedCheck(check="regex_match", params={"file": "a.py", "pattern": "x"})
        outcome = await evaluate_criterion(
            criterion,
            tmp_path,
            stack=None,
            typed_acceptance_enabled=False,
            command_acceptance_enabled=True,
        )
        assert outcome.status == "skipped"
        assert outcome.reason == "typed_acceptance_disabled"

    async def test_command_gate_skips_only_command_check(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        command = TypedCheck(check="command_exit_zero", params={"argv": ["true"]})
        regex = TypedCheck(check="regex_match", params={"file": "a.py", "pattern": "x"})

        cmd_outcome = await evaluate_criterion(
            command,
            tmp_path,
            stack=None,
            typed_acceptance_enabled=True,
            command_acceptance_enabled=False,
        )
        regex_outcome = await evaluate_criterion(
            regex,
            tmp_path,
            stack=None,
            typed_acceptance_enabled=True,
            command_acceptance_enabled=False,
        )
        assert cmd_outcome.status == "skipped"
        assert cmd_outcome.reason == "command_acceptance_checks_disabled"
        assert regex_outcome.status == "passed"

    async def test_unregistered_check_is_evaluator_error(self, tmp_path):
        # Constructed directly, bypassing the parser's vocabulary gate —
        # models a registry/spec drift, which must not crash the cycle.
        bogus = TypedCheck(check="not_registered", params={})
        outcome = await evaluate_criterion(
            bogus,
            tmp_path,
            stack=None,
            typed_acceptance_enabled=True,
            command_acceptance_enabled=True,
        )
        assert outcome.status == "error"
        assert outcome.reason == "no_evaluator_registered"

    async def test_missing_file_fails_with_file_not_found(self, tmp_path):
        # The #419 field shape: criterion addresses frontend/package.json,
        # the workspace has only a bare-path package.json.
        (tmp_path / "package.json").write_text('{"scripts": {"build": "vite build"}}')
        criterion = TypedCheck(
            check="regex_match", params={"file": "frontend/package.json", "pattern": "vite"}
        )
        outcome = await evaluate_criterion(
            criterion,
            tmp_path,
            stack=None,
            typed_acceptance_enabled=True,
            command_acceptance_enabled=True,
        )
        assert outcome.status == "failed"
        assert outcome.reason == "file_not_found"


def test_split_keeps_non_safelisted_command_rows_typed():
    """The #422 authoring lint must NOT leak into wire coercion: a dispatched
    plan may legally carry an out-of-safelist command (pre-lint plan, static
    fallback). Demoting it to unparseable here would fail OPEN — the row must
    stay typed so evaluation fails CLOSED with command_not_in_safelist."""
    wire_row = {
        "check": "command_exit_zero",
        "severity": "error",
        "description": "runs tests",
        "params": {"argv": ["npm", "test"]},
    }
    result = split_acceptance_criteria([wire_row])
    assert len(result.typed) == 1
    assert result.typed[0].params["argv"] == ["npm", "test"]
    assert not result.unparseable


# --------------------------------------------------------------------------- #
# resolve_check_stack (#503) — bug caught: live cycles fed stack=None into every
# AST evaluator (resolved_config never carries a "stack" key), so endpoint/field
# checks silently skipped in production while CI passed them with an explicit stack.
# --------------------------------------------------------------------------- #


def test_resolve_check_stack_maps_fullstack_profile_to_fastapi():
    from squadops.cycles.acceptance_evaluation import resolve_check_stack

    # the live shakedown-3 config shape: build_profile present, no stack key
    assert resolve_check_stack({"build_profile": "fullstack_fastapi_react"}) == "fastapi"


def test_resolve_check_stack_explicit_key_wins_over_profile():
    from squadops.cycles.acceptance_evaluation import resolve_check_stack

    assert (
        resolve_check_stack({"stack": "django", "build_profile": "fullstack_fastapi_react"})
        == "django"
    )


def test_resolve_check_stack_unmapped_profile_and_empty_config_stay_none():
    from squadops.cycles.acceptance_evaluation import resolve_check_stack

    # unmapped profiles keep today's skip behavior — never a guessed stack
    assert resolve_check_stack({"build_profile": "python_cli_builder"}) is None
    assert resolve_check_stack({}) is None
