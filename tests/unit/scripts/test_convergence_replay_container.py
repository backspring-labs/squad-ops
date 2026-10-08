"""The convergence replay's container stage (#1764): admission, the measures, the rebuilt records.

Bug classes guarded: a round admitted when its suite never executed (a crash would read as a
reproduced failure), a recorded check the verifier does not evaluate counted as not reproducing, a
handler's own report measured as the model's revision, and a cycle or profile rebuilt wrong, which
would change the repair's inputs without any error.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import inspect
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from squadops.cycles.models import AgentProfileEntry, Cycle, Gate, SquadProfile, TaskFlowPolicy
from squadops.memory.lessons import RecallDisposition

_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "dev" / "convergence_replay" / "container.py"
)
_SPEC = importlib.util.spec_from_file_location("convergence_replay_container", _PATH)
container = importlib.util.module_from_spec(_SPEC)
sys.modules["convergence_replay_container"] = container
_SPEC.loader.exec_module(container)


def _bundle(failed_checks: list[str]) -> dict:
    return {
        "round": {"failure": {"failed_checks": failed_checks}, "run_id": "run_x"},
        "prd": "the prd",
        "agents": {"qa": {"agent_id": "eve", "model": "m", "config_overrides": {}}},
        "resolved_config": {"build_profile": "fullstack_fastapi_react"},
        "failed_artifacts": [{"name": "tests/test_runs.py", "content": "def test(): assert 0\n"}],
        "envelope": {
            "task_id": "task-run_x-m005-qa.test",
            "agent_id": "eve",
            "cycle_id": "cyc_x",
            "pulse_id": "p",
            "project_id": "group_run",
            "task_type": "qa.test",
            "correlation_id": "c",
            "causation_id": "c",
            "trace_id": "t",
            "span_id": "s",
            "inputs": {"acceptance_criteria": [], "acceptance_workspace_files": {}},
        },
    }


def _system(tests_pass_row: dict) -> SimpleNamespace:
    result = SimpleNamespace(
        outputs={"validation_result": {"checks": [{"check": "tests_pass", **tests_pass_row}]}},
        error="Repaired suite still fails (exit 1)",
        status="FAILED",
    )
    return SimpleNamespace(orchestrator=SimpleNamespace(submit_task=AsyncMock(return_value=result)))


@pytest.mark.parametrize(
    "row, verdict",
    [
        ({"passed": False, "executed": True}, container.ADMITTED),
        ({"passed": False, "executed": False}, container.NOT_REPRODUCED),
        ({"passed": True, "executed": True}, container.NOT_REPRODUCED),
    ],
    ids=["suite-ran-and-failed", "suite-never-executed", "suite-now-passes"],
)
async def test_a_round_is_admitted_only_when_its_suite_executes_and_fails(row, verdict):
    """The retest's error text is present on a real reproduction too ("Repaired suite still
    fails"); only an executed failing suite reproduces a recorded tests_pass."""
    reading = await container.admit(_bundle(["tests_pass"]), _system(row))

    assert reading["verdict"] == verdict


async def test_a_check_the_verifier_does_not_evaluate_is_its_own_verdict(monkeypatch):
    """A framework-owed build row (acceptance:frontend_compiles) has no typed criterion; reading
    its absence as "did not reproduce" would drop the round for the wrong reason."""

    async def no_rows(*args, **kwargs):
        return SimpleNamespace(checks=())

    monkeypatch.setattr("squadops.cycles.patch_verification.verify_patched_artifacts", no_rows)

    reading = await container.admit(
        _bundle(["acceptance:frontend_compiles"]), _system({"passed": True})
    )

    assert reading["verdict"] == container.UNEVALUATED
    assert (await container.admit(_bundle([]), _system({})))["verdict"] == (
        container.NO_RECORDED_CHECK
    )


def test_only_the_files_the_repair_was_asked_to_revise_are_measured():
    bundle = _bundle(["tests_pass"])
    bundle["envelope"]["inputs"]["acceptance_workspace_files"] = {"app/x.py": "a\n"}
    emitted = [
        {"name": "tests/test_runs.py", "content": "def test(): assert 1\n", "type": "source"},
        {"name": "tests/test_new.py", "content": "x\ny\n", "type": "source"},
        {"name": "test_report.md", "content": "a report", "type": "document"},
        {
            "name": "typed_check_evaluation_task_5.json",
            "content": "{}",
            "type": "typed_check_evaluation",
        },
    ]

    measured = container.response_measures(
        bundle, emitted, asked={"tests/test_runs.py", "tests/test_new.py"}
    )

    assert [(f["file"], f["changed_lines"], f["new_file"]) for f in measured["files"]] == [
        ("tests/test_runs.py", 2, False),
        ("tests/test_new.py", 2, True),
    ]
    assert container.response_measures(bundle, emitted, asked=set())["empty"] is True


