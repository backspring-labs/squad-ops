"""Re-qualifying the worker after a Studio update (SIP-0117 R5.21; #3048).

# Platform: dev-mac (Roblox Studio and its StudioMCP run on the worker's Mac)

Studio updates itself, unasked, and its tool list changes with it. The worker is pinned to the
Studio version and tool list its operation was proved on, so after an update each claim reads
``not_executed`` with the difference named (R2.4). The only way to move the pin is a
re-qualification on the updated Studio, and its record is the pin:
- **the run:** the qualification scenario played on the live Studio, the place reset (Studio
  quit, the place restored, Studio reopened), and the scenario played again. It passes when both
  plays complete with every assertion passed, and the reset succeeds;
- **the record:** one JSON document per run, passed or failed, in the worker's qualifications
  directory. It names the Studio version and tool list it ran on, the tools added and removed
  since the pin it replaces, the scenario and source it played, and each step's outcome;
- **the pin:** the newest passing record for this provider version. A failed run leaves the pin
  where it was, and names the step that failed.

Each record carries the digest of its own body, and a record whose digest doesn't match is
refused by name, as is any record that can't be read. A pin isn't moved by editing a file.

The worker reads its pin at each claim, so the claim after a passing re-qualification runs with
no restart. A re-qualification holds Studio for its whole run through a lock file in the same
directory, and a claim or a reset that finds it held reads ``not_executed``, or tries again.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adapters.remote_execution.game_dev_roblox_studio import place
from adapters.remote_execution.game_dev_roblox_studio.runner import (
    OPERATION,
    PROVIDER,
    PROVIDER_VERSION,
    NotProved,
    ProvedOn,
    RobloxStudioRunner,
    StudioBusy,
)
from adapters.remote_execution.game_dev_roblox_studio.session import StudioSessionError
from squadops.remote_execution.models import OperationStatus, RemoteOperationRequest

SCHEMA = "squadops.studio-qualification/1"
LOCK_NAME = "studio.lock"
_KEYS = frozenset(
    {
        "schema", "provider", "provider_version", "recorded_at", "passed", "failing",
        "studio_version", "studio_tools", "tool_names", "replaces", "tools_added",
        "tools_removed", "scenario_digest", "source_revision", "steps", "digest",
    }
)  # fmt: skip


@dataclass(frozen=True)
class Step:
    """One step of the run: a play or the reset, with its outcome."""

    name: str
    #: ``completed``, ``not_executed`` or ``interrupted`` for a play; ``reset`` or ``failed``.
    status: str
    reason: str
    #: A play's assertions, ``id: outcome``.
    records: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        if self.name == "reset":
            return self.status == "reset"
        return (
            self.status == OperationStatus.COMPLETED.value
            and bool(self.records)
            and all(r.endswith(": passed") for r in self.records)
        )

    def failure(self) -> str:
        if self.status in (OperationStatus.COMPLETED.value, "reset"):
            failed = [r for r in self.records if not r.endswith(": passed")]
            return f"{self.name}: {', '.join(failed) or 'no assertion was recorded'}"
        return f"{self.name}: {self.status}: {self.reason}"


@dataclass(frozen=True)
class QualificationRecord:
    """One re-qualification run, as recorded (#3048)."""

    recorded_at: str
    passed: bool
    #: The first step that failed, named. Empty for a passing run.
    failing: str
    studio_version: str
    #: ``<count>:<schema digest>``, as the runner holds Studio to it.
    studio_tools: str
    tool_names: tuple[str, ...]
    #: The digest of the passing record whose pin this run would replace, or empty for the first.
    replaces: str
    tools_added: tuple[str, ...]
    tools_removed: tuple[str, ...]
    scenario_digest: str
    source_revision: str
    steps: tuple[Step, ...]
    provider_version: str = PROVIDER_VERSION

    def body(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "provider": PROVIDER,
            "provider_version": self.provider_version,
            "recorded_at": self.recorded_at,
            "passed": self.passed,
            "failing": self.failing,
            "studio_version": self.studio_version,
            "studio_tools": self.studio_tools,
            "tool_names": list(self.tool_names),
            "replaces": self.replaces,
            "tools_added": list(self.tools_added),
            "tools_removed": list(self.tools_removed),
            "scenario_digest": self.scenario_digest,
            "source_revision": self.source_revision,
            "steps": [
                {"name": s.name, "status": s.status, "reason": s.reason, "records": list(s.records)}
                for s in self.steps
            ],  # fmt: skip
        }

    @property
    def digest(self) -> str:
        return _digest(self.body())

    def pins(self) -> ProvedOn:
        return ProvedOn(self.studio_version, self.studio_tools, record=self.digest)

    def to_document(self) -> dict[str, Any]:
        return {**self.body(), "digest": self.digest}


def _digest(body: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def record_from_document(document: Any, where: str) -> QualificationRecord:
    """The record, or :class:`NotProved` naming what is wrong with it. Nothing is defaulted."""
    if not isinstance(document, dict) or set(document) != _KEYS:
        keys = sorted(document) if isinstance(document, dict) else type(document).__name__
        raise NotProved(f"the qualification record {where} isn't one: its keys are {keys}")
    if document["schema"] != SCHEMA or document["provider"] != PROVIDER:
        raise NotProved(
            f"the qualification record {where} is {document['schema']} for "
            f"{document['provider']}, not {SCHEMA} for {PROVIDER}"
        )
    body = {k: v for k, v in document.items() if k != "digest"}
    if _digest(body) != document["digest"]:
        raise NotProved(
            f"the qualification record {where} doesn't match its own digest: it was changed "
            "after it was recorded, and only a re-qualification moves a pin"
        )
    try:
        steps = tuple(
            Step(s["name"], s["status"], s["reason"], tuple(s["records"]))
            for s in document["steps"]
        )
        return QualificationRecord(
            recorded_at=document["recorded_at"],
            passed=document["passed"],
            failing=document["failing"],
            studio_version=document["studio_version"],
            studio_tools=document["studio_tools"],
            tool_names=tuple(document["tool_names"]),
            replaces=document["replaces"],
            tools_added=tuple(document["tools_added"]),
            tools_removed=tuple(document["tools_removed"]),
            scenario_digest=document["scenario_digest"],
            source_revision=document["source_revision"],
            steps=steps,
            provider_version=document["provider_version"],
        )
    except (KeyError, TypeError) as e:
        raise NotProved(f"the qualification record {where} can't be read: {e!r}") from e


class Qualifications:
    """A worker's qualification records, and the lock that holds Studio (#3048). It is the
    runner's :class:`~runner.Pins`."""

    def __init__(self, directory: Path) -> None:
        if not directory.is_dir():
            raise ValueError(f"the qualifications directory {directory} isn't there")
        self.directory = directory

    def records(self) -> list[QualificationRecord]:
        """Every record, oldest first. Raises :class:`NotProved` naming one that can't be read:
        skipping it could pin an older record over a newer one."""
        found = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                raise NotProved(f"the qualification record {path.name} can't be read: {e}") from e
            found.append(record_from_document(document, path.name))
        return sorted(found, key=lambda r: r.recorded_at)

    def pinned(self) -> QualificationRecord | None:
        """The newest passing record for this provider version, or ``None``."""
        passing = [r for r in self.records() if r.passed and r.provider_version == PROVIDER_VERSION]
        return passing[-1] if passing else None

    def current(self) -> ProvedOn:
        record = self.pinned()
        if record is None:
            raise NotProved(
                f"no passing qualification of {PROVIDER} {PROVIDER_VERSION} is recorded in "
                f"{self.directory}, so nothing says which Studio {OPERATION} was proved on "
                "(R2.4); re-qualify"
            )
        return record.pins()

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        with (self.directory / LOCK_NAME).open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as e:
                raise StudioBusy(
                    "Studio is held by another process (a re-qualification, or a worker's "
                    f"claim): {self.directory / LOCK_NAME} is locked"
                ) from e
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def write(self, record: QualificationRecord) -> Path:
        """The record, written whole: a reader never sees half of one."""
        stamp = record.recorded_at.replace(":", "").replace("-", "")
        path = self.directory / f"{stamp}-{'passed' if record.passed else 'failed'}.json"
        partial = path.with_suffix(".partial")
        partial.write_text(json.dumps(record.to_document(), indent=2) + "\n", encoding="utf-8")
        os.replace(partial, path)
        return path


async def requalify(
    qualifications: Qualifications,
    runner_for: Callable[[ProvedOn], RobloxStudioRunner],
    request_for: Callable[[str], RemoteOperationRequest],
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> tuple[QualificationRecord, Path]:
    """Re-qualify on the live Studio and record the run, passed or failed (#3048).

    ``runner_for`` builds the runner held to the pins under test; ``request_for`` builds the
    qualification request for a round name. Raises :class:`StudioBusy` when a worker holds
    Studio, and records nothing then."""
    with qualifications.exclusive():
        previous = qualifications.pinned()
        steps: list[Step] = []
        names: tuple[str, ...] = ()
        try:
            probe = runner_for(ProvedOn("", ""))
            version, check = await probe.live_studio()
        except (StudioSessionError, ValueError, OSError) as e:
            version, tools = "", ""
            steps.append(Step("tool check", "failed", f"{type(e).__name__}: {e}"))
        else:
            tools, names = f"{check.count}:{check.schema_digest}", check.names
            runner = runner_for(ProvedOn(version, tools))
            for name in ("play 1", "reset", "play 2"):
                if steps and not steps[-1].passed:
                    break
                steps.append(await _step(runner, name, request_for))
        failed = [s for s in steps if not s.passed]
        request = request_for("record")
        record = QualificationRecord(
            recorded_at=now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            passed=not failed and len(steps) == 3,
            failing=failed[0].failure() if failed else "",
            studio_version=version,
            studio_tools=tools,
            tool_names=tuple(names),
            replaces=previous.digest if previous else "",
            tools_added=tuple(sorted(set(names) - set(previous.tool_names if previous else ()))),
            tools_removed=tuple(sorted(set(previous.tool_names if previous else ()) - set(names))),
            scenario_digest=request.scenario.digest,
            source_revision=request.source_revision,
            steps=tuple(steps),
        )
        return record, qualifications.write(record)


async def _step(
    runner: RobloxStudioRunner,
    name: str,
    request_for: Callable[[str], RemoteOperationRequest],
) -> Step:
    if name == "reset":
        try:
            await runner.reset()
        except (place.PlaceStateError, place.PlaceReadError, StudioSessionError, OSError) as e:
            return Step(name, "failed", f"{type(e).__name__}: {e}")
        return Step(name, "reset", "")
    result = await runner.run(request_for(name))
    return Step(
        name,
        result.status.value,
        result.reason,
        tuple(f"{r.assertion_id}: {r.outcome.value}" for r in result.records),
    )
