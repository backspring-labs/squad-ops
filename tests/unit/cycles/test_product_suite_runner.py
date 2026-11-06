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
from unittest.mock import AsyncMock
from typing import Any

import pytest

from squadops.cycles.verification_normalize import normalize_task_checks
from squadops.execution.correction_runner import CorrectionRunner
from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor, _TaskOutcomeRouter
from squadops.execution.product_suite import (
    PRODUCT_RUNNER,
    PRODUCT_SUITE_KEY,
    judge_on_product_runner,
    rejudgeable,
)
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

    def __init__(
        self, exits=None, readings=None, *, raises=False, output="", unavailable=None
    ) -> None:
        self.exits, self.readings, self.raises = exits or {}, readings or {}, raises
        self.output, self.unavailable = output, unavailable
        self.seeded: dict[str, str] = {}
        self.commands: list[dict[str, Any]] = []
        self.released: list[str] = []

    async def release_workspace(self, workspace_id: str) -> None:
        self.released.append(workspace_id)

    async def seed_workspace(self, workspace_id, files, *, origin, executable=(), **_):
        """Refuses a path as the sandbox does (``workspace._safe_relpath``): a derived-state name,
        a ``package-lock.json``, is content only in a checkout's tracked set (X-2, #2900)."""
        from squadops.sandbox.models import RevisionOrigin
        from squadops.sandbox.workspace import _safe_relpath

        self.origin = origin
        tracked = None if origin in RevisionOrigin.TRACKED_TREE else ()
        for path in files:
            _safe_relpath(path, tracked=tracked)
        self.seeded, self.executable = dict(files), frozenset(executable)
        return SimpleNamespace(revision_id="rev_1")

    async def apply_workspace_patch(self, *, base, files, **_):
        """``seeded`` is the tree the command runs on: the seed with the patch over it. A patch
        may name a derived-state path only when its base holds it, as the sandbox's does."""
        from squadops.sandbox.workspace import _safe_relpath

        for path in files:
            _safe_relpath(path, tracked=self.seeded)
        self.patched = dict(files)
        self.seeded = {**self.seeded, **files}
        return SimpleNamespace(new_revision_id="rev_2")

    async def run_declared_command(self, *, revision, command, working_dir, setup, findings_reader):
        if self.raises:
            raise RuntimeError("sandbox down")
        path = command[-1]
        self.commands.append({"command": command, "setup": setup, "reader": findings_reader})
        if self.unavailable is not None:
            return SimpleNamespace(
                ran=False,
                outcome="unavailable",
                unavailable_reason=self.unavailable,
                exit_code=None,
                findings=None,
            )
        return SimpleNamespace(
            ran=True,
            outcome="exited",
            stdout_tail=self.output,
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
    project_id="prj_x",
    source_context=SimpleNamespace(development_configuration_revision=3, pinned_commit="c0ffee"),
)


class _Repository:
    """The managed clone: ``files`` at the pin, or a refusal when ``raises``. Empty by default,
    so a test that isn't about the clone sees only the run's own tree, as before #2900."""

    def __init__(self, files: dict[str, bytes] | None = None, *, raises: bool = False) -> None:
        self.files, self.raises = files or {}, raises
        self.read: list[tuple[str, str]] = []

    async def tree_at(self, project_id: str, commit: str):
        self.read.append((project_id, commit))
        if self.raises:
            raise RuntimeError("the clone does not hold c0ffee")
        return SimpleNamespace(files=dict(self.files), executable=frozenset({"bin/run"}))


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
        repository=_Repository(),
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

    judged = await _judge(result, sandbox, profile=_Profile(api, worker))

    assert judged is not None and judged.status == TaskResultStatus.FAILED
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
async def test_a_file_whose_tests_were_not_read_as_passed_stays_failed_on_the_products_reading(
    exits, reading
):
    """The runner ran it and it didn't pass: the task stays failed, and that run is the evidence
    (#2913). Exit zero is not a pass (review P2: ``unittest discover``), and it isn't the image's
    word either."""
    sandbox = _Sandbox(exits=exits, readings={"tests/test_t1.py": reading})

    judged = await _judge(_failed(_TESTS_PASS_RED), sandbox)

    assert judged is not None and judged.status == TaskResultStatus.FAILED
    row = next(
        r for r in judged.outputs["validation_result"]["checks"] if r["check"] == "tests_pass"
    )
    assert (row["judged_on"], row["passed"]) == (PRODUCT_RUNNER, False)


