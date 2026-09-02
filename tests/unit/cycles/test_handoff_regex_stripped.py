"""#1252: a plan-authored regex over the handoff's headings is dropped at dispatch.

The 1.7.1 React shakeout `cyc_8118588858a6` spent two of three correction rounds on the
WORD ORDER of two headings; the handoff's sections are the build profile's fact, checked
by name in any order, and the planner's regex was brittle duplication of that check.
Replayed from both shakeouts' stored plans.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadops.cycles.implementation_plan import ImplementationPlan, TypedCheck
from squadops.cycles.task_plan import _applicable_acceptance

pytestmark = [pytest.mark.domain_cycles]

_REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"


def _builder_task(plan_name: str):
    plan = ImplementationPlan.from_yaml((_REPLAYS / plan_name).read_text(encoding="utf-8"))
    return next(t for t in plan.tasks if t.task_type == "builder.assemble")


@pytest.mark.parametrize(
    ("plan_name", "handoff_rows"),
    [
        ("1-7-1-react-shakeout-2-implementation_plan.yaml", 6),
        ("1-7-1-react-shakeout-1-implementation_plan.yaml", 5),
    ],
)
def test_the_stored_plans_handoff_regexes_are_dropped_and_nothing_else_is(
    plan_name, handoff_rows, caplog
):
    task = _builder_task(plan_name)
    authored = [c for c in task.acceptance_criteria if isinstance(c, TypedCheck)]
    handoff = [
        c for c in authored if c.check == "regex_match" and c.params.get("file") == "qa_handoff.md"
    ]
    assert len(handoff) == handoff_rows, "the fixture is not the plan the issue was filed from"

    with caplog.at_level(logging.WARNING, logger="squadops.cycles.task_plan"):
        kept = _applicable_acceptance(task)

    assert [
        c
        for c in kept
        if isinstance(c, TypedCheck)
        and c.check == "regex_match"
        and c.params.get("file") == "qa_handoff.md"
    ] == []
    assert len(kept) == len(task.acceptance_criteria) - handoff_rows
    stripped = [r.message for r in caplog.records if "handoff_regex_stripped" in r.message]
    assert len(stripped) == handoff_rows
    # The row that cost the shakeout is named by its pattern.
    if handoff_rows == 6:
        assert any("(Backend|Server|API).*(Run|Start|Setup|Launch)" in m for m in stripped)


def test_a_regex_over_another_document_is_kept():
    """Over-stripping guard: `regex-only-on-documents` still lets the planner check a
    README or a runbook; only the handoff's headings are the profile's."""
    from types import SimpleNamespace

    task = SimpleNamespace(
        task_index=4,
        acceptance_criteria=[
            TypedCheck(check="regex_match", params={"file": "README.md", "pattern": "## Usage"}),
            TypedCheck(
                check="regex_match", params={"file": "docs/qa_handoff.md", "pattern": "## Run"}
            ),
        ],
    )
    kept = _applicable_acceptance(task)
    assert [c.params["file"] for c in kept] == ["README.md"]


class TestTheValidatorTeaches:
    """The gate half (#1252): a plan that authors a regex over the handoff is rejected
    at framing with the rule named, so the author learns it there; the dispatch strip
    above is the backstop for a plan that reaches dispatch unvalidated."""

    @pytest.mark.parametrize(
        ("plan_name", "rows"),
        [
            ("1-7-1-react-shakeout-2-implementation_plan.yaml", 6),
            ("1-7-1-react-shakeout-1-implementation_plan.yaml", 5),
        ],
    )
    def test_both_stored_plans_would_have_been_rejected_with_the_rule_named(self, plan_name, rows):
        plan = ImplementationPlan.from_yaml((_REPLAYS / plan_name).read_text(encoding="utf-8"))
        errors = plan.validate_handoff_criteria()
        assert len(errors) == rows
        assert all("no-regex-on-the-handoff" in e for e in errors)
        assert all("task 4 (builder.assemble)" in e for e in errors)

    def test_a_regex_over_another_document_passes(self):
        import yaml

        plan = ImplementationPlan.from_yaml(
            yaml.safe_dump(
                {
                    "version": 1,
                    "project_id": "p",
                    "cycle_id": "cy",
                    "prd_hash": "h",
                    "tasks": [
                        {
                            "task_index": 0,
                            "task_type": "builder.assemble",
                            "role": "builder",
                            "focus": "package",
                            "description": "package it",
                            "expected_artifacts": ["Dockerfile", "README.md"],
                            "acceptance_criteria": [
                                {"check": "regex_match", "file": "README.md", "pattern": "## Usage"}
                            ],
                            "depends_on": [],
                        }
                    ],
                    "summary": {"total_tasks": 1},
                }
            )
        )
        assert plan.validate_handoff_criteria() == []
