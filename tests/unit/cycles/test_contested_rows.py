"""SIP-0096 §17a change 2 — a row a producer disputes is marked ``contested``, and stays failed.

A dispute (change 1) names a check by the identity its prompt listed. These tests name what
each would catch: a dispute marking a row it did not name, or a passing or advisory row; a
contest lost between the task's outputs and the run's roll-up, or on the Postgres round-trip;
a contest that changes a verdict; and — end to end — the name the prompt shows disagreeing with
the key the matcher reads on a real row.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from adapters.cycles.dispatched_flow_executor import record_task_evidence
from adapters.cycles.postgres_cycle_registry import (
    _verification_summary_from_dict,
    _verification_summary_to_dict,
)
from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.agents.base import PortsBundle
from squadops.bootstrap.handlers import create_handler_registry
from squadops.capabilities.disputed_checks import mark_contested
from squadops.cycles.failure_evidence import build_failure_evidence
from squadops.cycles.run_ledger import RunLedger
from squadops.cycles.verification_integrity import Contest, RunVerdict, aggregate_verification
from squadops.llm.models import ChatMessage
from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.tasks.models import TaskEnvelope, TaskResult, TaskResultStatus
from squadops.tasks.task_types import TaskType

pytestmark = [pytest.mark.domain_orchestration]

_REASON = "the @/lib alias is declared in the tsconfig paths"


def _row(file: str, *, passed: bool = False, severity: str = "error", criterion=None) -> dict:
    return {
        "check": "acceptance:declared_imports",
        "severity": severity,
        "params": {"file": file},
        "status": "passed" if passed else "failed",
        # The seam derives `passed` from severity × status (RC-9): an advisory failure passes.
        "passed": passed or severity != "error",
        "reason": "ok" if passed else "unresolved import '@/lib/api'",
        "criterion_id": criterion,
    }


_LIST = _row("src/views/RunList.jsx", criterion="vc-list")
_DETAIL = _row("src/views/RunDetail.jsx", criterion="vc-detail")


def _dispute(**named) -> dict:
    return {"check": "declared_imports", "reason": _REASON, "by": "dev", **named}


_CONTEST = {"by": "dev", "reason": _REASON}


@pytest.mark.parametrize(
    ("rows", "disputes", "contested", "unmatched"),
    [
        # The file names one of two rows of the same check.
        ([_LIST, _DETAIL], [_dispute(file="src/views/RunList.jsx")], [0], 0),
        # The criterion names one, whatever the file.
        ([_LIST, _DETAIL], [_dispute(criterion_id="vc-detail")], [1], 0),
        # Neither: every failing row of the check — and the bare name matches the prefixed row.
        ([_LIST, _DETAIL], [_dispute()], [0, 1], 0),
        # A passing row, or a failure that is only advice, has nothing to contest.
        ([_row("a.jsx", passed=True), _row("b.jsx", severity="warning")], [_dispute()], [], 1),
        # A dispute of a check no row carries.
        ([_LIST], [{**_dispute(), "check": "frontend_build"}], [], 1),
    ],
    ids=["by file", "by criterion", "every row of the check", "nothing failing", "no such check"],
)
def test_a_dispute_marks_exactly_the_failing_rows_it_names(rows, disputes, contested, unmatched):
    """Bug caught: a dispute of one file's row contesting every file's; a bare check name that
    never matches the ``acceptance:`` row; a passing or advisory row marked; an unmatched
    dispute dropped instead of recorded."""
    marked, left = mark_contested(rows, disputes)

    assert [i for i, r in enumerate(marked) if r.get("contested")] == contested
    assert all(marked[i]["contested"] == _CONTEST for i in contested)
    assert len(left) == unmatched
    assert all("contested" not in r for r in rows), "the rows handed in are not changed"


def test_a_contest_is_not_evidence_of_the_failure_it_disputes():
    """``derived_failure_reason`` renders a reasonless row's other keys, and the correction
    signature reads it from the raw rows the evidence now marks. Bug caught: the same failure
    signing differently once contested — by a renderer that shows the contest, or a marking that
    touches the row's own fields — so the loop reads a shift where nothing moved."""
    from squadops.cycles.correction_signature import failure_signature
    from squadops.cycles.verification_normalize import derived_failure_reason

    row = {"check": "frontend_build", "passed": False, "missing": ["vite.config.js"]}
    (contested,), _ = mark_contested([row], [{"check": "frontend_build", "reason": _REASON}])

    assert derived_failure_reason(contested) == derived_failure_reason(row)
    evidence = {"validation_result": {"checks": [row]}}
    marked = {"validation_result": {"checks": [contested]}}
    assert failure_signature(marked) == failure_signature(evidence)