_IMAGE_LACKS_A_DEPENDENCY = {
    "check": "tests_pass",
    "passed": False,
    "exit_code": 4,
    "runner": "pytest",
    "reason": "exit_code 4: usage error",
    "stderr_tail": "ModuleNotFoundError: No module named 'slugify'",
}


async def test_the_image_failing_on_a_dependency_it_lacks_never_reaches_the_analysis():
    """#2913, seen live on Shelfnote's SN-6. The image died importing a dependency the product
    declares (exit 4); the product's runner ran the suite and read a real failure. Bug caught: the
    failed run left the agent's result, so the analysis read an environment problem, the repair
    had nothing to fix, and the real failure never reached either, twice. The image's row is kept
    apart, disclosed."""
    sandbox = _Sandbox(
        exits={"tests/test_t1.py": 1},
        readings={"tests/test_t1.py": _reading(0, 1)},
        output="AssertionError: PATCH b1 reading: 400",
    )

    judged = await _judge(_failed(_IMAGE_LACKS_A_DEPENDENCY), sandbox)

    assert judged is not None and judged.status == TaskResultStatus.FAILED
    outputs = judged.outputs
    row = next(r for r in outputs["validation_result"]["checks"] if r["check"] == "tests_pass")
    assert (row["judged_on"], row["exit_code"]) == (PRODUCT_RUNNER, 1)
    assert "slugify" not in repr(row) and "slugify" not in outputs["summary"]
    assert "400" in repr(outputs[PRODUCT_SUITE_KEY])
    assert outputs["test_result"]["judged_on"] == PRODUCT_RUNNER
    assert outputs["agent_tests_pass_row"]["exit_code"] == 4


async def test_a_run_that_never_exited_leaves_the_agents_result():
    """Bug caught: a sandbox that couldn't run the command replacing a real reading with nothing:
    a run that didn't exit is no reading of the product."""
    sandbox = _Sandbox(unavailable="no capacity")

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


async def test_a_sandbox_failure_leaves_the_agents_result_and_releases_the_workspace():
    """#2845: the spike's round 2 failed its run on a sandbox refusal inside the judgement. Bug
    caught: a judgement that can't run failing the run instead of leaving the agent's result."""
    sandbox = _Sandbox(raises=True)
    assert await _judge(_failed(_TESTS_PASS_RED), sandbox) is None
    assert sandbox.released == ["suite-run_1-t_qa", "suite-run_1-t_qa"]


def test_the_suite_workspace_id_is_one_the_sandbox_accepts(tmp_path):
    """#2845, against the real workspace store's check: the spike's id carried the task id's ``.``
    (``task-run_4af68354-m001-qa.test``) and the sandbox refused it."""
    from squadops.execution.product_suite import suite_workspace_prefix
    from squadops.sandbox.workspace import WorkspaceStore

    workspace_id = suite_workspace_prefix("run_4af68354f83c", "task-run_4af68354-m001-qa.test")
    WorkspaceStore(tmp_path)._cycle_dir(workspace_id)  # raises WorkspaceStoreError if refused
    assert workspace_id == "suite-run_4af68354f83c-task-run_4af68354-m001-qa-test"


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
    executor._source_repository = _Repository()
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


# --- #2877: the qa image couldn't run the suite ---------------------------------------------

_NOT_RUN_WORDS = "no pytest-discoverable test files — backend tests must be Python files"
_TESTS_PASS_NOT_RUN = {
    "check": "tests_pass",
    "passed": False,
    "executed": False,
    "exit_code": -1,
    "tests_passed": False,
    "suite_broken": True,
    "runner": "pytest",
}
_UNDEFINED_VI = {
    "check": "acceptance:undefined_names",
    "status": "failed",
    "passed": False,
    "reason": "undefined name(s): vi (line 9)",
}
_VITEST_FILE = "test/criterion_T1.test.js"
_VITEST = _Runner(name="vitest", root="test/", argv=("npx", "vitest", "run"), test_ids="vitest")
_RED_KEY = f"FAILED {_VITEST_FILE} > steers toward the objective"


