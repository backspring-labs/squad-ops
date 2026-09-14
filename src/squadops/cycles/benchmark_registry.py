"""The benchmark registry: which stored rolls the scorecard re-grades, and whether it can (SIP-0108 §4.3).

**A row per roll.** A row is one roll of one verification set. It carries:
- the cycle, the set and the set's record;
- the roll's position and role;
- the stack its arm ran and the code it ran on;
- when the stores can answer, the cycle's assessment by (a), with attribution from (b).

The membership is committed (``docs/benchmark/rolls.yaml``). The assessment is computed on read
from the registry and the vault (§4.1), never from the driver's per-roll JSON records or the
logs (§2).

**Why membership is declared, and then checked against the registry.** The registry holds the
cycles but not which of them a set counted. That is decided in the set's record: a relaunched
roll 1 voids the first launch (the 1.7.2 and 1.7.3 records, §0). The registry does hold the
driver's launch note, written from the set config's ``launch_notes`` template before the roll
was observed: ``COUNTED roll {roll} of {n}``. The preflight reads that note back. A declared row
whose cycle was not launched as that counted roll is refused, so a transcription error cannot
grade a shakeout as a count. The note is the driver's rendered template, not authored prose, and
it is read only to check the declaration, never to decide membership.

**Lineage.** Two sources, in order:
1. #80's fields, where the cycle carries a commit.
2. Otherwise, the set's pinned deploy commit and image ids, from its pre-registration.

Neither is guessed. A void roll ran on a deploy its set's pins do not describe (the set was
restarted on a rebuilt one), so it carries no pins, and a row with neither source has no lineage.

**Grouping.** Rows group by ``series_for``, the one lineage seam (plan §3.5), never by a second
series key. The stack is a slice within a series: the 1.x sets ran both arms under one project,
squad profile and request profile, with the stack set as an override.

Pure: the caller reads the manifest, the set configs and the stores, and passes them in.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from squadops.cycles.cycle_assessment import CycleAssessment, CycleEvidence, EvidenceRef
    from squadops.cycles.lineage import SeriesKey
    from squadops.cycles.models import Cycle

BENCHMARK_REGISTRY_VERSION = 1

#: The driver's launch-note template for a counted roll, as every set config since 1.6.3 renders
#: it (``launch_notes``: ``… COUNTED roll {roll} of {n} …``).
_COUNTED_LAUNCH_NOTE = re.compile(r"\bCOUNTED roll (\d+) of (\d+)\b")


class RollRole(StrEnum):
    """What a cycle was to its release: the release package's vocabulary
    (``scripts/maintainer/build_release_package.py`` ``CYCLE_ROLES``)."""

    COUNTED = "counted"
    SHAKEOUT = "shakeout"
    DIAGNOSTIC = "diagnostic"
    VOID = "void"


class PreflightRefusal(StrEnum):
    """Why a declared roll is not re-graded."""

    NOT_IN_REGISTRY = "not_in_registry"
    NOT_LAUNCHED_AS_DECLARED = "not_launched_as_declared"
    STACK_DISAGREES = "stack_disagrees"
    NO_RUNS = "no_runs"
    NO_VERIFICATION_SUMMARY = "no_verification_summary"


class LineageSource(StrEnum):
    CYCLE_RECORD = "cycle_record"
    SET_PINS = "set_pins"


class BenchmarkManifestError(ValueError):
    """The committed membership cannot be read as declared."""


@dataclass(frozen=True)
class PinnedDeploy:
    """A set's frozen deploy, and the document the pins were read from."""

    deploy_commit: str
    image_ids: Mapping[str, str]
    source: str


@dataclass(frozen=True)
class BenchmarkRoll:
    cycle_id: str
    set_name: str
    record: str
    stack: str
    roll: int
    role: RollRole
    #: ``None`` for a void roll: its set's pins describe the deploy the set restarted on.
    pins: PinnedDeploy | None
    void_reason: str | None = None


@dataclass(frozen=True)
class CodeLineage:
    source: LineageSource
    framework_version: str | None = None
    framework_git_sha: str | None = None
    pins: PinnedDeploy | None = None


@dataclass(frozen=True)
class Preflight:
    refusals: tuple[PreflightRefusal, ...] = ()
    detail: tuple[str, ...] = ()

    @property
    def gradeable(self) -> bool:
        return not self.refusals


