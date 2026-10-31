"""#2818: a product's ``qa.test`` failing only ``tests_pass`` in the qa image is judged on the
product's own runner, after its configured setup.

Bug caught: a product whose code needs a dependency the qa image lacks (2.5's ``z_continuum`` and
``tomli``) can never pass a criterion in-cycle, however correct the build, because the suite only
ever runs where the product's install never happened. And, from the outside review of PR #2835: a
judged pass the verification normalizer never sees (it reads ``test_result``), two runners of one
tool collapsed into one, an exit zero that ran nothing, and a repaired suite's retest left to the
qa image.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from squadops.cycles.verification_normalize import normalize_task_checks
from squadops.execution.correction_runner import CorrectionRunner
from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor, _TaskOutcomeRouter
from squadops.execution.product_suite import PRODUCT_RUNNER, judge_on_product_runner, rejudgeable
from squadops.tasks.models import TaskEnvelope, TaskResult, TaskResultStatus
from tests.unit.cycles._product_increment import squad

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
_AGENT_TEST_RESULT = {
    "executed": True,
    "exit_code": 1,
    "tests_passed": False,
    "source_file_count": 2,
}


def _failed(*rows: dict[str, Any], tests=("tests/test_t1.py",)) -> TaskResult:
    return TaskResult(
        task_id="t_qa",
        status=TaskResultStatus.FAILED,
        error="suite failed",
        outputs={
            "artifacts": [
                *({"name": t, "content": "def test_t(): ...\n", "type": "test"} for t in tests),
                {"name": "test_report.md", "content": "red", "type": "test_report"},
            ],
            "test_result": dict(_AGENT_TEST_RESULT),
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
_AUTHENTICITY_RED = {"check": "no_stub_fallback_tests", "passed": False}
_SKIPPED_TYPED = {"check": "acceptance:function_defined", "status": "skipped", "passed": False}
_IMPORTS_RED = {"check": "acceptance:module_imports", "status": "failed", "passed": False}


def _reading(passed: int, collected: int) -> dict[str, Any]:
    return {
        "reader": "pytest",
        "version": 1,
        "readable": True,
        "passed": passed,
        "collected": collected,
    }


class _Sandbox:
    """Answers each command by the file it names: ``exits[path]`` and ``readings[path]``."""

    def __init__(self, exits=None, readings=None, *, raises: bool = False) -> None:
        self.exits, self.readings, self.raises = exits or {}, readings or {}, raises
        self.seeded: dict[str, str] = {}
        self.commands: list[dict[str, Any]] = []
        self.released: list[str] = []

    async def release_workspace(self, workspace_id: str) -> None:
        self.released.append(workspace_id)

    async def seed_workspace(self, workspace_id, files, *, origin, **_):
        self.seeded = dict(files)
        return SimpleNamespace(revision_id="rev_1")

    async def run_declared_command(self, *, revision, command, working_dir, setup, findings_reader):
        if self.raises:
            raise RuntimeError("sandbox down")
        path = command[-1]
        self.commands.append({"command": command, "setup": setup, "reader": findings_reader})
        return SimpleNamespace(
            ran=True,
            outcome="exited",
            exit_code=self.exits.get(path, 0),
            findings=self.readings.get(path, _reading(1, 1)),
        )


class _Runner:
    def __init__(self, name="pytest", root="tests/", argv=("pytest", "-q"), test_ids="pytest"):
        self.runner, self.root, self.test_ids = name, root, test_ids
        self.single_file_argv = (*argv, "{path}") if argv else None
        self.suite_argv = argv

    def holds(self, path: str) -> bool:
        return path.startswith(self.root)


class _Profile:
    def __init__(self, *runners: _Runner) -> None:
        self.runners = runners or (_Runner(),)

    def runner_for(self, path: str):
        return next((r for r in self.runners if r.holds(path)), None)


_CYCLE = SimpleNamespace(
    project_id="prj_x", source_context=SimpleNamespace(development_configuration_revision=3)
)
_PROJECTS = SimpleNamespace(
    get_development_configuration=lambda *_: _async(
        SimpleNamespace(commands=SimpleNamespace(working_directory=".", check_setup=_SETUP))
    )
)


async def _async(value):
    return value


def _profile_of(profile: _Profile):
    async def read(_cycle):
        return profile

    return read


async def _judge(result, sandbox, *, profile=None, task_type="qa.test", inputs=_INPUTS):
    return await judge_on_product_runner(
        result,
        task_type=task_type,
        task_id="t_qa",
        inputs=inputs,
        cycle=_CYCLE,
        run_id="run_1",
        sandbox=sandbox,
        projects=_PROJECTS,
        read_profile=_profile_of(profile or _Profile()),
    )


@pytest.mark.parametrize(
    ("task_type", "inputs", "rows", "expected"),
    [
        ("qa.test", _INPUTS, (_TESTS_PASS_RED, _OTHER_GREEN), True),
        # Another failing check is the agent's to report: the product's runner can't clear it.
        ("qa.test", _INPUTS, (_TESTS_PASS_RED, _AUTHENTICITY_RED), False),
        # #2838, the spike's shape: a skipped typed row reads ``passed: False`` and isn't a failure,
        # and the import check fails in the qa image for the suite's own reason.
        ("qa.test", _INPUTS, (_TESTS_PASS_RED, _SKIPPED_TYPED, _IMPORTS_RED), True),
        # A sample application's suite already runs where its stack's toolchain lives.
        ("qa.test", {"artifact_contents": {}}, (_TESTS_PASS_RED,), False),
        ("development.develop", _INPUTS, (_TESTS_PASS_RED,), False),
    ],
)
def test_only_a_products_suite_failing_only_tests_pass_is_rejudged(
    task_type, inputs, rows, expected
):
    assert rejudgeable(task_type, inputs, _failed(*rows)) is expected


async def test_a_pass_on_the_products_runner_is_what_verification_reads():
    """Review P1: the normalizer synthesizes ``tests_pass`` from ``test_result``, so a judged pass
    that left the agent's ``test_result`` still read failed."""
    sandbox = _Sandbox()
    judged = await _judge(_failed(_TESTS_PASS_RED, _OTHER_GREEN), sandbox)

    assert judged is not None and judged.status == TaskResultStatus.SUCCEEDED
    # Each emitted file on its runner's single-file command, read by its test-id reader, after
    # the product's own install, on the agent's tree without the product's own tests.
    assert sandbox.commands == [
        {"command": ("pytest", "-q", "tests/test_t1.py"), "setup": _SETUP, "reader": "pytest"}
    ]
    assert set(sandbox.seeded) == {"app/main.py", "app/plugin.toml", "tests/test_t1.py"}
    assert judged.outputs["test_result"]["tests_passed"] is True
    assert judged.outputs["agent_test_result"] == _AGENT_TEST_RESULT
    row = judged.outputs["validation_result"]["checks"][0]
    assert row["judged_on"] == PRODUCT_RUNNER and row["agent_reading"] == _TESTS_PASS_RED
    normalized = {r.check_id: r.status for r in normalize_task_checks(judged.outputs)}
    assert normalized["tests_pass"] == "passed"
    assert sandbox.released == ["suite-run_1-t_qa", "suite-run_1-t_qa"]


