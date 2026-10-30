"""#2818: a product's ``qa.test`` failing only ``tests_pass`` in the qa image is judged on the
product's own runner, after its configured setup.

Bug caught: a product whose code needs a dependency the qa image lacks (2.5's ``z_continuum`` and
``tomli``) can never pass a criterion in-cycle, however correct the build, because the suite only
ever runs where the product's install never happened.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor, _TaskOutcomeRouter
from squadops.execution.product_suite import (
    PRODUCT_RUNNER,
    judge_on_product_runner,
    rejudgeable,
)
from squadops.tasks.models import TaskEnvelope, TaskResult, TaskResultStatus

pytestmark = [pytest.mark.domain_orchestration]

_INPUTS = {
    "source_repository": {"runners": []},
    "artifact_contents": {
        "app/main.py": "import plugins\n",
        "app/plugin.toml": "[plugin]\n",
        "tests/test_existing.py": "def test_old(): ...\n",
    },
}
_SETUP = (("pip", "install", "-e", "."),)


def _failed(*rows: dict[str, Any]) -> TaskResult:
    return TaskResult(
        task_id="t_qa",
        status=TaskResultStatus.FAILED,
        error="suite failed",
        outputs={
            "artifacts": [
                {"name": "tests/test_t1.py", "content": "def test_t1(): ...\n", "type": "test"},
                {"name": "test_report.md", "content": "red", "type": "test_report"},
            ],
            "validation_result": {
                "passed": False,
                "checks": list(rows),
                "missing_components": ["tests_pass"],
            },
            "outcome_class": "semantic_failure",
            "failure_classification": "work_product",
        },
    )


_TESTS_PASS_RED = {"check": "tests_pass", "passed": False, "exit_code": 1, "runner": "pytest"}
_OTHER_GREEN = {"check": "no_stub_fallback_tests", "passed": True}


class _Sandbox:
    def __init__(self, exit_code: int | None = 0, *, raises: bool = False) -> None:
        self.exit_code, self.raises = exit_code, raises
        self.seeded: dict[str, str] = {}
        self.commands: list[dict[str, Any]] = []
        self.released: list[str] = []

    async def release_workspace(self, workspace_id: str) -> None:
        self.released.append(workspace_id)

    async def seed_workspace(self, workspace_id, files, *, origin, **_):
        self.seeded = dict(files)
        return SimpleNamespace(revision_id="rev_1")

    async def run_declared_command(self, *, revision, command, working_dir, setup):
        if self.raises:
            raise RuntimeError("sandbox down")
        self.commands.append({"command": command, "working_dir": working_dir, "setup": setup})
        return SimpleNamespace(ran=True, outcome="exited", exit_code=self.exit_code)


class _Runner:
    runner = "pytest"
    suite_argv = ("python", "-m", "pytest", "-q")

    def holds(self, path: str) -> bool:
        return path.startswith("tests/")


class _Profile:
    def runner_for(self, path: str):
        return _Runner() if _Runner().holds(path) else None


_CYCLE = SimpleNamespace(
    project_id="prj_x",
    source_context=SimpleNamespace(development_configuration_revision=3),
)
_PROJECTS = SimpleNamespace(
    get_development_configuration=lambda *_: _async(
        SimpleNamespace(commands=SimpleNamespace(working_directory=".", check_setup=_SETUP))
    )
)


async def _async(value):
    return value


async def _profile(_cycle):
    return _Profile()


async def _judge(result: TaskResult, sandbox: Any, *, task_type: str = "qa.test", inputs=_INPUTS):
    return await judge_on_product_runner(
        result,
        task_type=task_type,
        task_id="t_qa",
        inputs=inputs,
        cycle=_CYCLE,
        run_id="run_1",
        sandbox=sandbox,
        projects=_PROJECTS,
        read_profile=_profile,
    )


@pytest.mark.parametrize(
    ("task_type", "inputs", "rows", "expected"),
    [
        ("qa.test", _INPUTS, (_TESTS_PASS_RED, _OTHER_GREEN), True),
        # Another failing check is the agent's to report: the product's runner can't clear it.
        ("qa.test", _INPUTS, (_TESTS_PASS_RED, {"check": "no_stub_fallback_tests"}), False),
        # A sample application's suite already runs where its stack's toolchain lives.
        ("qa.test", {"artifact_contents": {}}, (_TESTS_PASS_RED,), False),
        ("development.develop", _INPUTS, (_TESTS_PASS_RED,), False),
    ],
)
def test_only_a_products_suite_failing_only_tests_pass_is_rejudged(
    task_type, inputs, rows, expected
):
    assert rejudgeable(task_type, inputs, _failed(*rows)) is expected


async def test_a_pass_on_the_products_runner_after_its_setup_judges_the_task_passed():
    sandbox = _Sandbox(exit_code=0)
    judged = await _judge(_failed(_TESTS_PASS_RED, _OTHER_GREEN), sandbox)

    assert judged is not None and judged.status == TaskResultStatus.SUCCEEDED
    # The suite ran after the product's own install, on the agent's tree plus the emitted test,
    # and without the product's own tests (the run judges the suite under test only).
    assert sandbox.commands == [
        {"command": ("python", "-m", "pytest", "-q"), "working_dir": ".", "setup": _SETUP}
    ]
    assert set(sandbox.seeded) == {"app/main.py", "app/plugin.toml", "tests/test_t1.py"}
    row = judged.outputs["validation_result"]["checks"][0]
    assert row["passed"] is True and row["judged_on"] == PRODUCT_RUNNER
    assert row["agent_reading"] == _TESTS_PASS_RED
    assert judged.outputs["validation_result"]["missing_components"] == []
    assert "failure_classification" not in judged.outputs
    assert sandbox.released == ["suite-run_1-t_qa", "suite-run_1-t_qa"]


@pytest.mark.parametrize("exit_code", [1, None])
async def test_a_failure_or_no_exit_on_the_products_runner_leaves_the_agents_result(exit_code):
    sandbox = _Sandbox(exit_code=exit_code)
    if exit_code is None:
        sandbox.run_declared_command = lambda **_: _async(
            SimpleNamespace(ran=False, outcome="unavailable", exit_code=None)
        )
    assert await _judge(_failed(_TESTS_PASS_RED), sandbox) is None


async def test_a_test_no_runner_holds_is_not_judged_and_runs_nothing():
    result = _failed(_TESTS_PASS_RED)
    result.outputs["artifacts"][0]["name"] = "spec/t1_spec.py"
    sandbox = _Sandbox()
    assert await _judge(result, sandbox) is None
    assert sandbox.commands == []


async def test_the_workspace_is_released_when_the_run_raises():
    sandbox = _Sandbox(raises=True)
    with pytest.raises(RuntimeError):
        await _judge(_failed(_TESTS_PASS_RED), sandbox)
    assert sandbox.released == ["suite-run_1-t_qa", "suite-run_1-t_qa"]


async def test_the_router_accepts_a_product_suite_judged_passed_without_routing_a_correction():
    """Wiring: enters at the dispatcher's ``handle_task_outcome`` (``_TaskOutcomeRouter.route``),
    as a live cycle's failed ``qa.test`` does, and asserts the correction loop is never asked."""
    executor = object.__new__(DispatchedFlowExecutor)
    executor._sandbox = _Sandbox(exit_code=0)
    executor._project_registry = _PROJECTS
    executor._derived_profile_for = _profile

    async def admit(result, *_a, **_k):
        return result

    executor._admit_failed_emission = admit
    asked: list[Any] = []

    async def next_action(*args):
        asked.append(args)
        return "continue"

    envelope = TaskEnvelope(
        task_id="t_qa",
        agent_id="qa-agent",
        cycle_id="cyc_x",
        pulse_id="p",
        project_id="prj_x",
        task_type="qa.test",
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
        inputs=_INPUTS,
    )
    state = SimpleNamespace(
        produced=SimpleNamespace(all_artifact_refs=[]),
        ownership=SimpleNamespace(bound_record=None, compliance_counter={}),
        correction=SimpleNamespace(accepted_repair_task_ids=set()),
    )
    router = _TaskOutcomeRouter(
        executor=executor,
        state=state,
        envelope=envelope,
        enriched=envelope,
        cycle=_CYCLE,
        run_id="run_1",
        flow_run_id=None,
        profile=None,
        interface_manifest=None,
        budget_guard=lambda: None,
        ledger=None,
    )
    object.__setattr__(router, "next_action", next_action)
    object.__setattr__(router, "record_evidence", lambda _r: None)

    action = await router.route(_failed(_TESTS_PASS_RED))

    assert action == "accept_patch"
    assert asked == []
    assert router.held["patched_result"].status == TaskResultStatus.SUCCEEDED
    assert state.correction.accepted_repair_task_ids == {"t_qa"}