@dataclass(frozen=True)
class BenchmarkRow:
    roll: BenchmarkRoll
    preflight: Preflight
    series: SeriesKey | None = None
    lineage: CodeLineage | None = None
    assessment: CycleAssessment | None = None
    unresolved_refs: tuple[EvidenceRef, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------------------------


def pins_configs(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    """The set configs the manifest reads pins from — the caller loads each one."""
    return tuple(s["pins_config"] for s in manifest.get("sets", ()) if "pins_config" in s)


def _pins(entry: Mapping[str, Any], configs: Mapping[str, Mapping[str, Any]]) -> PinnedDeploy:
    name = entry.get("name")
    if "pins_config" in entry:
        path = entry["pins_config"]
        config = configs.get(path)
        if config is None:
            raise BenchmarkManifestError(f"set {name!r}: pins config {path!r} was not loaded")
        commit, images = config.get("frozen_deploy_commit"), config.get("frozen_image_ids")
        if not commit or not images:
            raise BenchmarkManifestError(f"set {name!r}: {path!r} pins no frozen deploy")
        return PinnedDeploy(str(commit), {str(k): str(v) for k, v in images.items()}, path)
    pins = entry.get("pins")
    if not pins or not pins.get("deploy_commit") or not pins.get("image_ids"):
        raise BenchmarkManifestError(f"set {name!r}: neither pins_config nor pins declared")
    return PinnedDeploy(
        str(pins["deploy_commit"]),
        {str(k): str(v) for k, v in pins["image_ids"].items()},
        str(pins["source"]),
    )


def benchmark_rolls(
    manifest: Mapping[str, Any], configs: Mapping[str, Mapping[str, Any]]
) -> tuple[BenchmarkRoll, ...]:
    """Every declared roll, in manifest order: each set's void launches, then its counted rolls.

    Refuses a cycle declared twice, a void roll without its reason, and a set whose pins cannot
    be read — each would put a row in the registry that says something the record does not.
    """
    rolls: list[BenchmarkRoll] = []
    seen: set[str] = set()

    def add(roll: BenchmarkRoll) -> None:
        if roll.cycle_id in seen:
            raise BenchmarkManifestError(f"{roll.cycle_id} is declared more than once")
        seen.add(roll.cycle_id)
        rolls.append(roll)

    for entry in manifest.get("sets", ()):
        name, record, stack = entry["name"], entry["record"], entry["stack"]
        pins = _pins(entry, configs)
        for void in entry.get("void", ()):
            if not void.get("reason"):
                raise BenchmarkManifestError(
                    f"set {name!r}: void {void.get('cycle')} has no reason"
                )
            add(
                BenchmarkRoll(
                    cycle_id=void["cycle"],
                    set_name=name,
                    record=record,
                    stack=stack,
                    roll=int(void["roll"]),
                    role=RollRole.VOID,
                    pins=None,
                    void_reason=void["reason"],
                )
            )
        for index, cycle_id in enumerate(entry.get("counted", ()), start=1):
            add(BenchmarkRoll(cycle_id, name, record, stack, index, RollRole.COUNTED, pins))
    return tuple(rolls)


# ---------------------------------------------------------------------------------------------
# Preflight and lineage
# ---------------------------------------------------------------------------------------------


def launched_counted_roll(notes: str | None) -> int | None:
    """The counted roll the driver's launch note declares, or ``None`` when it declares none."""
    match = _COUNTED_LAUNCH_NOTE.search(notes or "")
    return int(match.group(1)) if match else None


def cycle_stack(cycle: Cycle) -> str | None:
    """The stack a cycle ran: its override, else its request profile's applied default."""
    overrides = cycle.execution_overrides or {}
    defaults = cycle.applied_defaults or {}
    stack = overrides.get("build_profile") or defaults.get("build_profile")
    return str(stack) if stack else None


def preflight(
    roll: BenchmarkRoll, cycle: Cycle | None, evidence: CycleEvidence | None
) -> Preflight:
    """Whether ``roll`` can be re-graded from what the stores hold, and every reason it cannot."""
    if cycle is None:
        return Preflight((PreflightRefusal.NOT_IN_REGISTRY,), (f"{roll.cycle_id} not found",))
    refusals: list[PreflightRefusal] = []
    detail: list[str] = []
    launched = launched_counted_roll(cycle.notes)
    if launched != roll.roll:
        refusals.append(PreflightRefusal.NOT_LAUNCHED_AS_DECLARED)
        detail.append(f"declared {roll.role} roll {roll.roll}; launch note declares {launched}")
    stack = cycle_stack(cycle)
    if stack != roll.stack:
        refusals.append(PreflightRefusal.STACK_DISAGREES)
        detail.append(f"declared stack {roll.stack}; the cycle ran {stack}")
    if evidence is None or not evidence.runs:
        refusals.append(PreflightRefusal.NO_RUNS)
    elif not evidence.verification_summary_runs:
        refusals.append(PreflightRefusal.NO_VERIFICATION_SUMMARY)
        detail.append(f"no verification summary on any of {len(evidence.runs)} runs")
    return Preflight(tuple(refusals), tuple(detail))


def lineage_for(roll: BenchmarkRoll, cycle: Cycle) -> CodeLineage | None:
    """#80's fields where the cycle carries a commit, else the set's pins, else ``None``.

    A framework version without a commit does not name the code, so it does not win over pins;
    it is carried beside them.
    """
    if cycle.framework_git_sha:
        return CodeLineage(
            LineageSource.CYCLE_RECORD, cycle.framework_version, cycle.framework_git_sha, roll.pins
        )
    if roll.pins is not None:
        return CodeLineage(LineageSource.SET_PINS, cycle.framework_version, None, roll.pins)
    return None


# ---------------------------------------------------------------------------------------------
# The capture
# ---------------------------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    return value


def _assessment_record(assessment: CycleAssessment) -> dict[str, Any]:
    indicators = {}
    for dimension in ("outcome", "quality", "coordination", "efficiency"):
        for ind in getattr(assessment, dimension):
            entry: dict[str, Any] = {"dimension": dimension, "state": str(ind.state)}
            if ind.reason is not None:
                entry["reason"] = ind.reason
            else:
                entry["value"] = _jsonable(ind.value)
            entry["refs"] = len(ind.refs)
            indicators[ind.name] = entry
    reading = assessment.attribution
    attribution: dict[str, Any] = {"state": str(reading.state)}
    if reading.terminal_kind is not None:
        attribution["terminal_kind"] = str(reading.terminal_kind)
    if reading.attribution is not None:
        attribution["primary"] = _jsonable(reading.attribution.primary)
        attribution["contributing"] = [
            {"source": c.source, "value": c.value, "attribution": str(c.attribution)}
            for c in reading.attribution.contributing
        ]
    if reading.reason is not None:
        attribution["reason"] = reading.reason
    attribution["unrecorded"] = list(reading.unrecorded)
    return {
        "assessment_version": assessment.assessment_version,
        "attribution_registry_version": assessment.attribution_registry_version,
        "evidence_identity": assessment.evidence_identity,
        "indicators": indicators,
        "attribution": attribution,
    }


def row_record(row: BenchmarkRow) -> dict[str, Any]:
    """One row as the committed capture stores it: every indicator's state and value, the
    number of references it cited, and no reference ids (a re-grade resolves them again)."""
    roll = row.roll
    record: dict[str, Any] = {
        "cycle_id": roll.cycle_id,
        "set": roll.set_name,
        "record": roll.record,
        "stack": roll.stack,
        "roll": roll.roll,
        "role": str(roll.role),
    }
    if roll.void_reason is not None:
        record["void_reason"] = roll.void_reason
    record["gradeable"] = row.preflight.gradeable
    record["refusals"] = [str(r) for r in row.preflight.refusals]
    record["refusal_detail"] = list(row.preflight.detail)
    if row.series is not None:
        record["series"] = {
            "project_id": row.series.project_id,
            "squad_profile_id": row.series.squad_profile_id,
            "request_profile": row.series.request_profile,
        }
    if row.lineage is not None:
        lineage: dict[str, Any] = {
            "source": str(row.lineage.source),
            "framework_version": row.lineage.framework_version,
            "framework_git_sha": row.lineage.framework_git_sha,
        }
        if row.lineage.pins is not None:
            lineage["deploy_commit"] = row.lineage.pins.deploy_commit
            lineage["image_ids"] = dict(sorted(row.lineage.pins.image_ids.items()))
            lineage["pins_source"] = row.lineage.pins.source
        record["lineage"] = lineage
    else:
        record["lineage"] = None
    if row.assessment is not None:
        record["assessment"] = _assessment_record(row.assessment)
        record["unresolved_refs"] = [f"{r.kind}:{r.id}" for r in row.unresolved_refs]
    return record
