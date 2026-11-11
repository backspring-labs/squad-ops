"""The fixture provider: one operation that checks the files a request stages (SIP-0117 R5.5).

It drives no tool. It is what a worker runs to prove the path from a queued operation to an
accepted result, and its results are real readings of the request:

- **``fixture/staged_files``**: each assertion the scenario declares names a path. The
  assertion passes when the request stages a file with content at that path, and fails when
  the path isn't staged or the file is empty. The evidence is a manifest of the staged paths
  with each one's digest.
- **A staged ``.fixture/hold_seconds``** makes the operation wait that many seconds before it
  checks, so a rehearsal can watch a lease renew and a cancel arrive. A value that isn't a
  number of seconds is ``not_executed``, with the value.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from collections.abc import Awaitable, Callable, Mapping

from squadops.ports.remote_execution import OperationRunnerPort
from squadops.remote_execution.models import (
    AssertionOutcome,
    AssertionRecord,
    EvidenceItem,
    OperationStatus,
    RemoteOperationRequest,
    RemoteOperationResult,
)
from squadops.remote_execution.workers import ServedOperation
from squadops.runtime.models import RuntimeStatus

PROVIDER = "fixture"
OPERATION = "staged_files"
VERSION = "1"
HOLD_PATH = ".fixture/hold_seconds"
MANIFEST_NAME = "staged_files.json"


class FixtureOperationRunner(OperationRunnerPort):
    def __init__(self, *, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._sleep = sleep

    def serves(self) -> tuple[ServedOperation, ...]:
        return (ServedOperation(PROVIDER, OPERATION),)

    async def tool_versions(self) -> Mapping[str, str]:
        return {PROVIDER: VERSION}

    async def health(self) -> RuntimeStatus:
        return "online"

    async def reset(self) -> None:
        """Nothing to reset: the fixture keeps nothing between operations."""

    async def run(self, request: RemoteOperationRequest) -> RemoteOperationResult:
        if (request.provider, request.operation) != (PROVIDER, OPERATION):
            return self._not_executed(
                request,
                f"the fixture provider runs {PROVIDER}/{OPERATION}, and was asked for "
                f"{request.provider}/{request.operation}",
            )
        if HOLD_PATH in request.source_files:
            held = request.source_files[HOLD_PATH]
            try:
                seconds = float(held)
            except ValueError:
                seconds = math.nan
            if not math.isfinite(seconds) or seconds < 0:
                return self._not_executed(
                    request, f"{HOLD_PATH} is {held!r}, which isn't a number of seconds"
                )
            await self._sleep(seconds)
        manifest = {
            path: "sha256:" + hashlib.sha256(content.encode()).hexdigest()
            for path, content in sorted(request.source_files.items())
        }
        return RemoteOperationResult(
            status=OperationStatus.COMPLETED,
            records=tuple(
                _record(assertion_id, request.source_files)
                for assertion_id in request.scenario.assertions
            ),
            evidence=(
                EvidenceItem(MANIFEST_NAME, json.dumps(manifest, indent=2), "application/json"),
            ),
            provider_version=f"{PROVIDER}@{VERSION}",
            ran_with={PROVIDER: VERSION},
            dispatch_id=request.dispatch_id,
        )

    def _not_executed(self, request: RemoteOperationRequest, reason: str) -> RemoteOperationResult:
        return RemoteOperationResult(
            status=OperationStatus.NOT_EXECUTED,
            reason=reason,
            provider_version=f"{PROVIDER}@{VERSION}",
            dispatch_id=request.dispatch_id,
        )


def _record(path: str, staged: Mapping[str, str]) -> AssertionRecord:
    expected = "a staged file with content"
    if path not in staged:
        return AssertionRecord(path, AssertionOutcome.FAILED, "not staged", expected, "worker")
    size = len(staged[path].encode())
    if size == 0:
        return AssertionRecord(path, AssertionOutcome.FAILED, "staged, empty", expected, "worker")
    return AssertionRecord(
        path, AssertionOutcome.PASSED, f"staged, {size} bytes", expected, "worker"
    )