def _not_run(*others: dict[str, Any]) -> TaskResult:
    result = _failed(_TESTS_PASS_NOT_RUN, *others, tests=(_VITEST_FILE,))
    outputs = dict(result.outputs)
    outputs["artifacts"] = [
        {**a, "content": f"tests not run: {_NOT_RUN_WORDS}"} if a["type"] == "test_report" else a
        for a in outputs["artifacts"]
    ]
    outputs["summary"] = f"[qa] Generated 1 test file(s), tests not run: {_NOT_RUN_WORDS}"
    outputs["validation_result"] = {
        **outputs["validation_result"],
        "summary": f"tests not run: {_NOT_RUN_WORDS}",
    }
    return TaskResult(
        task_id=result.task_id,
        status=result.status,
        error=f"tests not run: {_NOT_RUN_WORDS}",
        outputs=outputs,
    )


def _vitest_reading(passed: int, collected: int, *failing: str) -> dict[str, Any]:
    return {
        "reader": "vitest",
        "version": 1,
        "readable": True,
        "passed": passed,
        "collected": collected,
        "counts": {k: 1 for k in failing},
    }


@pytest.mark.parametrize(
    ("others", "exit_code", "reading", "status", "tests_pass_passed", "still_failing"),
    [
        # The cycle's shape: a real defect beside the image's "not run". The suite's own result,
        # failing, replaces the image's; the defect stays.
        (
            (_UNDEFINED_VI,),
            1,
            _vitest_reading(0, 1, _RED_KEY),
            TaskResultStatus.FAILED,
            False,
            True,
        ),
        # The suite passes on the product's runner, and the defect still fails the task.
        ((_UNDEFINED_VI,), 0, _vitest_reading(1, 1), TaskResultStatus.FAILED, True, True),
        # Nothing else failed and the suite fails there: re-read, not judged.
        ((), 1, _vitest_reading(0, 1, _RED_KEY), TaskResultStatus.FAILED, False, False),
        # Nothing else failed and it passes there: judged passed, as #2835 already did.
        ((), 0, _vitest_reading(1, 1), TaskResultStatus.SUCCEEDED, True, False),
    ],
    ids=["defect-and-red", "defect-and-green", "red-only", "green-only"],
)
async def test_a_suite_the_qa_image_could_not_run_is_read_on_the_products_runner(
    others, exit_code, reading, status, tests_pass_passed, still_failing
):
    sandbox = _Sandbox(exits={_VITEST_FILE: exit_code}, readings={_VITEST_FILE: reading})
    judged = await _judge(_not_run(*others), sandbox, profile=_Profile(_VITEST))

    assert judged is not None and judged.status == status
    assert sandbox.commands[0]["command"] == ("npx", "vitest", "run", _VITEST_FILE)
    rows = {r["check"]: r for r in judged.outputs["validation_result"]["checks"]}
    assert rows["tests_pass"]["judged_on"] == PRODUCT_RUNNER
    assert rows["tests_pass"]["passed"] is tests_pass_passed
    assert ("acceptance:undefined_names" in rows) is still_failing
    if not tests_pass_passed:
        assert rows["tests_pass"]["failing_tests"] == [f"{_VITEST_FILE}::{_RED_KEY}"]
        assert rows["tests_pass"]["exit_code"] == 1


async def test_the_analysis_reads_the_products_runner_and_never_the_images_words():
    """Bug caught (cyc_0fbf09b7b96e): the image's "must be Python files" reached the failure
    analysis through the row, the summary, the error and the test report, and the analysis told
    the repair to rename a vitest suite to pytest. The image's reading is kept, apart."""
    from squadops.cycles.failure_evidence import build_failure_evidence

    sandbox = _Sandbox(
        exits={_VITEST_FILE: 1}, readings={_VITEST_FILE: _vitest_reading(0, 1, _RED_KEY)}
    )
    judged = await _judge(_not_run(_UNDEFINED_VI), sandbox, profile=_Profile(_VITEST))

    evidence = build_failure_evidence(_envelope(_INPUTS), judged, prior_plan_deltas_count=0)
    assert "pytest" not in repr(evidence)
    assert judged.outputs["agent_tests_pass_row"] == _TESTS_PASS_NOT_RUN
    assert judged.error == (
        "the suite failed on the product's runner (vitest): "
        f"{_VITEST_FILE}; also failing: acceptance:undefined_names"
    )