def test_where_two_disputes_name_one_row_the_first_stands():
    marked, _ = mark_contested([_LIST], [_dispute(), {**_dispute(), "reason": "a second"}])
    assert marked[0]["contested"] == _CONTEST


def _outputs(*rows, disputes=(), test_result=None) -> dict:
    outputs = {"validation_result": {"checks": list(rows)}, "disputed_checks": list(disputes)}
    if test_result is not None:
        outputs["test_result"] = test_result
    return outputs


@pytest.mark.parametrize("disputed", [True, False], ids=["disputed", "not disputed"])
def test_the_contest_reaches_the_roll_up_and_the_verdict_does_not_move(disputed):
    """Entered at ``record_task_evidence``, the executor's one recording seam. Bug caught: the
    contest lost between the outputs and the roll-up, lost on the stored round-trip — or a
    contested failure counted as anything but a failure (§17a: never a fourth family)."""
    ledger = RunLedger()
    outputs = _outputs(_LIST, disputes=[_dispute()] if disputed else [])
    record_task_evidence(ledger, TaskResult(task_id="t", status="FAILED", outputs=outputs), "t")

    summary = aggregate_verification(ledger.check_results)

    assert summary.verdict is RunVerdict.REJECTED
    (failed,) = summary.failed_detail
    assert failed.contested == (Contest(by="dev", reason=_REASON) if disputed else None)
    assert _verification_summary_from_dict(_verification_summary_to_dict(summary)) == summary


def test_a_disputed_tests_pass_is_carried_onto_the_result_synthesized_for_it():
    """``tests_pass`` is synthesized from ``test_result`` and its row is skipped. Bug caught:
    the dispute of the one check every behavioural failure rides on (#1581's shape) dropped
    with the row."""
    ledger = RunLedger()
    tests_row = {"check": "tests_pass", "passed": False, "reason": "2 failed"}
    test_result = {"executed": True, "exit_code": 1, "summary": "2 failed"}
    dispute = {"check": "tests_pass", "reason": "the suite asserts a field the PRD drops"}
    outputs = _outputs(tests_row, disputes=[{**dispute, "by": "dev"}], test_result=test_result)

    record_task_evidence(ledger, TaskResult(task_id="t", status="FAILED", outputs=outputs), "t")

    (result,) = [r for r in ledger.check_results if r.check_id == "tests_pass"]
    assert result.contested == Contest(by="dev", reason=dispute["reason"])


def test_the_failure_evidence_carries_contested_rows_and_unmatched_disputes_in_their_own_blocks():
    """What the analyzer reads (change 3 asks it one question per contested row). Bug caught:
    the contest marked on the row but no block to ask about, or an unmatched dispute lost."""
    envelope = MagicMock(task_id="t", task_type=TaskType.DEVELOPMENT_DEVELOP)
    stray = {**_dispute(), "check": "frontend_build"}
    outputs = _outputs(_LIST, _DETAIL, disputes=[_dispute(file="src/views/RunList.jsx"), stray])

    evidence = build_failure_evidence(
        envelope,
        TaskResult(task_id="t", status="FAILED", outputs=outputs),
        prior_plan_deltas_count=0,
    )

    assert evidence["contested_rows"] == [{**_LIST, "contested": _CONTEST}]
    assert evidence["unmatched_disputes"] == [stray]
    assert evidence["validation_result"]["checks"][1] == _DETAIL


