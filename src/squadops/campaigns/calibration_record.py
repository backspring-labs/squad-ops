"""A Campaign's calibration on a repository-backed Project is a record, not a cycle (SIP-0109
§24bv point 1, §24cc; SIP-0112 H.4 point 4, H.6).

A repository-backed Project (one with a source, SIP-0112 E.4.1) has already been checked by its own
checks at its pinned commit: the inherited baseline (FR-20). So its Campaign's start builds
nothing. It records the Project's state as it stands:
- the reconciled commit and the Development Configuration revision;
- the commit's tree identity (contract 4), which becomes the accepted tree's identity;
- the inherited baseline captured at both, by a digest of its checks and each check's result;
- the derived profile's disclosed gaps (contract 8).

The record is written in the start's own control-log row, in its binding, so the start and the
record commit together or not at all. Its promotion and its decision follow, keyed by its id, and
a restart between them is re-heard (``CampaignProgress.rehear_calibration_records``).

A start that can't write a record is refused (409 ``CALIBRATION_REFUSED``), naming why, and
nothing is written: nothing has been launched, so nothing escalates. A sample application's
Campaign (no source) still launches its calibration cycle (§11), and nothing here reads it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from squadops.campaigns.models import (
    AcceptedTree,
    CampaignError,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
)
from squadops.cycles.models import (
    DerivedProfileNotFoundError,
    InheritedBaselineNotFoundError,
    Project,
)

if TYPE_CHECKING:
    from squadops.ports.cycles.project_registry import ProjectRegistryPort

CALIBRATION_RECORD_SCHEMA = "calibration-record/v1"

#: The start row's binding key that holds the record.
BINDING_KEY = "calibration_record"

#: The ending a record's decision row names where a cycle's names its ``CycleEnding``: no cycle
#: ended, and the decision read the record as an accepted calibration (§24bv point 1, row 5).
RECORDED_ENDING = "calibration_recorded"


class RefusalCause(StrEnum):
    """Why a start could not write its calibration record (§24bv point 1, §24cc)."""

    #: The Project isn't READY, or has no validated commit and configuration revision to record.
    PROJECT_NOT_READY = "project_not_ready"
    #: Its latest sync read upstream past the baseline with relevant drift (SIP-0112 H.2).
    DRIFT_UNRECONCILED = "drift_unreconciled"
    #: No inherited baseline, or no tree, is captured at the commit and revision.
    NO_BASELINE = "no_baseline"
    #: No derived profile is recorded at the Project's pin (contract 8, "When it's absent"). One
    #: derived at another commit or revision is never read in its place (SIP-0112 H.8's ``at=``).
    NO_PROFILE = "no_profile"
    #: A blocking gap stands: ``no_check_ran``, a blocking ``missing_toolchain``, or
    #: ``test_files_unclassed``, which H.6 makes a stop for ``campaigns``.
    BLOCKING_GAP = "blocking_gap"


class CalibrationRecordRefused(CampaignError):
    """A start refused because its calibration record can't be written. Refused before anything
    is written; ``details`` names the cause, and for a blocking gap each gap's id."""

    def __init__(self, cause: RefusalCause, message: str, **details: Any) -> None:
        self.cause = cause
        self.details = {"cause": cause.value, **details}
        super().__init__(message)


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


@dataclass(frozen=True)
class CalibrationRecord:
    """What a repository-backed Campaign's start recorded (§24bv point 1)."""

    record_id: str
    project_id: str
    commit: str
    development_configuration_revision: int
    #: The commit's tree identity (contract 4): the accepted tree's identity once promoted.
    tree_identity: str
    #: sha256 of the inherited baseline's checks as its document records them.
    baseline_digest: str
    #: Each check's id and result, in the baseline's order.
    baseline_checks: tuple[tuple[str, str], ...]
    #: The derived profile's disclosed gaps, each as contract 8 records it.
    disclosed_gaps: tuple[Mapping[str, Any], ...]

    @property
    def accepted_tree(self) -> AcceptedTree:
        """The tree a promotion of this record accepts: its commit's, naming the record."""
        return AcceptedTree(self.tree_identity, calibration_record_id=self.record_id)

    def to_binding(self) -> dict[str, Any]:
        return {
            "schema": CALIBRATION_RECORD_SCHEMA,
            "record_id": self.record_id,
            "project_id": self.project_id,
            "commit": self.commit,
            "development_configuration_revision": self.development_configuration_revision,
            "tree_identity": self.tree_identity,
            "baseline": {
                "digest": self.baseline_digest,
                "checks": [{"id": i, "result": r} for i, r in self.baseline_checks],
            },
            "disclosed_gaps": [dict(g) for g in self.disclosed_gaps],
        }

    @classmethod
    def from_binding(cls, doc: Mapping[str, Any]) -> CalibrationRecord:
        if doc.get("schema") != CALIBRATION_RECORD_SCHEMA:
            raise ValueError(f"{doc.get('schema')!r} is not a calibration record")
        return cls(
            record_id=str(doc["record_id"]),
            project_id=str(doc["project_id"]),
            commit=str(doc["commit"]),
            development_configuration_revision=int(doc["development_configuration_revision"]),
            tree_identity=str(doc["tree_identity"]),
            baseline_digest=str(doc["baseline"]["digest"]),
            baseline_checks=tuple(
                (str(c["id"]), str(c["result"])) for c in doc["baseline"]["checks"]
            ),
            disclosed_gaps=tuple(dict(g) for g in doc["disclosed_gaps"]),
        )