@pytest.mark.parametrize(
    ("tests_pass", "profile"),
    [
        # The image ran the suite and it failed beside another check: the agent's result stands,
        # as before #2877.
        ({**_TESTS_PASS_NOT_RUN, "executed": True, "exit_code": 1}, _Profile(_VITEST)),
        # No runner of the product's holds the file: nothing can read it, so nothing runs.
        (_TESTS_PASS_NOT_RUN, _Profile(_Runner(root="spec/"))),
    ],
    ids=["image-ran-it", "no-runner-holds-it"],
)
async def test_a_suite_the_image_ran_or_no_runner_holds_is_not_reread(tests_pass, profile):
    sandbox = _Sandbox()
    result = _failed(tests_pass, _UNDEFINED_VI, tests=(_VITEST_FILE,))
    assert await _judge(result, sandbox, profile=profile) is None
    assert sandbox.commands == []


async def test_the_router_hands_the_correction_loop_the_products_reading():
    """Wiring, #2877: enters at ``_TaskOutcomeRouter.route``, as cyc_0fbf09b7b96e's failed
    ``qa.test`` did, and asserts the correction loop is asked about the product runner's reading,
    and the patch is never accepted on it."""
    executor = _executor()
    executor._sandbox = _Sandbox(
        exits={_VITEST_FILE: 1}, readings={_VITEST_FILE: _vitest_reading(0, 1, _RED_KEY)}
    )
    executor._derived_profile_for = _profile_of(_Profile(_VITEST))

    async def admit(result, *_a, **_k):
        return result

    executor._admit_failed_emission = admit
    asked: list[TaskResult] = []

    async def next_action(result, *_args):
        asked.append(result)
        return "fail"

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

    await router.route(_not_run(_UNDEFINED_VI))

    assert len(asked) == 1
    row = next(
        r for r in asked[0].outputs["validation_result"]["checks"] if r["check"] == "tests_pass"
    )
    assert row["judged_on"] == PRODUCT_RUNNER and row["executed"] is True
    assert router.held["result"] is asked[0]
    assert state.correction.accepted_repair_task_ids == set()


# #2881: a dev repair's retest. Its ``retest_files`` are the repaired source, which no runner holds,
# so before this the product's runner judged nothing (``runs=no runner holds a test``, four times in
# 2.5.1's validation Campaign ``cmp_5d8e8b9de6db``) and the qa image's reading stood.

_REPAIRED = "import plugins  # repaired\n"


def _dev_repair_retest(*, carries_suite: bool = True):
    """The retest a dev repair of ``app/main.py`` sends, built by the correction runner from the
    failed task's result, whose suite is ``tests/test_t1.py``."""
    executor = _executor()
    runner = object.__new__(CorrectionRunner)
    runner._judge_suite = lambda result, envelope, cycle, run_id: (
        executor._judged_on_product_runner(result, envelope, envelope, cycle, run_id)
    )
    dispatched: list[TaskEnvelope] = []

    async def dispatch(envelope, *_a, **_k):
        dispatched.append(envelope)
        # The qa image can't run the product's suite: its own reading is a failure.
        return _failed(_TESTS_PASS_RED, tests=())

    runner._dispatch_protocol_step = dispatch
    cycle = SimpleNamespace(**vars(_CYCLE), cycle_id="cyc_x", prd_ref=None)
    failed = _failed(_TESTS_PASS_RED)
    return (
        executor,
        dispatched,
        runner.reexecute_repaired_suite(
            "run_1",
            cycle,
            _envelope(_INPUTS),
            [{"name": "app/main.py", "content": _REPAIRED, "type": "source"}],
            1,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
            profile=squad(),
            failed_suite=failed.outputs["artifacts"] if carries_suite else (),
        ),
    )


async def test_a_dev_repairs_retest_runs_the_failed_suite_against_the_repaired_source():
    """Wiring, entering at ``CorrectionRunner.reexecute_repaired_suite`` with the executor's own
    judgement. Bug caught: the repaired ``app/main.py`` read as the suite, held by no runner, so
    the product's runner never judged the repair and the qa image's failure stood."""
    executor, dispatched, retest = _dev_repair_retest()
    result = await retest

    assert [c["command"] for c in executor._sandbox.commands] == [
        ("pytest", "-q", "tests/test_t1.py")
    ]
    # The suite ran against the repaired code, not the tree the failed task saw.
    assert executor._sandbox.seeded["app/main.py"] == _REPAIRED
    assert result.status == TaskResultStatus.SUCCEEDED
    # The qa image's own retest still gets the repaired files as it always has.
    assert dispatched[0].inputs["retest_files"] == [
        {"filename": "app/main.py", "content": _REPAIRED}
    ]