def test_the_cycle_and_profile_rebuild_to_what_was_bundled():
    cycle = Cycle(
        cycle_id="cyc_x",
        project_id="group_run",
        created_at=datetime(2026, 9, 29, tzinfo=UTC),
        created_by="system",
        prd_ref="the prd text",
        squad_profile_id="full-38",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(
            mode="sequential",
            gates=(Gate(name="g", description="d", after_task_types=("qa.test",)),),
        ),
        build_strategy="fresh",
        applied_defaults={"build_profile": "fullstack_fastapi_react"},
        expected_artifact_types=("source",),
        deploy_id="dep_x",
    )
    profile = SquadProfile(
        profile_id="full-38",
        name="Full",
        description="d",
        version=1,
        agents=(
            AgentProfileEntry(
                agent_id="eve", role="qa", model="qwen3.8:27b", enabled=True, serves_roles=("qa",)
            ),
        ),
        created_at=datetime(2026, 9, 29, tzinfo=UTC),
    )

    assert container.cycle_from_dict(dataclasses.asdict(cycle)) == cycle
    assert container.profile_from_dict(dataclasses.asdict(profile)) == profile


def test_a_loaded_bundle_carries_no_fault_to_fire_in_the_replay(tmp_path):
    """Bug caught (#1764, the first live sample): a round from a diagnostic cycle was rebuilt with
    its declared faults, and `repair_prose_only` replaced the model's repair with planted prose.
    The declaration sits in four places, and the correction runner reads the cycle's."""
    from squadops.capabilities.handlers.fault_injection import declared_faults

    declared = "qa_suite_own_frame_failure,repair_prose_only"
    bundle = _bundle(["tests_pass"])
    bundle["resolved_config"]["fault_injection"] = declared
    bundle["envelope"]["inputs"]["resolved_config"] = {"fault_injection": declared, "x": 1}
    bundle["cycle"] = {
        "applied_defaults": {"fault_injection": declared, "build_profile": "p"},
        "execution_overrides": {"fault_injection": declared},
    }
    bundle["failed_artifacts"][0]["content"] = "# mentions fault_injection in prose\n"
    path = tmp_path / "b.json"
    path.write_text(__import__("json").dumps(bundle))

    loaded = container.load_bundle(path)

    assert declared_faults(loaded["resolved_config"]) == ()
    assert declared_faults(loaded["envelope"]["inputs"]["resolved_config"]) == ()
    assert loaded["cycle"] == {
        "applied_defaults": {"build_profile": "p"},
        "execution_overrides": {},
    }
    # File content is evidence, not a declaration: untouched.
    assert loaded["failed_artifacts"][0]["content"] == "# mentions fault_injection in prose\n"
    assert loaded["envelope"]["inputs"]["resolved_config"]["x"] == 1


# --- #1788: each repair step keeps the generations it made --------------------------------


class _FakeLLM:
    """Answers each call with the next canned reply, or raises it."""

    def __init__(self, *replies):
        self._replies = list(replies)

    async def chat_stream_with_usage(self, messages, **kwargs):
        reply = self._replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


def _reply(content: str):
    from squadops.llm.models import ChatMessage

    return ChatMessage(
        role="assistant",
        content=content,
        prompt_tokens=900,
        completion_tokens=40,
        reasoning_tokens=12,
        reasoning_text="thinking",
    )


_PROSE = "The failing test is in a suite I may not edit, so I am leaving the app unchanged."
_MALFORMED_EDIT = "```edit:app/x.py\n<<<<<<< SEARCH\nfoo\n```\n"