async def test_two_runners_of_one_tool_each_run_their_own_files():
    """Review P2: keyed by the tool's name, the second pytest runner never ran, and its failure
    read as a pass."""
    api, worker = (
        _Runner(root="tests/", argv=("pytest",)),
        _Runner(root="worker/", argv=("pytest", "-c", "w.ini")),
    )
    sandbox = _Sandbox(exits={"worker/test_w.py": 1})
    result = _failed(_TESTS_PASS_RED, tests=("tests/test_t1.py", "worker/test_w.py"))

    assert await _judge(result, sandbox, profile=_Profile(api, worker)) is None
    assert [c["command"] for c in sandbox.commands] == [
        ("pytest", "tests/test_t1.py"),
        ("pytest", "-c", "w.ini", "worker/test_w.py"),
    ]


@pytest.mark.parametrize(
    ("exits", "reading"),
    [
        ({"tests/test_t1.py": 1}, _reading(0, 1)),  # the file's test failed
        ({}, _reading(0, 0)),  # exit zero, nothing ran (review P2: ``unittest discover``)
        ({}, _reading(1, 2)),  # one passed, one not: collected but not all passed
    ],
    ids=["failed", "ran-nothing", "not-all-passed"],
)
async def test_a_file_whose_tests_were_not_read_as_passed_leaves_the_agents_result(exits, reading):
    sandbox = _Sandbox(exits=exits, readings={"tests/test_t1.py": reading})
    assert await _judge(_failed(_TESTS_PASS_RED), sandbox) is None


@pytest.mark.parametrize(
    "runner",
    [_Runner(root="spec/"), _Runner(argv=()), _Runner(test_ids=None)],
    ids=["no-runner-holds-it", "not-scopable-to-a-file", "no-test-id-reader"],
)
async def test_a_file_the_product_gives_no_way_to_read_is_not_judged_and_runs_nothing(runner):
    sandbox = _Sandbox()
    assert await _judge(_failed(_TESTS_PASS_RED), sandbox, profile=_Profile(runner)) is None
    assert sandbox.commands == []


