"""Which ``qa.test`` output shape a dispatched task reaches — entered at the live callers (#1444).

#1444 moved the choice between whole-file authoring and scaffold fill out of branches on
``verification_scaffold`` inside ``handle()`` and into ``QATestHandler._output_shape``,
which selects the shape that parses, merges and evidences the emission. The handler
tests hand ``handle()`` its inputs directly; that proves the handler, not the wiring
(TEST_QUALITY_STANDARD anti-pattern 6a).

These enter where a cycle does. The cycle executor's ``inject_contract_inputs`` builds the
qa envelope's inputs — the only producer of ``verification_scaffold`` — and the agent's
``HandlerExecutor`` resolves ``qa.test`` from the bootstrap registry and calls ``handle()``
with the envelope's inputs. The same fills-only emission is then merged into the frozen
shells on a stack that opts into the verification scaffold, and extracted as a file named
for the slot on one that does not.

Bug caught: a selector that keys on something the envelope does not carry — a renamed
input, a shape table keyed on the wrong value, a registry binding a handler whose
``_output_shape`` is the base's ``None`` — so a scaffold-bound task is parsed as whole
files, its fills are stored as stray files, and nothing is merged into the shells.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from squadops.agents.base import PortsBundle
from squadops.bootstrap.handlers import create_handler_registry
from squadops.capabilities.handlers.test_runner import RunTestsResult
from squadops.capabilities.scaffold_contract import emit_contract_dict
from squadops.cycles.task_plan import inject_contract_inputs
from squadops.cycles.verification_contract import VerificationContract
from squadops.llm.models import ChatMessage
from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.tasks.models import TaskEnvelope
from squadops.tasks.task_types import TaskType
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_capabilities]

_FILLS_ONLY = (
    "Fills below.\n\n```fill:slot-vc-probe-api-runs\n    expect(body.id).toBeTruthy()\n```\n"
)
_SHELL = "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"


def _executor(sent: list[dict]) -> HandlerExecutor:
    llm = MagicMock()
    # A registered model, so the capability's reasoning declaration is actually sent.
    llm.default_model = "qwen3.8:27b"

    async def _chat(messages, **kwargs):
        sent.append(dict(kwargs))
        return ChatMessage(role="assistant", content=_FILLS_ONLY, completion_tokens=40)

    llm.chat_stream_with_usage = _chat
    assembled = MagicMock()
    assembled.content = "system"
    assembled.assembly_hash = "sha256:x"
    prompt_service = MagicMock()
    prompt_service.assemble.return_value = assembled
    ports = PortsBundle(
        llm=llm,
        memory=MagicMock(),
        prompt_service=prompt_service,
        queue=MagicMock(),
        metrics=MagicMock(),
        events=MagicMock(),
        filesystem=MagicMock(),
    )
    return HandlerExecutor("qa-agent", create_handler_registry(roles=["qa"]), ports, role="qa")


def _envelope(stack: str) -> TaskEnvelope:
    manifest = manifest_for_stack(stack)
    inputs: dict = {
        "prd": "group_run",
        "artifact_contents": {},
        "subtask_focus": "cover the runs API",
        "expected_artifacts": [],
        "resolved_config": {"development_profile": stack},
    }
    contract = VerificationContract.from_dict(emit_contract_dict(manifest))
    inject_contract_inputs(inputs, contract, TaskType.QA_TEST, manifest)
    return TaskEnvelope(
        task_id="task-qa",
        agent_id="qa-agent",
        cycle_id="cyc_wiring",
        pulse_id="pulse-1",
        project_id="group_run",
        task_type=TaskType.QA_TEST,
        inputs=inputs,
        correlation_id="corr",
        causation_id="cause",
        trace_id="trace",
        span_id="span",
    )


@pytest.fixture(autouse=True)
def _no_real_runner(monkeypatch):
    """The suite runner and the contract probes execute subprocesses and boot the app.
    Neither is the subject here; both run after the shape has already been chosen."""

    async def _passed(framework, sources, tests, timeout_seconds=None):
        return RunTestsResult(executed=True, exit_code=0, runner="vitest", suite_broken=False)

    monkeypatch.setattr("squadops.capabilities.handlers.test_runner.run_build_validation", _passed)
    monkeypatch.setattr(
        "squadops.capabilities.handlers.probe_runner.run_probes", lambda *a, **kw: []
    )


async def test_a_scaffold_bound_task_reaches_the_fill_shape_through_the_agent_executor():
    sent: list[dict] = []
    envelope = _envelope("nextjs_ts")
    assert envelope.inputs.get("verification_scaffold"), "the injection is what opts the task in"

    result = await _executor(sent).execute(envelope)

    assert result.status == "SUCCEEDED", result.error
    assert "emission_failure" not in result.outputs
    stored = {a["name"]: a for a in result.outputs["artifacts"]}
    assert len([n for n in stored if n.startswith("__tests__/scaffold/")]) == 8
    assert "expect(body.id).toBeTruthy()" in stored[_SHELL]["content"]
    assert "slot-vc-probe-api-runs" not in stored
    assert "fill_merge_evidence.json" in stored
    # The reasoning declaration read the same shape the parse did (register entry 44).
    assert sent[0]["reasoning"] == "low"


async def test_the_same_emission_without_a_scaffold_reaches_the_whole_file_shape():
    sent: list[dict] = []
    envelope = _envelope("fullstack_fastapi_react")
    assert "verification_scaffold" not in envelope.inputs

    result = await _executor(sent).execute(envelope)

    stored = {a["name"]: a for a in result.outputs["artifacts"]}
    # Parsed as whole files: the fill fence became a test file named for the slot, nothing
    # was merged into a shell, and there is no fill-merge evidence to bank.
    assert stored["slot-vc-probe-api-runs"]["type"] == "test"
    assert not any(n.startswith("__tests__/scaffold/") for n in stored)
    assert "fill_merge_evidence.json" not in stored
    assert "scaffold_evidence" not in result.outputs
    assert sent[0]["reasoning"] == "medium"
