"""The skeleton-execution gate — Gate 2's dynamic half (SIP-0104 P2).

Collection is not sufficient (plan P2): every behavior shell must actually *execute*
against the walking skeleton and complete without a mechanical crash. Against stub
handlers the expected outcome is a wall of **assertion failures** (stubs throw
``not_implemented`` by design — SIP-0098 §7's bare-skeleton-must-fail rule); those are
counted and ignored. What fails the gate is the mechanical class: a suite that does not
collect, a shell the runner never saw, a ``TypeError``/``ReferenceError``/transform crash
— each is ``scaffold-invalid`` (a generator defect, SIP §5).

Placement: the handlers lane, beside ``test_runner`` — this is subprocess machinery that
needs the Node toolchain, which exists in the agent containers, not the executor. The
*classification* is a pure function over the vitest JSON report so its corpus runs
everywhere; only :func:`run_skeleton_execution_gate` needs npm.

A runner-level failure (no npm, timeout, no report produced) is ``executed=False`` and is
**infrastructure**, not scaffold-invalid — the SIP's §5 taxonomy distinguishes "the gate
could not run" from "the gate ran and the scaffold failed it", and conflating them would
let a broken toolchain condemn a correct generator.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_REPORT_FILENAME = ".scaffold_gate_report.json"
_MESSAGE_LIMIT = 400

#: vitest's OWN report vocabulary (jest-compatible JSON reporter), named so it cannot be
#: mistaken for — or drift with — this codebase's status enums (#380).
_VITEST_STATUS_FAILED = "failed"


@dataclass(frozen=True)
class SkeletonExecutionVerdict:
    """The gate's outcome for one scaffold, executed against its stub skeleton."""

    executed: bool
    scaffold_valid: bool = False
    mechanical_failures: tuple[str, ...] = ()
    assertion_failures: int = 0
    collected_files: tuple[str, ...] = ()
    missing_files: tuple[str, ...] = ()
    error: str = ""

    @property
    def summary(self) -> str:
        if not self.executed:
            return f"gate did not run: {self.error or 'unknown runner failure'}"
        if self.scaffold_valid:
            return (
                f"scaffold executed cleanly against the skeleton "
                f"({len(self.collected_files)} shell file(s), "
                f"{self.assertion_failures} expected stub assertion failure(s))"
            )
        parts = []
        if self.missing_files:
            parts.append(f"{len(self.missing_files)} shell(s) never collected")
        if self.mechanical_failures:
            parts.append(f"{len(self.mechanical_failures)} mechanical failure(s)")
        return "scaffold-invalid: " + ", ".join(parts)


def _first_line(message: str) -> str:
    return message.strip().split("\n", 1)[0][:_MESSAGE_LIMIT]


#: The shapes vitest's JSON reporter gives an ``expect()`` mismatch. Measured against a
#: real gate run (node:20-alpine, vitest 1.6, 2026-08-14): chai serializes the failure as
#: the BARE message — ``expected 500 to be 201 // Object.is equality`` — with no error-name
#: prefix; the ``AssertionError:`` form is kept for reporter variants that do prefix.
_ASSERTION_SHAPES = re.compile(r"^\s*(?:AssertionError\b|expected\b)")


def _is_assertion_failure(failure_messages: list[str]) -> bool:
    """An expected stub-behavior failure, as vitest reports expect() mismatches.

    Deliberately an ALLOWLIST of assertion shapes, not a blocklist of error names: the
    gate's safe misclassification direction is expected-as-mechanical (a valid scaffold
    fails loudly), never mechanical-as-expected (a broken shell ships — the exact tail
    this SIP exists to end). An unrecognized failure shape is therefore mechanical.
    """
    return bool(failure_messages) and all(
        _ASSERTION_SHAPES.match(message) for message in failure_messages
    )


