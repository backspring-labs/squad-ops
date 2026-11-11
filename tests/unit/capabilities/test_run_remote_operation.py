"""``qa.run_remote_operation`` with a fixture provider (SIP-0117 R4.4, phase 2a).

No Studio, no worker, no transport: the provider is a fake behind the remote-execution port,
and the skillset is a fixture. What is real is everything the framework owns: the request the
handler builds, how it believes a result, the evidence rows it writes, and the verdict the
roll-up reads from them."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from squadops.bootstrap.handlers import HANDLER_CONFIGS, create_handler_registry
from squadops.capabilities.capability_contracts import VerificationMode
from squadops.capabilities.handlers.context import ExecutionContext
from squadops.capabilities.handlers.cycle import run_remote_operation
from squadops.capabilities.handlers.cycle.run_remote_operation import (
    QARunRemoteOperationHandler,
)
from squadops.capabilities.skillsets import Skillset, SkillsetCapability, ToolRequest
from squadops.cycles.verification_integrity import RunVerdict, aggregate_verification
from squadops.cycles.verification_normalize import has_blocking_failure, normalize_task_checks
from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.orchestration.handler_registry import HandlerRegistry
from squadops.ports.remote_execution import RemoteExecutionPort
from squadops.remote_execution.models import (
    ASSERTION_RECORDS_ARTIFACT_TYPE,
    OPERATION_EVIDENCE_ARTIFACT_TYPE,
    AssertionOutcome,
    AssertionRecord,
    EvidenceItem,
    OperationStatus,
    RemoteOperationRequest,
    RemoteOperationResult,
)
from squadops.tasks.models import TaskEnvelope
from squadops.tasks.task_types import (
    TaskType,
    corrects_only_executed_failures,
    fails_without_correction,
    runs_an_operation,
)

pytestmark = [pytest.mark.domain_capabilities]

CONTRACT = "game.scenario_verification"
TOOL = ToolRequest("play_scenario", "fixture-editor", "worker")


def _skillset(*tools: ToolRequest, digest: str = "digest-1") -> Skillset:
    return Skillset(
        id="fixture-qa",
        version=1,
        description="fixture",
        roles=("qa",),
        platform_id="fixture",
        platform_variants=("local",),
        prerequisites=("fixture-editor",),
        capabilities=(SkillsetCapability(CONTRACT, (VerificationMode.PLAY,), (), tuple(tools)),),
        skill_digests={},
        digest=digest,
    )


class FixtureProvider(RemoteExecutionPort):
    """A provider behind the port: it records the request and answers with a prepared result."""

    def __init__(self, answer) -> None:
        self.answer = answer
        self.requests: list[RemoteOperationRequest] = []

    async def run_operation(self, request: RemoteOperationRequest) -> RemoteOperationResult:
        self.requests.append(request)
        return self.answer(request)


def _completed(*records: AssertionRecord, evidence=()):
    return lambda request: RemoteOperationResult(
        OperationStatus.COMPLETED,
        records=tuple(records),
        evidence=tuple(evidence),
        provider_version="fixture-editor@0.1",
        ran_with={"editor": "9.9"},
        dispatch_id=request.dispatch_id,
    )


def _inputs(**over):
    base = {
        "operation": {
            "contract": CONTRACT,
            "mode": "play",
            "role": "qa",
            "skillset": "fixture-qa",
            "skillset_digest": "digest-1",
            "agent_id": "eve",
        },
        "operation_scenario": {
            "scenario_id": "open-the-map",
            "digest": "sha256:scenario",
            "assertions": ["map_opens", "marker_shown", "closes_on_escape"],
        },
        "acceptance_workspace_files": {"src/Client/Map.local.luau": "-- map"},
        "workspace_revision_id": "rev_candidate",
    }
    return {**base, **over}


@pytest.fixture
def held(monkeypatch):
    """The deployment holds the fixture skillset."""
    monkeypatch.setattr(
        run_remote_operation, "packaged_skillsets", lambda: {"fixture-qa": _skillset(TOOL)}
    )


def _context(port, dispatch_id: str | None = "send-7") -> ExecutionContext:
    ports = MagicMock()
    ports.remote_execution = port
    return ExecutionContext.create(
        agent_id="eve",
        role_id="qa",
        task_id="task-7",
        cycle_id="cyc_1",
        ports=ports,
        dispatch_id=dispatch_id,
    )


async def _run(answer=None, *, port="provider", dispatch_id: str | None = "send-7", **over):
    provider = FixtureProvider(answer) if answer is not None else None
    bound = provider if port == "provider" else None
    result = await QARunRemoteOperationHandler().handle(
        _context(bound, dispatch_id), _inputs(**over)
    )
    return result, provider


def _verdict(result) -> tuple[RunVerdict, dict[str, str]]:
    """The run verdict the roll-up reads from this task's outputs, and each unverified
    check's disclosed reason: the handler's rows through the real normalizer and aggregator."""
    summary = aggregate_verification(normalize_task_checks(result.outputs, subject="task-7"))
    return summary.verdict, {u.check_id.rsplit(":", 1)[1]: u.reason for u in summary.unverified}


PASSED = AssertionRecord("map_opens", AssertionOutcome.PASSED, "true", "true", "client")
SHOWN = AssertionRecord("marker_shown", AssertionOutcome.PASSED, "1", "1", "client")
CLOSES = AssertionRecord("closes_on_escape", AssertionOutcome.PASSED, "true", "true", "client")


async def test_the_provider_is_asked_for_the_contract_by_the_skillsets_tool_on_the_candidate(held):
    """Bug caught: the handler naming an operation or a provider of its own, or sending a tree
    other than the candidate at its revision."""
    result, provider = await _run(_completed(PASSED, SHOWN, CLOSES))

    (request,) = provider.requests
    assert (request.contract, request.mode) == (CONTRACT, "play")
    assert (request.provider, request.operation, request.location) == (
        "fixture-editor",
        "play_scenario",
        "worker",
    )
    assert request.source_revision == "rev_candidate"
    assert request.source_files == {"src/Client/Map.local.luau": "-- map"}
    assert request.scenario.assertions == ("map_opens", "marker_shown", "closes_on_escape")
    assert (request.task_id, request.dispatch_id) == ("task-7", "send-7")
    assert result.success


async def test_a_task_that_came_in_no_named_send_asks_for_nothing_and_fails(held):
    """The operation is asked for, read and stopped under the send (SIP-0117 R5.6). Bug
    caught: the task id sent in the send's place, so the runtime refuses every call, or a
    retry's operation can't be told from the first send's."""
    result, provider = await _run(_completed(PASSED, SHOWN, CLOSES), dispatch_id=None)

    assert not result.success
    assert "task task-7 came in no named send" in result.error
    assert provider.requests == []
    assert result.outputs["outcome_class"] == "semantic_failure"


