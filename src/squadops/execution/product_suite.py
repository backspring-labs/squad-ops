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
the task stays failed on that run's reading, not the agent's (#2913: the image's error about a
dependency it lacks told the analysis and the repair nothing was wrong). If it can't run, the
agent's result stands and the correction loop sees it as before.

#2877: when the qa image couldn't run the suite at all (its ``tests_pass`` row reads not executed:
a vitest product's suite, which the image's pytest can't collect), the product's runner runs it
whatever else failed, and its reading replaces the image's before the correction loop sees the
result. Otherwise the image's "not run" repeats every round as a carried failure, and its words
(``backend tests must be Python files``) reach the analysis and the repair as advice. A pass there
still judges the task only when nothing else failed; a re-read result otherwise stays failed, on
the product runner's evidence.

The tree is the product's own at the pin, from the managed clone, as the baseline and the
acceptance read it, with what the agent ran laid over it: ``qa_run_tree.suite_run_tree`` over the
dispatched inputs (the product's non-test files as the run has them), then a retest's repaired
files, with the suite beside them. The clone is the base because a run's artifacts hold back what
no task's view carries, a binary file or a generated lockfile, and a product's setup needs them:
``npm ci`` installs nothing without ``package-lock.json`` (#2900). A sample application's run is
never re-judged: its suite already runs where its stack's toolchain lives.
"""

from __future__ import annotations

import dataclasses
import logging
import re
from collections.abc import Callable, Mapping
from typing import Any

from squadops.campaigns.runner_acceptance import RunnerSetup, single_file_argv
from squadops.capabilities.handlers.source_repository import source_backed
from squadops.capabilities.qa_run_tree import product_runners, product_tree, suite_run_tree
from squadops.cycles.verification_integrity import ResultStatus
from squadops.cycles.verification_normalize import row_is_blocking_failure
from squadops.tasks.models import TaskResult, TaskResultStatus
from squadops.tasks.task_types import authors_qa_suite

logger = logging.getLogger(__name__)

#: The ``tests_pass`` row's ``judged_on`` when the product's runner decided it.
PRODUCT_RUNNER = "product_runner"
#: Where the product runner's runs are kept on the judged result's outputs.
PRODUCT_SUITE_KEY = "product_runner_suite"
_TESTS_PASS = "tests_pass"
_SUCCESS = "success"
#: #2838: typed checks the qa agent executes in its own image, which fail there for the same reason
#: the suite does when the product's dependencies are missing (2.5.1 spike, ``cmp_76242b27df5b``:
#: ``acceptance:module_imports`` failed beside ``tests_pass`` on a module the image lacked). A pass on
#: the product's runner doesn't credit them; it records them as not executed in a valid environment.
ENVIRONMENT_SENSITIVE = frozenset({"acceptance:module_imports", "acceptance:command_exit_zero"})


def sandbox_workspace_id(kind: str, run_id: str, task_id: str) -> str:
    """The workspace one task's run of ``kind`` seeds, apart from acceptance's (``acc-``), in the
    sandbox's id alphabet (``[A-Za-z0-9_-]``): a task id carries its task type's ``.`` (#2845)."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", f"{kind}-{run_id}-{task_id}")


def suite_workspace_prefix(run_id: str, task_id: str) -> str:
    """The workspace one task's re-judged suite seeds."""
    return sandbox_workspace_id("suite", run_id, task_id)


def _failing(row: Any) -> bool:
    """A row the loop would act on: the system's one predicate, and never a skipped row, which is
    not executed rather than failed (SIP-0096), whatever its ``passed`` reads (#2838)."""
    return (
        isinstance(row, Mapping)
        and row.get("status") != ResultStatus.SKIPPED
        and row_is_blocking_failure(row)
    )


def why_not_rejudged(task_type: str, inputs: Mapping[str, Any], result: TaskResult) -> str | None:
    """Why the product's runner can't decide this result, or ``None`` when it can: a product's
    ``qa.test`` whose ``tests_pass`` failed, beside nothing but checks that fail in the qa image for
    the same reason (``ENVIRONMENT_SENSITIVE``). Any other failing check (a probe, an authenticity
    check, a missing file) is the agent's to report, and stands."""
    if result.status == TaskResultStatus.SUCCEEDED:
        return "the task succeeded"
    if not authors_qa_suite(task_type):
        return f"{task_type} doesn't author the qa suite"
    if not source_backed(inputs):
        return "a sample application's run"
    checks = ((result.outputs or {}).get("validation_result") or {}).get("checks") or []
    failing = [str(c.get("check")) for c in checks if _failing(c)]
    if _TESTS_PASS not in failing:
        return f"tests_pass didn't fail (failing: {failing})"
    others = [c for c in failing if c != _TESTS_PASS and c not in ENVIRONMENT_SENSITIVE]
    if others:
        return f"other checks failed: {others}"
    return None


def rejudgeable(task_type: str, inputs: Mapping[str, Any], result: TaskResult) -> bool:
    return why_not_rejudged(task_type, inputs, result) is None


def _tests_pass_row(result: TaskResult) -> Mapping[str, Any] | None:
    checks = ((result.outputs or {}).get("validation_result") or {}).get("checks") or []
    return next(
        (c for c in checks if isinstance(c, Mapping) and c.get("check") == _TESTS_PASS), None
    )


def why_not_reread(task_type: str, inputs: Mapping[str, Any], result: TaskResult) -> str | None:
    """#2877, SIP-0112 H.26: why the product's runner's reading can't replace the image's, or
    ``None`` when it can: a product's ``qa.test`` whose ``tests_pass`` failed, whatever else failed
    beside it and whether or not the image executed the suite. The image is never the authority
    on a product's suite, so what it managed to run must not decide who reads the failure."""
    if result.status == TaskResultStatus.SUCCEEDED:
        return "the task succeeded"
    if not authors_qa_suite(task_type):
        return f"{task_type} doesn't author the qa suite"
    if not source_backed(inputs):
        return "a sample application's run"
    row = _tests_pass_row(result)
    if row is None or not _failing(row):
        return "tests_pass didn't fail"
    return None


#: A retest's own suite (#2881): the failed task's test files, which
#: ``CorrectionRunner.reexecute_repaired_suite`` carries beside ``retest_files``. A retest's
#: ``retest_files`` are the repair's patched files, and a dev repair's are source, which no
#: runner holds, so they can't be the suite on the product's runner.
RETEST_SUITE_KEY = "retest_suite"


def _by_path(files: Any, name_key: str) -> dict[str, str]:
    return {
        str(f[name_key]): str(f.get("content") or "")
        for f in files or []
        if isinstance(f, Mapping) and f.get(name_key)
    }


def emitted_tests(inputs: Mapping[str, Any], outputs: Mapping[str, Any]) -> dict[str, str]:
    """The test files an emission stored, by path, or a retest's ``retest_files`` when it
    carries no suite of its own (an envelope from before #2881)."""
    retest = inputs.get("retest_files")
    if retest:
        return _by_path(retest, "filename")
    return _by_path(
        [
            a
            for a in outputs.get("artifacts") or []
            if isinstance(a, Mapping) and a.get("type") == "test"
        ],
        "name",
    )


def suite_under_judgement(
    inputs: Mapping[str, Any], outputs: Mapping[str, Any], profile: Any
) -> tuple[dict[str, str], dict[str, str]]:
    """The test files to run on the product's runner, and the files to lay over the tree first.

    An emission's suite is the test files it stored. A retest's (#2881) is the failed task's own
    suite (``RETEST_SUITE_KEY``), with each patched file a runner holds replacing its namesake,
    while the patched files no runner holds (a dev repair's source) are overlaid on the tree, so
    the suite runs against the repaired code, as the qa image's retest does
    (``test_runner._effective_sources``)."""
    suite = _by_path(inputs.get(RETEST_SUITE_KEY), "filename")
    if not inputs.get("retest_files") or not suite:
        return emitted_tests(inputs, outputs), {}
    patched = _by_path(inputs.get("retest_files"), "filename")
    held = {path: c for path, c in patched.items() if profile.runner_for(path) is not None}
    overlay = {path: c for path, c in patched.items() if path not in held}
    return {**suite, **held}, overlay


@dataclasses.dataclass(frozen=True)
class PinnedTree:
    """The product's own non-test files at the cycle's pin, as bytes, and their executable bits."""

    files: Mapping[str, bytes]
    executable: frozenset[str]


async def product_tree_at_pin(
    repository: Any,
    cycle: Any,
    inputs: Mapping[str, Any],
    task_id: str,
    *,
    unread: str = "product suite %s: not re-judged",
) -> PinnedTree | None:
    """The product's own non-test files at the cycle's pin, from the managed clone, or ``None``
    when there is no clone to read: a tree without the files its artifacts hold back fails the
    product's setup, so it judges nothing (#2900). ``unread`` opens the log line that says so, for
    the caller it stops (``%s`` is the task): the re-judged suite, or the head check (#2890)."""
    context = cycle.source_context
    if repository is None:
        logger.info(unread + ": no source repository", task_id)
        return None
    try:
        clone = await repository.tree_at(cycle.project_id, context.pinned_commit)
    except Exception:
        logger.warning(
            unread + ": the product's tree at %s is unreadable",
            task_id,
            getattr(context, "pinned_commit", None),
            exc_info=True,
        )
        return None
    files = product_tree(clone.files, product_runners(inputs))
    return PinnedTree(files, frozenset(clone.executable) & frozenset(files))


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
    #: The failing tests' ids, as the test-id reader keyed them, and the end of the run's output:
    #: what a re-read result shows the correction loop in place of the image's (#2877).
    failing: tuple[str, ...] = ()
    output_tail: str = ""

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
        return dataclasses.asdict(self) | {
            "argv": list(self.argv),
            "failing": list(self.failing),
            "passed": self.passed,
        }


def _removed(inputs: Mapping[str, Any]) -> dict[str, None]:
    """What earlier tasks of the run removed, as a patch names a removal (H.23)."""
    return dict.fromkeys(inputs["source_repository"].get("deleted") or ())


async def run_on_product_runner(
    *,
    sandbox: Any,
    profile: Any,
    setup: RunnerSetup,
    pinned: PinnedTree,
    tree: Mapping[str, str | None],
    tests: Mapping[str, str],
    workspace_id: str,
) -> list[SuiteRun] | None:
    """Run each of ``tests`` on its own runner's single-file command, read by that runner's
    test-id reader, on ``pinned`` with ``tree`` and ``tests`` laid over it (a ``None`` in ``tree``
    removes that path: H.23). ``None`` when a test
    file is held by no runner, or by one that can't be scoped to a file or has no test-id reader:
    the product names no way to show that file's tests ran, so nothing here can judge it.

    ``pinned`` is seeded as the checkout it is (``GIT_CHECKOUT``), so the sandbox takes a file its
    derived-state rule would refuse from anything else, a tracked ``package-lock.json`` (X-2), and
    the rest is a patch on it, as source delivery assembles a candidate (#2900)."""
    # deferred (pair): squadops.sandbox imports the campaigns package at load (its API's seed plan)
    from squadops.sandbox.findings import FindingsReading

    # deferred (pair): as above
    from squadops.sandbox.models import CommandOutcome, RevisionOrigin, WorkspaceRevision

    planned: list[tuple[str, Any]] = []
    for path in tests:
        runner = profile.runner_for(path)
        if runner is None or runner.single_file_argv is None or not runner.test_ids:
            return None
        planned.append((path, runner))
    runs: list[SuiteRun] = []
    await sandbox.release_workspace(workspace_id)
    try:
        seeded = await sandbox.seed_workspace(
            workspace_id,
            dict(pinned.files),
            origin=RevisionOrigin.GIT_CHECKOUT,
            executable=pinned.executable,
        )
        patched = await sandbox.apply_workspace_patch(base=seeded, files={**tree, **tests})
        revision = WorkspaceRevision(
            revision_id=patched.new_revision_id,
            cycle_id=workspace_id,
            origin=RevisionOrigin.AGENT_PATCH,
            parent_revision_id=seeded.revision_id,
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
            parsed = FindingsReading.from_dict(findings) if findings else None
            reading = parsed if parsed is not None and parsed.readable else None
            runs.append(
                SuiteRun(
                    runner=runner.runner,
                    path=path,
                    argv=argv,
                    revision_id=revision.revision_id,
                    exit_code=result.exit_code if exited else None,
                    tests_passed=reading.passed if reading is not None else None,
                    collected=reading.collected if reading is not None else None,
                    failing=tuple(sorted(reading.counts)) if reading is not None else (),
                    output_tail=_output_tail(result),
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


#: How much of a run's output a re-read result carries: the end, where a runner's summary is.
_OUTPUT_TAIL_LIMIT = 2000
_FAILING_CASES_LIMIT = 40


def _output_tail(result: Any) -> str:
    text = "\n".join(
        t for t in (getattr(result, "stdout_tail", ""), getattr(result, "stderr_tail", "")) if t
    )
    return text[-_OUTPUT_TAIL_LIMIT:]


def _runner_summary(runs: list[SuiteRun], still_failing: list[str]) -> str:
    runners = ", ".join(sorted({r.runner for r in runs}))
    if all(r.passed for r in runs):
        verdict = f"the suite passed on the product's runner ({runners})"
    else:
        failed = [r.path for r in runs if not r.passed]
        verdict = f"the suite failed on the product's runner ({runners}): {', '.join(failed)}"
    return verdict + (f"; also failing: {', '.join(still_failing)}" if still_failing else "")


def _runner_row(runs: list[SuiteRun]) -> dict[str, Any]:
    """The ``tests_pass`` row the product's runner gives, in ``failed_tests_pass_row``'s shape, so
    the correction loop's signature and the repair brief read it as they read the image's."""
    passed = all(r.passed for r in runs)
    exited = all(r.unexecuted is None for r in runs)
    row: dict[str, Any] = {
        "check": _TESTS_PASS,
        "executed": exited,
        "exit_code": next((r.exit_code for r in runs if r.exit_code), 0 if exited else None),
        "tests_passed": passed,
        "passed": passed,
        "judged_on": PRODUCT_RUNNER,
        "runner": ",".join(r.runner for r in runs),
    }
    if passed:
        return row
    cases = [
        {"file": r.path, "title": test_id, "line": None, "failing_line": None, "message": ""}
        for r in runs
        for test_id in r.failing
    ][:_FAILING_CASES_LIMIT]
    return row | {
        # A file that ran nothing it could read (a syntax or import error) is a broken suite,
        # which the locus classifier reads as the qa role's, as it reads the image's.
        "suite_broken": any(not r.passed and not r.failing for r in runs),
        # ``file::title``, as the signature partitions an identity (``correction_signature``).
        "failing_tests": sorted({f"{c['file']}::{c['title']}" for c in cases}),
        "suite_defects": [],
        "failing_cases": cases,
        "runner_output": {r.path: r.output_tail for r in runs if not r.passed and r.output_tail},
    }


def _runner_report(runs: list[SuiteRun], summary: str, agent_test: Any = None) -> str:
    """What ran, where, on which runner, and with what result (H.26). The qa image's own attempt is
    named beside it, so this report can't read as if the image's result were the suite's."""
    runners = ", ".join(sorted({r.runner for r in runs}))
    image = (agent_test or {}).get("summary") if isinstance(agent_test, Mapping) else None
    lines = [
        "# Test Execution Report",
        "",
        f"**Result:** {summary}",
        "",
        f"**Ran on:** the product's runner ({runners}), in the sandbox",
        "",
        f"**In the qa image:** {image or 'no reading'}",
        "",
    ]
    for r in runs:
        lines += [
            f"## {r.path}",
            "",
            f"- command: `{' '.join(r.argv)}`",
            f"- exit code: {r.exit_code if r.unexecuted is None else 'not run: ' + r.unexecuted}",
            f"- passed: {r.tests_passed} of {r.collected}",
        ]
        if r.failing:
            lines += ["- failing:", *(f"  - {t}" for t in r.failing)]
        if not r.passed and r.output_tail:
            lines += ["", "```", r.output_tail, "```"]
        lines.append("")
    return "\n".join(lines)


def _with_runner_report(
    outputs: Mapping[str, Any], runs: list[SuiteRun], summary: str, agent_test: Any
) -> list[Any]:
    """The task's artifacts, its ``test_report`` being the product runner's. Both judgements use
    it: a report left as the image wrote it said a suite that passed had never run (#2937)."""
    return [
        {**a, "content": _runner_report(runs, summary, agent_test)}
        if isinstance(a, Mapping) and a.get("type") == "test_report"
        else a
        for a in outputs.get("artifacts") or []
    ]


def reread(result: TaskResult, runs: list[SuiteRun]) -> TaskResult:
    """#2877, #2913: ``result`` with the product runner's reading of its suite in place of the qa
    image's, a "not run" or a failure the image's environment made. It stays failed: either the
    suite failed on the product's runner, or another check did. The image's row and test result
    are kept apart from what the analysis reads."""
    outputs = dict(result.outputs or {})
    vr = dict(outputs.get("validation_result") or {})
    passed = all(r.passed for r in runs)
    checks, agent_row = [], None
    for row in vr.get("checks") or []:
        if isinstance(row, Mapping) and row.get("check") == _TESTS_PASS:
            agent_row, row = dict(row), _runner_row(runs)
        elif passed and isinstance(row, Mapping) and row.get("check") in ENVIRONMENT_SENSITIVE:
            if _failing(row):
                row = {
                    "check": row["check"],
                    "status": ResultStatus.SKIPPED,
                    "reason": "agent_environment: the suite passed on the product's runner",
                    "agent_reading": dict(row),
                }
        checks.append(row)
    still_failing = [
        str(c.get("check")) for c in checks if _failing(c) and c.get("check") != _TESTS_PASS
    ]
    summary = _runner_summary(runs, still_failing)
    missing = [m for m in vr.get("missing_components") or [] if _TESTS_PASS not in m]
    vr.update(
        checks=checks,
        missing_components=missing if passed else [*missing, _TESTS_PASS],
        summary=summary,
    )
    agent_test = outputs.get("test_result")
    outputs.update(
        validation_result=vr,
        agent_tests_pass_row=agent_row,
        test_result={
            "executed": all(r.unexecuted is None for r in runs),
            "exit_code": _runner_row(runs)["exit_code"],
            "tests_passed": passed,
            "test_file_count": len(runs),
            "source_file_count": (agent_test or {}).get("source_file_count"),
            "summary": summary,
            "judged_on": PRODUCT_RUNNER,
        },
        summary=f"[qa] {summary}",
    )
    if agent_test is not None:
        outputs["agent_test_result"] = agent_test
    outputs[PRODUCT_SUITE_KEY] = [r.as_dict() for r in runs]
    outputs["artifacts"] = _with_runner_report(outputs, runs, summary, agent_test)
    return dataclasses.replace(result, outputs=outputs, error=summary)


def judged_passed(result: TaskResult, runs: list[SuiteRun]) -> TaskResult:
    """``result`` judged passed on the product's runner: its ``tests_pass`` row reads the runner's
    runs, with the agent's row kept as ``agent_reading``, and the task succeeds."""
    outputs = dict(result.outputs or {})
    vr = dict(outputs.get("validation_result") or {})
    checks = []
    for row in vr.get("checks") or []:
        if isinstance(row, Mapping) and row.get("check") in ENVIRONMENT_SENSITIVE and _failing(row):
            row = {
                "check": row["check"],
                "status": ResultStatus.SKIPPED,
                "reason": "agent_environment: the suite passed on the product's runner",
                "agent_reading": dict(row),
            }
        elif isinstance(row, Mapping) and row.get("check") == _TESTS_PASS:
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
    outputs["artifacts"] = _with_runner_report(outputs, runs, vr["summary"], agent)
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
    repository: Any,
    read_profile: Callable[[Any], Any],
) -> TaskResult | None:
    """The result judged on the product's runner, or ``None`` when the agent's result stands.

    Judged passed (``SUCCEEDED``): a product's ``qa.test`` failing only ``tests_pass`` (beside
    ``ENVIRONMENT_SENSITIVE`` checks) whose suite passes there. Re-read (still ``FAILED``): any
    other product ``qa.test`` whose ``tests_pass`` failed (#2877, H.26), on the runner's reading. ``None``: neither applies, no sandbox, no profile or
    configuration at the pin, no clone of the product at the pin, a test no runner holds, or a run
    that can't be judged or didn't exit."""
    if result.status == TaskResultStatus.SUCCEEDED or not authors_qa_suite(task_type):
        return None
    why_judge: str | None
    why_reread: str | None
    if sandbox is None:
        why_judge = why_reread = "no sandbox"
    else:
        why_judge = why_not_rejudged(task_type, inputs, result)
        why_reread = why_not_reread(task_type, inputs, result)
    if why_judge is not None and why_reread is not None:
        # #2838: a product's failed suite the runner didn't re-judge says why, in the log.
        logger.info(
            "product suite %s: not re-judged: %s; not re-read: %s", task_id, why_judge, why_reread
        )
        return None
    context = getattr(cycle, "source_context", None)
    profile = await read_profile(cycle)
    if context is None or profile is None:
        return None
    configuration = await projects.get_development_configuration(
        cycle.project_id, context.development_configuration_revision
    )
    tests, overlay = suite_under_judgement(inputs, result.outputs or {}, profile)
    if configuration is None or not tests:
        return None
    pinned = await product_tree_at_pin(repository, cycle, inputs, task_id)
    if pinned is None:
        return None
    try:
        runs = await run_on_product_runner(
            sandbox=sandbox,
            profile=profile,
            setup=RunnerSetup.of(configuration.commands),
            pinned=pinned,
            # H.23: the pin still holds what the run removed. A file written since wins.
            tree={**_removed(inputs), **suite_run_tree(inputs), **overlay},
            tests=tests,
            workspace_id=suite_workspace_prefix(run_id, task_id),
        )
    except Exception:
        # #2845: a judgement that can't run leaves the agent's result for the correction loop, as
        # every other case it can't judge does. It never fails the run.
        logger.warning(
            "product suite %s: not re-judged: the sandbox run failed", task_id, exc_info=True
        )
        return None
    logger.info(
        "product suite %s: runs=%s",
        task_id,
        [r.as_dict() for r in runs] if runs is not None else "no runner holds a test",
    )
    if not runs:
        return None
    if why_judge is None and all(r.passed for r in runs):
        return judged_passed(result, runs)
    exited = all(r.unexecuted is None for r in runs)
    row = _tests_pass_row(result) or {}
    # A run that never exited is no reading, so what the image read stands (H.24), unless the
    # image read nothing either (#2877).
    if exited or (why_reread is None and row.get("executed") is False):
        return reread(result, runs)
    return None