def recorded_calibration(log: Iterable[ControlLogEntry]) -> CalibrationRecord | None:
    """The record the campaign's applied start wrote, or ``None`` for a start that launched a
    calibration cycle (a sample application's, or one made before §24bv point 1)."""
    for entry in log:
        if entry.operation is ControlOperation.START and entry.outcome is ControlOutcome.APPLIED:
            recorded = entry.binding.get(BINDING_KEY)
            return CalibrationRecord.from_binding(recorded) if recorded else None
    return None


def _record_id(campaign_id: str, content: Mapping[str, Any]) -> str:
    """Derived from the campaign and what it records, so a replayed start computes the same one,
    and two campaigns on one commit never share one."""
    digest = hashlib.sha256(_canonical({"campaign_id": campaign_id, **content})).hexdigest()
    return f"calrec_{digest[:12]}"


async def record_for(
    registry: ProjectRegistryPort, project: Project, *, campaign_id: str
) -> CalibrationRecord:
    """The calibration record ``project``'s state allows, or :class:`CalibrationRecordRefused`
    naming the first cause that stops it, in §24bv point 1's order. Reads only; writes nothing."""
    # deferred (pair): squadops.projects imports this package at load (workspaces' FileTree)
    from squadops.projects.derived_profile import DISCLOSED

    # deferred (pair): squadops.projects imports this package at load
    from squadops.projects.sync import unreconciled

    pid = project.project_id
    if not project.lifecycle_status.accepts_cycles:
        raise CalibrationRecordRefused(
            RefusalCause.PROJECT_NOT_READY,
            f"Project {pid} is {project.lifecycle_status.value}: a Campaign's calibration record "
            "needs it READY",
        )
    commit = project.development_baseline_commit
    revision = project.development_configuration_revision
    if commit is None or revision is None:
        raise CalibrationRecordRefused(
            RefusalCause.PROJECT_NOT_READY,
            f"Project {pid} needs its source validated and a Development Configuration recorded "
            "before a Campaign calibrates on it (E.4.2)",
        )
    finding = unreconciled(await registry.source_syncs(pid), commit)
    if finding is not None:
        raise CalibrationRecordRefused(
            RefusalCause.DRIFT_UNRECONCILED,
            f"Project {pid}'s upstream is at {finding['upstream_commit']}, past its baseline "
            f"{commit}, with {', '.join(finding['drift']['relevant'])} changed (projects sync): "
            "reconcile it at the new commit first (squadops projects validate, configure, "
            "baseline --capture)",
            upstream_commit=finding["upstream_commit"],
        )
    try:
        baseline = await registry.get_inherited_baseline(pid)
    except InheritedBaselineNotFoundError:
        baseline = None
    if baseline is None or (baseline.commit, baseline.development_configuration_revision) != (
        commit,
        revision,
    ):
        held = (
            "none"
            if baseline is None
            else f"{baseline.commit}, revision {baseline.development_configuration_revision}"
        )
        raise CalibrationRecordRefused(
            RefusalCause.NO_BASELINE,
            f"Project {pid}'s inherited baseline is {held}; its calibration record is at "
            f"{commit}, revision {revision}: capture the baseline there first "
            "(squadops projects baseline --capture)",
        )
    try:
        # SIP-0112 H.8: the profile at the Project's pin, as prepare_cycle reads a Cycle's.
        profile = await registry.get_derived_profile(pid, at=(commit, revision))
    except DerivedProfileNotFoundError as e:
        raise CalibrationRecordRefused(
            RefusalCause.NO_PROFILE,
            f"Project {pid} has no derived profile at its pin, {commit}, revision {revision} "
            f"({e}): capture the baseline there again to derive one (SIP-0112 H.6)",
        ) from e
    if profile.blocking:
        named = "; ".join(
            f"{g.id}{f' ({g.subject})' if g.subject else ''}: {g.reason}; closes by {g.closes_by}"
            for g in profile.blocking
        )
        raise CalibrationRecordRefused(
            RefusalCause.BLOCKING_GAP,
            f"Project {pid}'s derived profile names a blocking gap: {named}",
            gaps=[g.id for g in profile.blocking],
        )
    trees = {m.tree_identity for m in await registry.source_mappings(pid) if m.commit == commit}
    if len(trees) != 1:
        raise CalibrationRecordRefused(
            RefusalCause.NO_BASELINE,
            f"Project {pid} has {len(trees)} tree identities recorded at {commit}, not one: its "
            "baseline capture records the tree it seeded (contract 3), so capture it again",
        )
    checks = [c.to_document() for c in baseline.checks]
    tree = next(iter(trees))
    digest = hashlib.sha256(_canonical(checks)).hexdigest()
    results = tuple((str(c["id"]), str(c["result"])) for c in checks)
    disclosed = tuple(g for g in profile.to_document()["gaps"] if g["kind"] == DISCLOSED)
    content = {
        "project_id": pid,
        "commit": commit,
        "development_configuration_revision": revision,
        "tree_identity": tree,
        "baseline_digest": digest,
        "baseline_checks": results,
        "disclosed_gaps": disclosed,
    }
    return CalibrationRecord(
        record_id=_record_id(campaign_id, content),
        project_id=pid,
        commit=commit,
        development_configuration_revision=revision,
        tree_identity=tree,
        baseline_digest=digest,
        baseline_checks=results,
        disclosed_gaps=disclosed,
    )