async def test_a_dispute_by_the_identity_its_prompt_listed_contests_the_real_row():
    """End to end, entered where the agent enters (``HandlerExecutor.execute``) and read where
    the correction protocol reads (``build_failure_evidence``): a develop task judged by a typed
    criterion it fails disputes it by the line its own prompt listed. Bug caught: the name, file
    or criterion the prompt shows disagreeing with what the typed-acceptance seam writes on the
    row — every dispute would be unmatched, and nothing would ever be contested."""
    prompts = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
    criterion = {
        "check": "import_present",
        "params": {"file": "backend/routes.py", "module": "fastapi"},
        "id": "vc-routes-imports-fastapi",
    }
    listed_lines: list[str] = []

    async def _chat(messages, **kwargs):
        listed = messages[-1].content.split("Checks you may dispute:")[1].split("\n\n")[1]
        listed_lines.append(listed)
        # The listed line, as the model is asked to copy it: `- check: `x`, file: `y`, ...`
        fields = dict(part.split(": ", 1) for part in listed.removeprefix("- ").split(", "))
        block = "\n".join(f"  {k}: {v.strip('`')}" for k, v in fields.items())
        emission = (
            "```python:backend/routes.py\nx = 1\n```\n\n```disputed_checks\n"
            f"-{block[1:]}\n  reason: {_REASON}\n```\n"
        )
        return ChatMessage(role="assistant", content=emission, completion_tokens=40)

    llm = MagicMock()
    llm.default_model = "qwen3.8:27b"
    llm.chat_stream_with_usage = _chat
    prompt_service = MagicMock()
    prompt_service.assemble.return_value = MagicMock(content="system", assembly_hash="h")
    ports = PortsBundle(
        llm=llm,
        memory=MagicMock(),
        prompt_service=prompt_service,
        queue=MagicMock(),
        metrics=MagicMock(),
        events=MagicMock(),
        filesystem=MagicMock(),
        request_renderer=RequestTemplateRenderer(
            FilesystemPromptAssetAdapter(prompts / "fragments", prompts / "request_templates")
        ),
    )
    envelope = TaskEnvelope(
        task_id="task-dev",
        agent_id="dev-agent",
        cycle_id="cyc",
        pulse_id="p",
        project_id="group_run",
        task_type=TaskType.DEVELOPMENT_DEVELOP,
        inputs={
            "prd": "Runs API",
            "artifact_contents": {"implementation_plan.md": "1. routes"},
            "subtask_focus": "the runs routes",
            "expected_artifacts": ["backend/routes.py"],
            "acceptance_criteria": [criterion],
            "resolved_config": {"output_validation": True, "max_self_eval_passes": 0},
        },
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
        metadata={"role": "dev"},
    )
    executor = HandlerExecutor(
        "dev-agent", create_handler_registry(roles=["dev"]), ports, role="dev"
    )

    result = await executor.execute(envelope)
    evidence = build_failure_evidence(envelope, result, prior_plan_deltas_count=0)

    assert result.status == TaskResultStatus.FAILED
    assert listed_lines == [
        "- check: `acceptance:import_present`, file: `backend/routes.py`, "
        "criterion_id: `vc-routes-imports-fastapi`"
    ], "the prompt names the check as the row will carry it"
    (row,) = evidence["contested_rows"]
    assert (row["check"], row["params"]["file"], row["criterion_id"]) == (
        "acceptance:import_present",
        "backend/routes.py",
        "vc-routes-imports-fastapi",
    )
    assert row["contested"] == {"by": "dev", "reason": _REASON}
    assert "unmatched_disputes" not in evidence, json.dumps(evidence.get("unmatched_disputes"))
