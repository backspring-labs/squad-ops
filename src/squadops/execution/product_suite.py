"""A repository-backed product's in-cycle suite, judged on the product's own runner (#2818).

A product's ``qa.test`` suite runs first in the qa agent's container (``run_build_validation``),
where only the image's packages are installed. A product whose code needs anything else, a
dependency its configuration installs, fails there however correct the build: 2.5's
``z_continuum`` read 0 plugins because ``tomli`` wasn't in the image, while the product's own
runner, after its configured setup, passed the same suite.

So when a product's ``qa.test`` fails and ``tests_pass`` is its only failing check, the runtime
runs the same suite again where acceptance and the baseline run a product's tests: in the sandbox,
on the product's runner, after the Development Configuration's install and build steps
(``RunnerSetup``, SIP-0109 §24bv point 3, H.6). That run decides the check. If it passes, the task
is judged passed on it, and the agent's run is kept beside it as a disclosed reading. If it fails,
or can't run, the agent's result stands and the correction loop sees it as before.

The tree is the one the agent ran: ``qa_run_tree.suite_run_tree`` over the dispatched inputs, the
product's non-test files, with the task's emitted test files beside it. A sample application's run
is never re-judged: its suite already runs where its stack's toolchain lives.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Mapping
from typing import Any

from squadops.campaigns.runner_acceptance import RunnerSetup, single_file_argv
from squadops.capabilities.handlers.source_repository import source_backed
from squadops.capabilities.qa_run_tree import suite_run_tree
from squadops.tasks.models import TaskResult, TaskResultStatus
from squadops.tasks.task_types import authors_qa_suite

logger = logging.getLogger(__name__)

#: The ``tests_pass`` row's ``judged_on`` when the product's runner decided it.
PRODUCT_RUNNER = "product_runner"
#: Where the product runner's runs are kept on the judged result's outputs.
PRODUCT_SUITE_KEY = "product_runner_suite"
_TESTS_PASS = "tests_pass"
_SUCCESS = "success"


def suite_workspace_prefix(run_id: str, task_id: str) -> str:
    """The workspace one task's re-judged suite seeds, apart from acceptance's (``acc-``)."""
    return f"suite-{run_id}-{task_id}"


def rejudgeable(task_type: str, inputs: Mapping[str, Any], result: TaskResult) -> bool:
    """Whether a failed result is a product's ``qa.test`` whose only failing check is
    ``tests_pass``: the one case the product's runner can decide differently. Any other failing
    check (a probe, an authenticity check, a missing file) is the agent's to report, and stands."""
    if result.status == TaskResultStatus.SUCCEEDED or not authors_qa_suite(task_type):
        return False
    if not source_backed(inputs):
        return False
    checks = ((result.outputs or {}).get("validation_result") or {}).get("checks") or []
    failing = [c for c in checks if isinstance(c, Mapping) and not c.get("passed")]
    return len(failing) == 1 and failing[0].get("check") == _TESTS_PASS


def emitted_tests(inputs: Mapping[str, Any], outputs: Mapping[str, Any]) -> dict[str, str]:
    """The suite under judgement, by path: a repaired suite's retest runs its ``retest_files``
    (``CorrectionRunner.reexecute_repaired_suite``); an emission, the test files it stored."""
    retest = inputs.get("retest_files")
    if retest:
        return {str(f["filename"]): str(f.get("content") or "") for f in retest}
    return {
        str(a["name"]): str(a.get("content") or "")
        for a in outputs.get("artifacts") or []
        if isinstance(a, Mapping) and a.get("type") == "test" and a.get("name")
    }


@dataclasses.dataclass(frozen=True)
class SuiteRun:
    """One emitted test file's run on its runner's single-file command."""

    runner: str
    path: str
    argv: tuple[str, ...]
    revision_id: str | None
    exit_code: int | None
    #: How many of the file's tests the runner's test-id reader read as passed, and collected.
    tests_passed: int | None = None
    collected: int | None = None
    #: Why nothing exited, when nothing did: the sandbox's own words.
    unexecuted: str | None = None

    @property
    def passed(self) -> bool:
        """Exit zero is not enough: a runner can exit zero having run nothing (``unittest
        discover`` over a directory with no package marker). So the file's own tests must be
        read as run, at least one passed and none failed."""
        return (
            self.unexecuted is None
            and self.exit_code == 0
            and (self.tests_passed or 0) > 0
            and (self.collected is None or self.collected == self.tests_passed)
        )

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self) | {"argv": list(self.argv), "passed": self.passed}