def classify_vitest_report(report: dict, scaffold_paths: list[str]) -> SkeletonExecutionVerdict:
    """Classify a vitest ``--reporter=json`` report for the scaffold files only.

    Non-scaffold suites (the harness proof, authored tests) are outside the gate's
    subject: their outcomes are the suite run's business, not the generator's.
    """
    mechanical: list[str] = []
    assertion_failures = 0
    collected: list[str] = []

    by_suffix: dict[str, dict] = {}
    for suite in report.get("testResults", ()):
        name = str(suite.get("name", ""))
        for path in scaffold_paths:
            if name.endswith(path):
                by_suffix[path] = suite

    for path in scaffold_paths:
        suite = by_suffix.get(path)
        if suite is None:
            continue
        collected.append(path)
        results = suite.get("assertionResults") or []
        if suite.get("status") == _VITEST_STATUS_FAILED and not results:
            # The suite died before any test ran: unresolved import, transform
            # failure, a top-level throw — the collection-level mechanical class.
            mechanical.append(
                f"{path}: suite failed to run: {_first_line(str(suite.get('message', '')))}"
            )
            continue
        for result in results:
            if result.get("status") != _VITEST_STATUS_FAILED:
                continue
            messages = [str(m) for m in result.get("failureMessages") or []]
            if _is_assertion_failure(messages):
                assertion_failures += 1
            else:
                detail = _first_line(messages[0]) if messages else "no failure message"
                mechanical.append(f"{path}: {result.get('title', '?')}: {detail}")

    missing = tuple(p for p in scaffold_paths if p not in by_suffix)
    for path in missing:
        mechanical.append(
            f"{path}: never collected by the runner — the shell would silently not exist"
        )
    return SkeletonExecutionVerdict(
        executed=True,
        scaffold_valid=not mechanical,
        mechanical_failures=tuple(mechanical),
        assertion_failures=assertion_failures,
        collected_files=tuple(collected),
        missing_files=missing,
    )


async def run_skeleton_execution_gate(
    skeleton_files: list[dict[str, str]],
    scaffold_files: list[dict[str, str]],
    timeout_seconds: int = 240,
) -> SkeletonExecutionVerdict:
    """Execute the scaffold against its stub skeleton in an isolated workspace.

    Materializes skeleton + scaffold, ``npm install``s, runs the stack's runner with the
    JSON reporter, and classifies. The vitest exit code is deliberately ignored — against
    stubs the suite MUST fail (SIP-0098 §7); the report's failure *types* are the verdict.
    Never raises.
    """
    from squadops.capabilities.handlers.test_runner import _materialize_files

    scaffold_paths = [f["name"] for f in scaffold_files]
    workspace = tempfile.mkdtemp(prefix="scaffold_gate_")
    try:
        _materialize_files(
            workspace,
            [{"path": f["name"], "content": f["content"]} for f in skeleton_files]
            + [{"path": f["name"], "content": f["content"]} for f in scaffold_files],
        )

        try:
            install = await asyncio.create_subprocess_exec(
                "npm",
                "install",
                "--no-audit",
                "--no-fund",
                cwd=workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return SkeletonExecutionVerdict(
                executed=False, error="npm not found — Node.js is not installed"
            )
        try:
            await asyncio.wait_for(install.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            install.kill()
            await install.wait()
            return SkeletonExecutionVerdict(
                executed=False, error=f"npm install timed out after {timeout_seconds}s"
            )
        if install.returncode != 0:
            return SkeletonExecutionVerdict(
                executed=False, error="npm install failed (dependency resolution error)"
            )

        report_path = os.path.join(workspace, _REPORT_FILENAME)
        try:
            proc = await asyncio.create_subprocess_exec(
                "npx",
                "vitest",
                "run",
                "--reporter=json",
                f"--outputFile={report_path}",
                cwd=workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return SkeletonExecutionVerdict(
                executed=False, error="npx not found — Node.js is not installed"
            )
        try:
            _, raw_stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return SkeletonExecutionVerdict(
                executed=False, error=f"vitest timed out after {timeout_seconds}s"
            )

        try:
            with open(report_path, encoding="utf-8") as fh:
                report = json.load(fh)
        except (OSError, ValueError):
            # No report at all: vitest itself failed to start (config error, OOM).
            # Runner-level, not a scaffold verdict.
            return SkeletonExecutionVerdict(
                executed=False,
                error=(
                    "vitest produced no JSON report — runner-level failure: "
                    + _first_line(raw_stderr.decode(errors="replace"))
                ),
            )
        return classify_vitest_report(report, scaffold_paths)
    except Exception as exc:  # never raise — a runner error is infrastructure, not a verdict
        logger.warning("Skeleton execution gate error: %s", exc, exc_info=True)
        return SkeletonExecutionVerdict(executed=False, error=str(exc))
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
