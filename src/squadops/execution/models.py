"""Execution sandbox domain models (SIP-0102 §4.4/§4.6 — phase 102.1 slice a).

The sandbox's agent-facing surface is typed operations returning structured
semantic results, never raw console text. Two semantics here are load-bearing:

- §4.6: every operation executes against, and records, an explicit workspace
  revision; verification pins a revision by content match.
- §4.4 ``ran=False``: environment unavailable is an environment-contract
  outcome, never a deliverable failure (the roll-4 class). The coherence rules
  in ``OperationResult.__post_init__`` make that conflation unrepresentable.

No wall-clock here — timestamps are caller-supplied (the replay doctrine, same
rule as ``BoundScaffoldRecord``).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass


class RevisionOrigin:
    """How content entered the workspace. §4.6: a revision is cut only when
    content crosses the sandbox boundary from outside an execution unit —
    warm-attempt dirty state never gets an id and is never referenceable."""

    SCAFFOLD_SEED = "scaffold_seed"
    AGENT_PATCH = "agent_patch"
    PROMOTED_OUTPUTS = "promoted_outputs"

    ALL = frozenset({SCAFFOLD_SEED, AGENT_PATCH, PROMOTED_OUTPUTS})


class OperationStatus:
    """Semantic outcome of a typed operation. ``NOT_RUN`` pairs with
    ``ran=False`` only — see ``OperationResult``."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NOT_RUN = "not_run"

    ALL = frozenset({SUCCEEDED, FAILED, NOT_RUN})


class OperationName:
    """The typed-operation vocabulary (§4.4). Policy-bearing operations, not
    renamed shell commands — an unknown name is a bug, not an extension point."""

    INSTALL_DEPENDENCIES = "install_dependencies"
    BUILD_FRONTEND = "build_frontend"
    RUN_BACKEND_TESTS = "run_backend_tests"
    START_APPLICATION = "start_application"
    STOP_APPLICATION = "stop_application"
    PROBE_HTTP_ENDPOINT = "probe_http_endpoint"
    APPLY_WORKSPACE_PATCH = "apply_workspace_patch"
    READ_BUILD_DIAGNOSTICS = "read_build_diagnostics"

    ALL = frozenset(
        {
            INSTALL_DEPENDENCIES,
            BUILD_FRONTEND,
            RUN_BACKEND_TESTS,
            START_APPLICATION,
            STOP_APPLICATION,
            PROBE_HTTP_ENDPOINT,
            APPLY_WORKSPACE_PATCH,
            READ_BUILD_DIAGNOSTICS,
        }
    )


def compute_revision_id(files: Mapping[str, str]) -> str:
    """Content-addressed revision id — deterministic and order-independent over
    (path, content) pairs, so identical workspace content always pins the same
    revision (the §4.6 verification-pinning primitive)."""
    h = hashlib.sha256()
    for path in sorted(files):
        h.update(path.encode("utf-8"))
        h.update(b"\x00")
        h.update(hashlib.sha256(files[path].encode("utf-8")).digest())
    return h.hexdigest()