async def run_on_product_runner(
    *,
    sandbox: Any,
    profile: Any,
    setup: RunnerSetup,
    tree: Mapping[str, str],
    tests: Mapping[str, str],
    workspace_id: str,
) -> list[SuiteRun] | None:
    """Run each of ``tests`` on its own runner's single-file command, read by that runner's
    test-id reader, on ``tree`` with ``tests`` beside it. ``None`` when a test file is held by no
    runner, or by one that can't be scoped to a file or has no test-id reader: the product names
    no way to show that file's tests ran, so nothing here can judge it."""
    # deferred (pair): squadops.sandbox imports the campaigns package at load (its API's seed plan)
    # deferred (pair): as above
    from squadops.sandbox.findings import FindingsReading
    from squadops.sandbox.models import CommandOutcome, RevisionOrigin

    planned: list[tuple[str, Any]] = []
    for path in tests:
        runner = profile.runner_for(path)
        if runner is None or runner.single_file_argv is None or not runner.test_ids:
            return None
        planned.append((path, runner))
    files = {**tree, **tests}
    runs: list[SuiteRun] = []
    await sandbox.release_workspace(workspace_id)
    try:
        revision = await sandbox.seed_workspace(
            workspace_id, files, origin=RevisionOrigin.ACCEPTANCE_ASSEMBLY
        )
        for path, runner in planned:
            argv = single_file_argv(runner, path)
            result = await sandbox.run_declared_command(
                revision=revision,
                command=argv,
                working_dir=setup.working_directory,
                setup=setup.setup,
                findings_reader=runner.test_ids,
            )
            exited = result.ran and result.outcome == CommandOutcome.EXITED
            findings = getattr(result, "findings", None)
            reading = FindingsReading.from_dict(findings) if findings else None
            readable = reading is not None and reading.readable
            runs.append(
                SuiteRun(
                    runner=runner.runner,
                    path=path,
                    argv=argv,
                    revision_id=revision.revision_id,
                    exit_code=result.exit_code if exited else None,
                    tests_passed=reading.passed if readable else None,
                    collected=reading.collected if readable else None,
                    unexecuted=None
                    if exited
                    else (
                        getattr(result, "unavailable_reason", None) or result.outcome or "not run"
                    ),
                )
            )
    finally:
        try:
            await sandbox.release_workspace(workspace_id)
        except Exception:
            logger.warning("suite workspace %s not released", workspace_id, exc_info=True)
    return runs


def judged_passed(result: TaskResult, runs: list[SuiteRun]) -> TaskResult:
    """``result`` judged passed on the product's runner: its ``tests_pass`` row reads the runner's
    runs, with the agent's row kept as ``agent_reading``, and the task succeeds."""
    outputs = dict(result.outputs or {})
    vr = dict(outputs.get("validation_result") or {})
    checks = []
    for row in vr.get("checks") or []:
        if isinstance(row, Mapping) and row.get("check") == _TESTS_PASS:
            row = {
                "check": _TESTS_PASS,
                "passed": True,
                "executed": True,
                "exit_code": 0,
                "judged_on": PRODUCT_RUNNER,
                "runner": ",".join(r.runner for r in runs),
                "agent_reading": dict(row),
            }
        checks.append(row)
    vr.update(
        passed=True,
        checks=checks,
        missing_components=[m for m in vr.get("missing_components") or [] if _TESTS_PASS not in m],
        coverage_ratio=1.0,
        summary=f"suite passed on the product's runner ({', '.join(r.runner for r in runs)})",
    )
    outputs.update(validation_result=vr, outcome_class=_SUCCESS)
    # The verification normalizer reads ``test_result``, not the row, so it is the product run's
    # now, and the agent's is kept beside it.
    agent = outputs.get("test_result")
    outputs["test_result"] = {
        "executed": True,
        "exit_code": 0,
        "tests_passed": True,
        "test_file_count": len(runs),
        "source_file_count": (agent or {}).get("source_file_count"),
        "summary": f"{sum(r.tests_passed or 0 for r in runs)} passed on the product's runner",
        "judged_on": PRODUCT_RUNNER,
    }
    if agent is not None:
        outputs["agent_test_result"] = agent
    outputs[PRODUCT_SUITE_KEY] = [r.as_dict() for r in runs]
    outputs.pop("failure_classification", None)
    return dataclasses.replace(
        result,
        status=TaskResultStatus.SUCCEEDED,
        outputs=outputs,
        error=None,
        outcome_class=_SUCCESS,
    )


async def judge_on_product_runner(
    result: TaskResult,
    *,
    task_type: str,
    task_id: str,
    inputs: Mapping[str, Any],
    cycle: Any,
    run_id: str,
    sandbox: Any,
    projects: Any,
    read_profile: Callable[[Any], Any],
) -> TaskResult | None:
    """The result judged passed on the product's runner, or ``None`` when the agent's result
    stands: not a product's ``qa.test`` failing only ``tests_pass``, no sandbox, no profile or
    configuration at the pin, a test no runner holds, or a run that didn't pass."""
    if sandbox is None or not rejudgeable(task_type, inputs, result):
        return None
    context = getattr(cycle, "source_context", None)
    profile = await read_profile(cycle)
    if context is None or profile is None:
        return None
    configuration = await projects.get_development_configuration(
        cycle.project_id, context.development_configuration_revision
    )
    tests = emitted_tests(inputs, result.outputs or {})
    if configuration is None or not tests:
        return None
    runs = await run_on_product_runner(
        sandbox=sandbox,
        profile=profile,
        setup=RunnerSetup.of(configuration.commands),
        tree=suite_run_tree(inputs),
        tests=tests,
        workspace_id=suite_workspace_prefix(run_id, task_id),
    )
    logger.info(
        "product suite %s: runs=%s",
        task_id,
        [r.as_dict() for r in runs] if runs is not None else "no runner holds a test",
    )
    if not runs or not all(r.passed for r in runs):
        return None
    return judged_passed(result, runs)