async def test_every_assertion_passing_is_an_accepted_run_with_its_evidence_stored(held):
    console = EvidenceItem("console.log", "[assert] map_opens ok")
    result, _ = await _run(_completed(PASSED, SHOWN, CLOSES, evidence=[console]))

    assert _verdict(result) == (RunVerdict.ACCEPTED, {})
    records, evidence = result.outputs["artifacts"]
    assert (records["type"], evidence["type"]) == (
        ASSERTION_RECORDS_ARTIFACT_TYPE,
        OPERATION_EVIDENCE_ARTIFACT_TYPE,
    )
    assert evidence["content"] == "[assert] map_opens ok"
    document = json.loads(records["content"])
    assert document["provider_version"] == "fixture-editor@0.1"
    assert document["ran_with"] == {"editor": "9.9"}
    assert document["source_revision"] == "rev_candidate"
    assert document["scenario"]["digest"] == "sha256:scenario"
    assert [a["outcome"] for a in document["assertions"]] == ["passed", "passed", "passed"]


async def test_a_failed_assertion_is_an_executed_failure_and_the_run_is_rejected(held):
    failed = AssertionRecord("marker_shown", AssertionOutcome.FAILED, "0", "1", "client")

    result, _ = await _run(_completed(PASSED, failed, CLOSES))

    assert _verdict(result) == (RunVerdict.REJECTED, {})
    # The task fails, carrying the failed row, so the correction loop has something to repair.
    assert not result.success
    assert result.error == "scenario:open-the-map:marker_shown: observed '0', expected '1'"
    assert result.outputs["outcome_class"] == "semantic_failure"
    assert has_blocking_failure(result.outputs)
    (row,) = [c for c in result.outputs["validation_result"]["checks"] if c["status"] == "failed"]
    assert row["check"] == "scenario:open-the-map:marker_shown"
    assert row["reason"] == "observed '0', expected '1'"
    assert result.outputs["summary"].endswith("2 passed, 1 failed, 0 not executed of 3")


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        (AssertionOutcome.SETUP_FAILED, "evaluator_gap:setup_failed"),
        (AssertionOutcome.UNSUPPORTED_INPUT, "evaluator_gap:unsupported_input"),
        (AssertionOutcome.WRONG_CONTEXT, "evaluator_gap:wrong_context"),
    ],
)
async def test_an_assertion_that_did_not_execute_blocks_the_run_and_is_never_a_failure(
    held, outcome, reason
):
    """R3.7: only ``failed`` is an executed behavioural failure. Bug caught: a scenario whose
    setup never established reading as a product failure, or as nothing at all."""
    result, _ = await _run(_completed(PASSED, AssertionRecord("marker_shown", outcome), CLOSES))

    assert _verdict(result) == (RunVerdict.BLOCKED_UNVERIFIED, {"marker_shown": reason})