@dataclass(frozen=True)
class WorkspaceRevision:
    """A pinned, content-addressed workspace state (§4.6). ``revision_id``
    derives from content alone; origin/parent are lineage metadata and never
    affect the id."""

    revision_id: str
    cycle_id: str
    origin: str
    parent_revision_id: str | None = None
    created_at: str | None = None  # ISO8601, caller-supplied

    def __post_init__(self) -> None:
        if self.origin not in RevisionOrigin.ALL:
            raise ValueError(f"unknown revision origin: {self.origin!r}")
        if self.parent_revision_id == self.revision_id:
            raise ValueError("a revision cannot be its own parent")

    @classmethod
    def cut(
        cls,
        *,
        cycle_id: str,
        origin: str,
        files: Mapping[str, str],
        parent: WorkspaceRevision | None = None,
        created_at: str | None = None,
    ) -> WorkspaceRevision:
        """Cut a revision from workspace content at a §4.6 boundary."""
        return cls(
            revision_id=compute_revision_id(files),
            cycle_id=cycle_id,
            origin=origin,
            parent_revision_id=parent.revision_id if parent else None,
            created_at=created_at,
        )

    def matches(self, files: Mapping[str, str]) -> bool:
        """§4.6 verification pinning: True iff this exact content is what the
        revision was cut from. Clean-room verification fails on a mismatch."""
        return compute_revision_id(files) == self.revision_id

    def to_dict(self) -> dict:
        return {
            "revision_id": self.revision_id,
            "cycle_id": self.cycle_id,
            "origin": self.origin,
            "parent_revision_id": self.parent_revision_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> WorkspaceRevision:
        return cls(
            revision_id=d["revision_id"],
            cycle_id=d["cycle_id"],
            origin=d["origin"],
            parent_revision_id=d.get("parent_revision_id"),
            created_at=d.get("created_at"),
        )


@dataclass(frozen=True, kw_only=True)
class OperationResult:
    """Common semantic envelope for every typed operation (§4.4).

    Coherence is enforced, not documented: ``ran=False`` ⇔ ``NOT_RUN``. An
    environment that could not execute the operation can never masquerade as a
    deliverable failure, and a run that executed can never be recorded as
    not-run."""

    operation: str
    workspace_revision_id: str
    status: str
    ran: bool
    duration_seconds: float | None = None
    exit_classification: str | None = None  # e.g. "nonzero_exit", "timeout"
    image_identity: str | None = None  # §7 item 4 — populated from 102.2
    environment_contract_id: str | None = None  # §7 item 4
    unavailable_reason: str | None = None
    raw_log_ref: str | None = None

    def __post_init__(self) -> None:
        if self.operation not in OperationName.ALL:
            raise ValueError(f"unknown operation: {self.operation!r}")
        if self.status not in OperationStatus.ALL:
            raise ValueError(f"unknown operation status: {self.status!r}")
        if not self.ran and self.status != OperationStatus.NOT_RUN:
            raise ValueError("a result that did not run must carry status 'not_run'")
        if self.ran and self.status == OperationStatus.NOT_RUN:
            raise ValueError("a result that ran cannot carry status 'not_run'")


def is_deliverable_failure(result: OperationResult) -> bool:
    """True only for failures the application owns. ``NOT_RUN`` (environment
    unavailable) never counts — it rolls up through SIP-0096 as an explicit
    environment-contract failure instead (§4.4)."""
    return result.ran and result.status == OperationStatus.FAILED


@dataclass(frozen=True, kw_only=True)
class InstallResult(OperationResult):
    manifest_hash: str | None = None
    lockfile_captured: bool = False
    cache_hit: bool = False  # recorded, never semantic (§4.7)


@dataclass(frozen=True, kw_only=True)
class BuildResult(OperationResult):
    diagnostics: tuple[str, ...] = ()
    warning_count: int = 0
    artifact_refs: tuple[str, ...] = ()
    failure_ownership_hint: str | None = None


@dataclass(frozen=True, kw_only=True)
class TestRunResult(OperationResult):
    framework: str | None = None
    exit_code: int | None = None
    output_tail: str = ""


@dataclass(frozen=True, kw_only=True)
class StartResult(OperationResult):
    process_identity: str | None = None
    endpoints: tuple[str, ...] = ()
    ready: bool = False
    startup_diagnostics: tuple[str, ...] = ()
    cleanup_handle: str | None = None


@dataclass(frozen=True, kw_only=True)
class StopResult(OperationResult):
    detail: str | None = None


@dataclass(frozen=True, kw_only=True)
class ProbeResult(OperationResult):
    probe_id: str
    observed_status_code: int | None = None
    detail: str | None = None


@dataclass(frozen=True, kw_only=True)
class PatchResult(OperationResult):
    new_revision_id: str
    files_changed: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class DiagnosticsResult(OperationResult):
    entries: tuple[str, ...] = ()