async def test_the_workspace_is_released_when_the_run_raises():
    sandbox = _Sandbox(raises=True)
    with pytest.raises(RuntimeError):
        await _judge(_failed(_TESTS_PASS_RED), sandbox)
    assert sandbox.released == ["suite-run_1-t_qa", "suite-run_1-t_qa"]


def _envelope(inputs) -> TaskEnvelope:
    return TaskEnvelope(
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
        inputs=inputs,
    )


def _executor() -> DispatchedFlowExecutor:
    executor = object.__new__(DispatchedFlowExecutor)
    executor._sandbox = _Sandbox()
    executor._project_registry = _PROJECTS
    executor._derived_profile_for = _profile_of(_Profile())
    return executor


async def test_the_router_accepts_a_product_suite_judged_passed_without_routing_a_correction():
    """Wiring: enters at the dispatcher's ``handle_task_outcome`` (``_TaskOutcomeRouter.route``),
    as a live cycle's failed ``qa.test`` does, and asserts the correction loop is never asked."""
    executor = _executor()

    async def admit(result, *_a, **_k):
        return result

    executor._admit_failed_emission = admit
    asked: list[Any] = []

    async def next_action(*args):
        asked.append(args)
        return "continue"

    envelope = _envelope(_INPUTS)
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


async def test_a_repaired_suites_retest_is_judged_on_the_products_runner():
    """Review P2, wiring: enters at ``CorrectionRunner.reexecute_repaired_suite``, the retest
    patch acceptance reads, with the judgement the executor hands the runner. The retest's suite
    is the repaired files it carries, and its pass is what patch acceptance reads."""
    executor = _executor()
    runner = object.__new__(CorrectionRunner)
    runner._judge_suite = lambda result, envelope, cycle, run_id: (
        executor._judged_on_product_runner(result, envelope, envelope, cycle, run_id)
    )
    dispatched: list[TaskEnvelope] = []

    async def dispatch(envelope, *_a, **_k):
        dispatched.append(envelope)
        return _failed(_TESTS_PASS_RED, tests=())

    runner._dispatch_protocol_step = dispatch
    cycle = SimpleNamespace(**vars(_CYCLE), cycle_id="cyc_x", prd_ref=None)
    result = await runner.reexecute_repaired_suite(
        "run_1",
        cycle,
        _envelope(_INPUTS),
        [{"name": "tests/test_t1.py", "content": "def test_t(): ...\n", "type": "test"}],
        1,
        prior_outputs={},
        all_artifact_refs=[],
        stored_artifacts=[],
        completed_task_ids=[],
        plan_delta_refs=[],
        profile=squad(),
    )

    assert result.status == TaskResultStatus.SUCCEEDED
    assert result.outputs["test_result"]["tests_passed"] is True
    assert executor._sandbox.commands[0]["command"] == ("pytest", "-q", "tests/test_t1.py")


async def test_the_import_check_that_failed_in_the_qa_image_is_recorded_not_executed_not_passed():
    """#2838: the spike's ``acceptance:module_imports`` failed in the qa image beside ``tests_pass``.
    A pass on the product's runner neither credits it nor leaves it failing: it reads not executed
    in a valid environment, with the agent's row kept."""
    result = _failed(_TESTS_PASS_RED, _SKIPPED_TYPED, _IMPORTS_RED)
    judged = await _judge(result, _Sandbox())

    assert judged is not None and judged.status == TaskResultStatus.SUCCEEDED
    rows = {r["check"]: r for r in judged.outputs["validation_result"]["checks"]}
    assert rows["acceptance:module_imports"]["status"] == "skipped"
    assert "passed" not in rows["acceptance:module_imports"]
    assert rows["acceptance:module_imports"]["agent_reading"] == _IMPORTS_RED
    statuses = {r.check_id: r.status for r in normalize_task_checks(judged.outputs)}
    assert statuses["tests_pass"] == "passed"
    assert statuses.get("acceptance:module_imports") != "failed"


async def test_a_product_suite_not_rejudged_says_why_in_the_log(caplog):
    """#2838: the spike's miss left no line saying why; now the reason is logged."""
    caplog.set_level("INFO", logger="squadops.execution.product_suite")
    assert await _judge(_failed(_TESTS_PASS_RED, _AUTHENTICITY_RED), _Sandbox()) is None
    assert "not re-judged: other checks failed: ['no_stub_fallback_tests']" in caplog.text