async def test_a_declared_assertion_with_no_record_is_missing_never_passed(held):
    """Bug caught: the absence of a record reading as a pass, so a scenario that silently
    skipped its last assertion is accepted."""
    result, _ = await _run(_completed(PASSED, SHOWN))

    assert _verdict(result) == (
        RunVerdict.BLOCKED_UNVERIFIED,
        {"closes_on_escape": "evaluator_gap:missing"},
    )


async def test_a_failure_does_not_hide_an_assertion_that_never_ran(held):
    failed = AssertionRecord("marker_shown", AssertionOutcome.FAILED, "0", "1")

    result, _ = await _run(_completed(PASSED, failed))

    verdict, unverified = _verdict(result)
    assert verdict is RunVerdict.BLOCKED_UNVERIFIED
    assert unverified == {"closes_on_escape": "evaluator_gap:missing"}


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (OperationStatus.NOT_EXECUTED, "evaluator_gap:operation_not_executed"),
        (OperationStatus.INTERRUPTED, "evaluator_gap:operation_interrupted"),
    ],
)
async def test_an_operation_that_did_not_run_or_was_interrupted_verifies_nothing(
    held, status, reason
):
    """R3.3: neither reads as a failure or a pass."""
    answer = lambda request: RemoteOperationResult(  # noqa: E731
        status, reason="the worker's editor was closed", dispatch_id=request.dispatch_id
    )

    result, _ = await _run(answer)

    verdict, unverified = _verdict(result)
    assert verdict is RunVerdict.BLOCKED_UNVERIFIED
    assert unverified == dict.fromkeys(("map_opens", "marker_shown", "closes_on_escape"), reason)
    document = json.loads(result.outputs["artifacts"][0]["content"])
    assert (document["status"], document["reason"]) == (
        status.value,
        "the worker's editor was closed",
    )
    assert document["assertions"] == []


async def test_an_agent_with_no_port_bound_reports_the_operation_as_not_executed(held):
    """Bug caught: an absent port reading as an empty, passing run. The reason names the
    binding, so it isn't mistaken for a provider's refusal."""
    result, _ = await _run(port=None)

    verdict, unverified = _verdict(result)
    assert verdict is RunVerdict.BLOCKED_UNVERIFIED
    assert set(unverified.values()) == {"evaluator_gap:no_remote_execution_port"}
    assert result.success