async def test_a_retest_carrying_no_suite_of_its_own_is_not_judged():
    """An envelope from before #2881 has only the repaired source. Bug caught: a guess at the
    suite (every test in the tree, say) judged in its place. The agent's reading stands."""
    executor, _, retest = _dev_repair_retest(carries_suite=False)
    result = await retest

    assert executor._sandbox.commands == []
    assert result.status == TaskResultStatus.FAILED


@pytest.mark.parametrize(
    ("patched", "expected_tests", "expected_overlay"),
    [
        # A qa repair: the repaired test replaces its namesake.
        ({"tests/test_t1.py": "fixed"}, {"tests/test_t1.py": "fixed"}, {}),
        # A repair that adds a test file and changes source: both reach the run.
        (
            {"tests/test_t2.py": "new", "app/main.py": "src"},
            {"tests/test_t1.py": "old", "tests/test_t2.py": "new"},
            {"app/main.py": "src"},
        ),
    ],
    ids=["qa repair", "dev and qa repair"],
)
def test_a_retests_suite_is_the_failed_suite_with_the_repair_laid_in(
    patched, expected_tests, expected_overlay
):
    """Bug caught: a repaired test run beside its stale namesake, or a repaired source file
    handed to the runner as a test instead of placed on the tree."""
    from squadops.execution.product_suite import RETEST_SUITE_KEY, suite_under_judgement

    inputs = {
        "retest_files": [{"filename": p, "content": c} for p, c in patched.items()],
        RETEST_SUITE_KEY: [{"filename": "tests/test_t1.py", "content": "old"}],
    }

    assert suite_under_judgement(inputs, {}, _Profile()) == (expected_tests, expected_overlay)


async def test_patch_acceptance_hands_the_retest_the_failed_tasks_suite():
    """Wiring, from ``PatchAcceptance``, the caller the live correction loop uses. Bug caught: the
    retest dispatched without the failed task's suite, so the product's runner has nothing to
    judge after any dev repair."""
    from squadops.execution.patch_acceptance import PatchAcceptance, _PatchSubject

    handed: dict[str, Any] = {}

    async def retest(*_args, **kwargs):
        handed.update(kwargs)

    acceptance = PatchAcceptance(
        reexecute_repaired_suite=retest,
        enforce_frozen_ownership=lambda *a, **k: ([], []),
        emit_integrity_evidence=lambda *a: None,
        enforce_compliance_budget=lambda *a, **k: None,
        read_repaired_suite_on_head=AsyncMock(return_value=None),
    )
    failed = _failed(_TESTS_PASS_RED)
    await acceptance._retest_patched_suite(
        _envelope(_INPUTS),
        failed,
        _PatchSubject(
            resolved_config={},
            criteria=[],
            patched_artifacts=[{"name": "app/main.py", "content": _REPAIRED, "type": "source"}],
            workspace_files={},
            file_owned=[],
        ),
        run_id="run_1",
        cycle=SimpleNamespace(**vars(_CYCLE), cycle_id="cyc_x", prd_ref=None),
        correction_attempts=1,
        round_seq=0,
        prior_outputs=None,
        all_artifact_refs=None,
        stored_artifacts=None,
        completed_task_ids=None,
        plan_delta_refs=None,
        profile=squad(),
        flow_run_id=None,
        enriched_envelope=None,
        budget_guard=None,
        repair_rejection_carry={},
    )

    assert handed["failed_suite"] == failed.outputs["artifacts"]


# #2900: a run's artifacts hold back a generated lockfile (``manifest.held_back``), so a tree built
# from them alone has no ``package-lock.json``, and an npm product's setup (``npm ci``) refused it:
# ``unexecuted: setup_failed`` on every run of battle-trainer's suite (cmp_c59db96e4a87).

_LOCK = b'{"lockfileVersion": 3}\n'
_CLONE = {
    "package.json": b'{"name": "p"}\n',
    "package-lock.json": _LOCK,
    "app/main.py": b"import plugins  # the pin's\n",
    "app/logo.png": b"\x89PNG\r\n\x1a\n",
    "bin/run": b"#!/bin/sh\n",
    "tests/test_existing.py": b"def test_old(): ...\n",
}


