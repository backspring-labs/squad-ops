"""The convergence replay's container stage (#1764): admission, the measures, the rebuilt records.

Bug classes guarded: a round admitted when its suite never executed (a crash would read as a
reproduced failure), a recorded check the verifier does not evaluate counted as not reproducing, a
handler's own report measured as the model's revision, and a cycle or profile rebuilt wrong, which
would change the repair's inputs without any error.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from squadops.cycles.models import AgentProfileEntry, Cycle, Gate, SquadProfile, TaskFlowPolicy

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