@pytest.mark.parametrize(
    ("answer", "defect"),
    [
        (
            lambda r: RemoteOperationResult(
                OperationStatus.COMPLETED, records=(PASSED, SHOWN, CLOSES), dispatch_id="task-6"
            ),
            "echoes dispatch 'task-6'",
        ),
        (
            lambda r: RemoteOperationResult(
                OperationStatus.COMPLETED,
                records=(PASSED, SHOWN, CLOSES, AssertionRecord("extra", AssertionOutcome.PASSED)),
                dispatch_id=r.dispatch_id,
            ),
            "a record for 'extra', which the scenario doesn't declare",
        ),
        (
            lambda r: RemoteOperationResult(
                OperationStatus.COMPLETED,
                records=(PASSED, PASSED, SHOWN),
                dispatch_id=r.dispatch_id,
            ),
            "more than one record for 'map_opens'",
        ),
        (
            lambda r: RemoteOperationResult(
                OperationStatus.NOT_EXECUTED, dispatch_id=r.dispatch_id
            ),
            "is not_executed and gives no reason",
        ),
        (
            lambda r: RemoteOperationResult(
                OperationStatus.INTERRUPTED,
                reason="lease expired",
                records=(PASSED,),
                dispatch_id=r.dispatch_id,
            ),
            "is interrupted and still returned records",
        ),
    ],
    ids=["a stale echo", "an undeclared assertion", "two records", "no reason", "records after"],
)
async def test_a_result_that_does_not_answer_the_request_credits_nothing(held, answer, defect):
    """A provider is outside the framework. Bug caught: a late result from an earlier dispatch,
    or records the scenario never asked for, being read as this run's passes."""
    result, _ = await _run(answer)

    verdict, unverified = _verdict(result)
    assert verdict is RunVerdict.BLOCKED_UNVERIFIED
    assert set(unverified.values()) == {"evaluator_gap:operation_result_unreadable"}
    assert defect in json.loads(result.outputs["artifacts"][0]["content"])["reason"]


@pytest.mark.parametrize(
    ("catalog", "over", "expected"),
    [
        (
            {},
            {},
            "skillset `fixture-qa` supplies this task by the cycle's record, and this deployment doesn't hold it",
        ),
        (
            {"fixture-qa": _skillset(TOOL, digest="digest-2")},
            {},
            "skillset `fixture-qa` has changed since the cycle was created",
        ),
        (
            {"fixture-qa": _skillset()},
            {},
            "skillset `fixture-qa` requests 0 tools for `game.scenario_verification`",
        ),
        (
            {"fixture-qa": _skillset(TOOL, ToolRequest("capture", "fixture-editor", "worker"))},
            {},
            "skillset `fixture-qa` requests 2 tools for `game.scenario_verification`",
        ),
        (
            {"fixture-qa": _skillset(TOOL)},
            {"operation": {**_inputs()["operation"], "mode": "multiplayer"}},
            "skillset `fixture-qa` doesn't specialize `game.scenario_verification` in `multiplayer` mode",
        ),
    ],
    ids=["not held", "changed since creation", "no tool", "two tools", "another mode"],
)
async def test_a_supplier_the_deployment_cannot_vouch_for_fails_the_task_and_runs_nothing(
    monkeypatch, catalog, over, expected
):
    """Bug caught: an operation run in the name of a skillset that was revised after the cycle
    recorded it, or picked among several tools by position."""
    monkeypatch.setattr(run_remote_operation, "packaged_skillsets", lambda: catalog)

    result, provider = await _run(_completed(PASSED, SHOWN, CLOSES), **over)

    assert not result.success
    assert expected in result.error
    assert provider.requests == []
    # No executed failure, so the executor ends the run on it rather than repairing anything.
    assert not has_blocking_failure(result.outputs)
    assert result.outputs["outcome_class"] == "semantic_failure"


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"operation": None}, "'operation' is required"),
        ({"operation": {"contract": CONTRACT, "mode": "play"}}, "'operation.skillset' is required"),
        ({"operation_scenario": None}, "'operation_scenario' is required"),
        (
            {"operation_scenario": {"scenario_id": "s", "digest": "d", "assertions": []}},
            "A scenario that asserts nothing verifies nothing",
        ),
        (
            {"operation_scenario": {"scenario_id": "s", "digest": "d", "assertions": ["a", "a"]}},
            "'operation_scenario.assertions' is required",
        ),
        (
            {"operation_scenario": {"scenario_id": "s", "assertions": ["a"]}},
            "'operation_scenario.digest' is required",
        ),
        ({"acceptance_workspace_files": None}, "'acceptance_workspace_files' is required"),
        ({"workspace_revision_id": ""}, "'workspace_revision_id' is required"),
    ],
)
def test_an_input_the_operation_needs_is_required_and_nothing_is_filled_in(change, expected):
    errors = QARunRemoteOperationHandler().validate_inputs(_inputs(**change))

    assert any(expected in e for e in errors), errors