@pytest.mark.parametrize(
    "content, reading",
    [
        ("", {"chars": 0, "edit_fences_found": False, "edits_malformed": [], "whole_files": []}),
        (
            _PROSE,
            {
                "chars": len(_PROSE),
                "edit_fences_found": False,
                "edits_malformed": [],
                "whole_files": [],
            },
        ),
        (
            _MALFORMED_EDIT,
            {
                "chars": len(_MALFORMED_EDIT),
                "edit_fences_found": True,
                "edits_malformed": [{"path": "app/x.py", "reason": "missing_divider"}],
                "whole_files": [],
            },
        ),
    ],
    ids=["an empty response", "a prose-only abstention", "an edit that failed to parse"],
)
async def test_a_sample_keeps_what_each_empty_repair_said(monkeypatch, content, reading):
    """#1788: nine Next.js repairs read ``emitted 0`` and the record could not say why.
    Entered at ``replay_sample``, the function ``_replay_all`` runs per sample, with the
    repair and its judge stubbed and the role's recorded adapter real. Bug caught: the
    response, its parse and its usage not kept, so these three read the same; or a stale
    generation from before the step credited to it."""
    from squadops.tasks.models import TaskEnvelope

    recorder = container.RecordingLLM(_FakeLLM(_reply("a stale earlier call"), _reply(content)))
    await recorder.chat_stream_with_usage([])  # made before the step: not its response
    transaction = {"accepted": False, "refusals": ["app/x.py: missing_divider"]}

    async def _submit(step_envelope, timeout_seconds):
        await recorder.chat_stream_with_usage([])
        return SimpleNamespace(outputs={"llm_usage": None, "anchored_edits": transaction})

    from adapters.cycles.correction_repair import CorrectionRepair

    constructed: dict = {}

    class _Repair:
        def __init__(self, **kwargs):
            # Bound against the real constructor, so a dependency it comes to require fails here
            # rather than as every live sample's `unrunnable` (#2129 added `failure_recall`).
            inspect.signature(CorrectionRepair.__init__).bind(None, **kwargs)
            constructed.update(kwargs)
            self._dispatch_step = kwargs["dispatch_step"]

        async def dispatch(self, mode, diagnosis, envelope, result, cycle, run_id, *a, **k):
            step = TaskEnvelope.from_dict(
                {
                    **_bundle(["tests_pass"])["envelope"],
                    "task_type": "development.repair",
                    "metadata": {"role": "dev"},
                }
            )
            await self._dispatch_step(step, run_id, cycle, None)
            return SimpleNamespace(
                artifacts=[],
                typed_checks=[],
                steps_ran=["development.repair"],
                empty_signatures=[],
                anchored_edits_refused=False,
            )

    class _Judge:
        def __init__(self, **_):
            pass

        async def accept(self, *a, **k):
            return "reject_patch"

    monkeypatch.setattr("adapters.cycles.correction_repair.CorrectionRepair", _Repair)
    monkeypatch.setattr("adapters.cycles.patch_acceptance.PatchAcceptance", _Judge)
    monkeypatch.setattr(container, "cycle_from_dict", lambda d: SimpleNamespace())
    monkeypatch.setattr(container, "profile_from_dict", lambda d: SimpleNamespace())
    bundle = {**_bundle(["tests_pass"]), "analysis": {}, "decision": {}, "cycle": {}, "profile": {}}
    systems = {
        "dev": SimpleNamespace(
            ports=SimpleNamespace(llm=recorder),
            orchestrator=SimpleNamespace(submit_task=_submit),
        )
    }
    retest = _system({"passed": False, "executed": True}).orchestrator.submit_task.return_value

    row = await container.replay_sample(bundle, systems, retest)

    (step,) = row["usage"]
    (kept,) = step["responses"]
    assert {k: kept[k] for k in reading} == reading
    assert (kept["text"], kept["truncated"]) == (content, False)
    assert (kept["prompt_tokens"], kept["completion_tokens"], kept["reasoning_tokens"]) == (
        900,
        40,
        12,
    )
    assert step["anchored_edits"] == transaction
    recalled = await constructed["failure_recall"].recall(None)
    assert recalled.disposition is RecallDisposition.DISABLED  # the pre-memory prompt


async def test_a_long_response_is_kept_bounded_and_a_failed_call_as_its_error():
    """The edges: a response past the limit keeps its true length beside the bounded text; a
    call that raises is kept as its error and still raises. Bug caught: an unbounded sample
    row, or a timed-out call vanishing so the step reads as a model that said nothing."""
    long = "x" * (container.RAW_RESPONSE_LIMIT + 10)
    recorder = container.RecordingLLM(_FakeLLM(_reply(long), TimeoutError("read timed out")))

    await recorder.chat_stream_with_usage([])
    with pytest.raises(TimeoutError):
        await recorder.chat_stream_with_usage([])

    first, second = (container.response_reading(c) for c in recorder.drain())
    assert (first["chars"], len(first["text"]), first["truncated"]) == (
        len(long),
        container.RAW_RESPONSE_LIMIT,
        True,
    )
    assert second == {"error": "TimeoutError: read timed out"}
    assert recorder.drain() == []


async def test_every_role_generates_through_its_own_recorder(monkeypatch):
    """``_replay_all`` composes through ``compose_recorded_systems``. Bug caught: a role whose
    adapter is not recorded (its steps would carry no responses), or the stub answering for
    one role only."""
    composed = []

    async def _compose(role, *, model, llm=None):
        composed.append((role, llm))
        return SimpleNamespace(ports=SimpleNamespace(llm=llm or _FakeLLM()))

    monkeypatch.setattr(container, "compose_system", _compose)
    bundle = {"agents": {"dev": {"model": "m"}, "qa": {"model": "m"}}}

    systems, stub = await container.compose_recorded_systems(bundle, stub=True)

    assert sorted(systems) == ["dev", "qa"]
    assert all(isinstance(s.ports.llm, container.RecordingLLM) for s in systems.values())
    assert {id(s.ports.llm._inner) for s in systems.values()} == {id(stub)}
    plain, no_stub = await container.compose_recorded_systems(bundle, stub=False)
    assert no_stub is None
    assert not any(isinstance(s.ports.llm._inner, container.StubLLM) for s in plain.values())