async def test_the_products_suite_runs_on_the_pinned_tree_with_its_held_back_lockfile():
    """Wiring, entering at the executor's ``_judged_on_product_runner`` as a live failed
    ``qa.test`` does. Bug caught: the suite's tree built from the run's artifacts alone, so the
    lockfile they hold back never reached the sandbox and the product's setup failed every run."""
    executor = _executor()
    executor._source_repository = _Repository(_CLONE)
    envelope = _envelope(_INPUTS)

    judged = await executor._judged_on_product_runner(
        _failed(_TESTS_PASS_RED), envelope, envelope, _CYCLE, "run_1"
    )

    assert executor._source_repository.read == [("prj_x", "c0ffee")]
    sandbox = executor._sandbox
    # The pin is seeded as the checkout it is, so the sandbox takes its tracked lockfile, which
    # its derived-state rule refuses from any other origin; the run's tree is a patch on it.
    assert sandbox.origin == "git_checkout"
    assert "package-lock.json" not in sandbox.patched
    assert sandbox.executable == {"bin/run"}
    seeded = sandbox.seeded
    # What the run's artifacts hold back comes from the clone, byte for byte.
    assert seeded["package-lock.json"] == _LOCK
    assert seeded["app/logo.png"] == _CLONE["app/logo.png"]
    # What the run has is laid over the pin: the agent's tree, not the commit's.
    assert seeded["app/main.py"] == "import plugins\n"
    # The product's own tests stay out of the run, from the clone as from the artifacts.
    assert "tests/test_existing.py" not in seeded
    assert seeded["tests/test_t1.py"] == "def test_t(): ...\n"
    assert judged is not None and judged.status == TaskResultStatus.SUCCEEDED


async def test_a_file_the_run_removed_stays_removed_on_the_pinned_tree():
    """H.23 over H.19, entering where a live failed ``qa.test`` does. Bug caught: the tree seeded
    from the pin brings back a file an earlier task removed, so the suite is judged on a product
    the run doesn't deliver, and a test of the removal fails here and passes at delivery."""
    executor = _executor()
    executor._source_repository = _Repository(_CLONE)
    view = {**_INPUTS["source_repository"], "deleted": ["app/logo.png"]}
    envelope = _envelope({**_INPUTS, "source_repository": view})

    await executor._judged_on_product_runner(
        _failed(_TESTS_PASS_RED), envelope, envelope, _CYCLE, "run_1"
    )

    patched = executor._sandbox.patched
    assert patched["app/logo.png"] is None
    assert patched["app/main.py"] == "import plugins\n"


async def test_the_executor_hands_on_the_products_failure_in_place_of_the_images():
    """Wiring for #2913, entering at ``_judged_on_product_runner`` as a live failed ``qa.test``
    does. Bug caught: a seam-level reading the executor drops, so the router still hands the
    correction loop the image's result."""
    executor = _executor()
    executor._source_repository = _Repository(_CLONE)
    executor._sandbox = _Sandbox(
        exits={"tests/test_t1.py": 1}, readings={"tests/test_t1.py": _reading(0, 1)}
    )
    envelope = _envelope(_INPUTS)

    judged = await executor._judged_on_product_runner(
        _failed(_IMAGE_LACKS_A_DEPENDENCY), envelope, envelope, _CYCLE, "run_1"
    )

    assert judged is not None and judged.status == TaskResultStatus.FAILED
    assert judged.outputs["test_result"]["judged_on"] == PRODUCT_RUNNER
    assert judged.outputs["agent_tests_pass_row"]["exit_code"] == 4


@pytest.mark.parametrize(
    "repository", [None, _Repository(raises=True)], ids=["no repository", "clone refuses the pin"]
)
async def test_no_readable_tree_at_the_pin_judges_nothing(repository):
    """Bug caught: a fallback to the artifacts' tree, which lacks the held-back lockfile and so
    reads ``setup_failed`` in place of the suite's result. The agent's result stands, as for every
    judgement that can't run, and the sandbox is never asked."""
    executor = _executor()
    executor._source_repository = repository
    envelope = _envelope(_INPUTS)

    judged = await executor._judged_on_product_runner(
        _failed(_TESTS_PASS_RED), envelope, envelope, _CYCLE, "run_1"
    )

    assert judged is None
    assert executor._sandbox.commands == []