def test_complete_inputs_are_accepted():
    assert QARunRemoteOperationHandler().validate_inputs(_inputs()) == []


def test_the_handler_is_registered_for_qa_and_constructs_with_no_arguments():
    """``create_handler_registry`` logs and skips a handler whose constructor raises, and the
    task then fails at dispatch as having no handler. Bug caught: that, for this type."""
    assert (QARunRemoteOperationHandler, ("qa",)) in HANDLER_CONFIGS

    registry = create_handler_registry(roles=["qa"])

    assert isinstance(registry.get(TaskType.QA_RUN_REMOTE_OPERATION), QARunRemoteOperationHandler)


def test_the_type_runs_an_operation_and_is_corrected_only_for_an_executed_failure():
    """Bug caught: the loop's default sending every failure of this type to a dev repair,
    including an operation that never ran, where no edit to the application could help."""
    assert runs_an_operation("qa.run_remote_operation")
    assert corrects_only_executed_failures("qa.run_remote_operation")
    assert not fails_without_correction("qa.run_remote_operation")
    assert not runs_an_operation("qa.test")
    assert not corrects_only_executed_failures("qa.test")


@pytest.mark.parametrize(
    ("metadata", "asked", "failure"),
    [
        ({"dispatch_id": "send-9"}, ("task-7", "send-9"), None),
        ({}, None, "came in no named send"),
        ({"dispatch_id": 9}, None, "ValueError"),
    ],
    ids=["the-send-it-came-in", "no-send", "a-send-that-isnt-text"],
)
async def test_the_send_an_agent_was_dispatched_reaches_the_request(held, metadata, asked, failure):
    """The wiring (R5.6), entered at the handler executor, which builds the handler's context
    from the dispatched envelope as the agent does. Bug caught: the envelope's dispatch id
    dropped on the way to the context, so every live request goes out under no send; or a
    malformed one passed through as if it named a send."""
    provider = FixtureProvider(_completed(PASSED, SHOWN, CLOSES))
    ports = MagicMock()
    ports.remote_execution = provider
    registry = HandlerRegistry()
    registry.register(QARunRemoteOperationHandler(), roles=("qa",))
    executor = HandlerExecutor(executor_id="eve", handler_registry=registry, ports=ports, role="qa")
    envelope = TaskEnvelope(
        task_id="task-7",
        agent_id="eve",
        cycle_id="cyc_1",
        pulse_id="pulse-1",
        project_id="project-1",
        task_type=TaskType.QA_RUN_REMOTE_OPERATION,
        inputs=_inputs(),
        correlation_id="corr-1",
        causation_id="cause-1",
        trace_id="trace-1",
        span_id="span-1",
        metadata=metadata,
    )

    result = await executor.execute(envelope)

    sent = [(r.task_id, r.dispatch_id) for r in provider.requests]
    assert sent == ([asked] if asked else [])
    if failure is None:
        assert result.status == "SUCCEEDED"
    else:
        assert result.status == "FAILED"
        assert failure in f"{result.error} {result.execution_evidence}"
