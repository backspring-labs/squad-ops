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

import base64
import binascii
import hashlib
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any

from squadops.sandbox.findings import READERS, FindingsReading, UnknownReader


class RevisionOrigin:
    """How content entered the workspace. §4.6: a revision is cut only when
    content crosses the sandbox boundary from outside an execution unit —
    warm-attempt dirty state never gets an id and is never referenceable."""

    SCAFFOLD_SEED = "scaffold_seed"
    AGENT_PATCH = "agent_patch"
    PROMOTED_OUTPUTS = "promoted_outputs"
    #: #734 Slice A: the executor's acceptance-workspace assembly (#643) —
    #: content crossing into a verification substrate, cut at dispatch so
    #: every acceptance verdict names the tree it ran against. Identity-only
    #: in 1.5 (nothing reconstructs from it until SIP-0102 steps 3-4).
    ACCEPTANCE_ASSEMBLY = "acceptance_assembly"
    #: SIP-0112 §8.2.2 (X-1, #2419): a Project's Git checkout at a pinned commit,
    #: seeded as the cycle's live tree by Project Lifecycle Management. The
    #: sandbox never runs Git: the commit lives in that SIP's revision-to-commit
    #: mapping, never on the revision.
    GIT_CHECKOUT = "git_checkout"

    ALL = frozenset(
        {SCAFFOLD_SEED, AGENT_PATCH, PROMOTED_OUTPUTS, ACCEPTANCE_ASSEMBLY, GIT_CHECKOUT}
    )
    #: Origins whose files are a repository's own tracked set (X-2, #2420): each one is
    #: content, whatever its name. A product that commits its package-lock.json or a built
    #: dist/ file names them, so the derived-state exclusion keeps out only what no
    #: revision names.
    TRACKED_TREE = frozenset({GIT_CHECKOUT})


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
    #: SIP-0112 §8.2.2, X-3a (#2421): a product's own declared command, such as a check its
    #: Development Configuration names, run against a pinned revision in a disposable copy
    #: (SIP-0102 §11d). The argv is the declaration's, never an agent's output.
    RUN_DECLARED_COMMAND = "run_declared_command"

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
            RUN_DECLARED_COMMAND,
        }
    )


#: A workspace file's content (X-2, #2420): text, or the raw bytes of a file that
#: isn't UTF-8 (an image, a font). Text is written and hashed as its UTF-8 encoding.
FileContent = str | bytes


def content_bytes(content: FileContent) -> bytes:
    """The bytes a file's content is written to disk and hashed as."""
    return content.encode("utf-8") if isinstance(content, str) else bytes(content)


def wire_files(files: Mapping[str, FileContent | None]) -> dict:
    """Content for the wire (X-2, #2420): text and deletions under ``files``, and each file
    that isn't UTF-8 base64-encoded under ``binary_files``. A text-only message carries no
    ``binary_files``, so it is what it was before bytes were carried. Both directions use it:
    the client's seeds and patches, and the service's revision reads (#2451's consumer)."""
    text: dict[str, str | None] = {}
    binary: dict[str, str] = {}
    for path, content in files.items():
        if isinstance(content, bytes):
            try:
                text[path] = content.decode("utf-8")
            except UnicodeDecodeError:
                binary[path] = base64.b64encode(content).decode("ascii")
        else:
            text[path] = content
    return {"files": text, **({"binary_files": binary} if binary else {})}


def decode_binary(binary_files: Mapping[str, str], *, alongside: Mapping) -> dict[str, bytes]:
    """The wire's base64-encoded binary files (X-2, #2420), refusing a path also sent as
    text: which content was meant is not the reader's to guess."""
    both = sorted(set(binary_files) & set(alongside))
    if both:
        raise ValueError(f"paths sent both as text and as binary: {both}")
    decoded: dict[str, bytes] = {}
    for path, encoded in binary_files.items():
        try:
            decoded[path] = base64.b64decode(encoded, validate=True)
        except binascii.Error as e:
            raise ValueError(f"binary file {path!r} is not valid base64: {e}") from e
    return decoded


def compute_revision_id(files: Mapping[str, FileContent], executable: Collection[str] = ()) -> str:
    """Content-addressed revision id — deterministic and order-independent over
    (path, content) pairs, so identical workspace content always pins the same
    revision (the §4.6 verification-pinning primitive). It hashes each file's
    bytes, so a text file and its UTF-8 encoding name the same revision, and
    every revision cut before bytes were carried (X-2) keeps its id.

    ``executable`` names the files whose executable bit is set (X-2, #2420). It
    joins the hash only when it names one, after every file and behind a NUL that
    no path can begin with, so a revision with no executable file keeps its id."""
    h = hashlib.sha256()
    for path in sorted(files):
        h.update(path.encode("utf-8"))
        h.update(b"\x00")
        h.update(hashlib.sha256(content_bytes(files[path])).digest())
    if executable:
        h.update(b"\x00executable")
        for path in sorted(executable):
            h.update(b"\x00" + path.encode("utf-8"))
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
        files: Mapping[str, FileContent],
        executable: Collection[str] = (),
        parent: WorkspaceRevision | None = None,
        created_at: str | None = None,
    ) -> WorkspaceRevision:
        """Cut a revision from workspace content at a §4.6 boundary."""
        return cls(
            revision_id=compute_revision_id(files, executable),
            cycle_id=cycle_id,
            origin=origin,
            parent_revision_id=parent.revision_id if parent else None,
            created_at=created_at,
        )

    def matches(self, files: Mapping[str, FileContent], executable: Collection[str] = ()) -> bool:
        """§4.6 verification pinning: True iff this exact content, and these
        executable files, are what the revision was cut from. Clean-room
        verification fails on a mismatch."""
        return compute_revision_id(files, executable) == self.revision_id

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


@dataclass(frozen=True)
class RevisionContent:
    """A pinned revision's files and executable bits, read from the live tree only while it
    matches the pin (contract 3; SIP-0112's E.4.3 captures a change back from it). The store
    keeps hashes, not contents, so this is the tree as it stands, held to the revision's ID."""

    revision: WorkspaceRevision
    files: Mapping[str, FileContent]
    executable: frozenset[str] = frozenset()


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


class CommandOutcome:
    """How a declared command ended (X-3a, #2421), so a caller tells a check that failed from
    one that never ran (SIP-0112 §8.3.1). Exit 127 and 126 are the shell's own "not found" and
    "not executable", which the container runtime reports the same way."""

    EXITED = "exited"
    SETUP_FAILED = "setup_failed"
    TIMEOUT = "timeout"
    COMMAND_NOT_FOUND = "command_not_found"
    COMMAND_NOT_EXECUTABLE = "command_not_executable"

    ALL = frozenset({EXITED, SETUP_FAILED, TIMEOUT, COMMAND_NOT_FOUND, COMMAND_NOT_EXECUTABLE})


@dataclass(frozen=True, kw_only=True)
class CommandResult(OperationResult):
    """A declared command's run (X-3a, #2421). ``outcome`` says how it ended. Only ``exited``
    means the command itself ran to an exit status: ``exit_code`` 0 is a pass and anything else
    a failure. ``failed_setup_step`` indexes the setup argv that stopped the run.

    Each tail says whether it was cut from a longer output (#2622), so a stored tail never reads
    as the whole of it. ``findings`` is the declared reader's reading of the command's whole
    output (#2609, ``squadops.sandbox.findings.FindingsReading.as_dict()``), present exactly when
    the request named a reader: unreadable, with why, when the command never ran to an exit."""

    command: tuple[str, ...] = ()
    outcome: str | None = None
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    failed_setup_step: int | None = None
    findings: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.outcome is not None and self.outcome not in CommandOutcome.ALL:
            raise ValueError(f"unknown command outcome: {self.outcome!r}")
        if self.ran and self.outcome is None:
            raise ValueError("a declared command that ran says how it ended")


def declared_argv(argv: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """A declared command's argv (X-3a, #2421): a non-empty sequence of non-empty strings, run
    as given, never through a shell. Anything else is the declaration's error."""
    # A string is a sequence of strings too: "ls -l" would run as ('l', 's', ' ', '-', 'l').
    if isinstance(argv, str) or not argv or not all(isinstance(a, str) and a for a in argv):
        raise ValueError(f"a declared command is a non-empty argv of non-empty strings: {argv!r}")
    return tuple(argv)


def declared_reader(reader: str | None) -> str | None:
    """A declared command's findings reader (#2609): none, or one of ``READERS``. Anything else
    is the declaration's error, refused before the command runs, never run unread."""
    if reader is not None and (not isinstance(reader, str) or reader not in READERS):
        raise UnknownReader(f"no findings reader {reader!r}; readers are {', '.join(READERS)}")
    return reader


def unread(reader: str | None, reason: str) -> dict[str, Any] | None:
    """A named reader's reading of a command that never ran to an exit: unreadable, with why, so
    a declared reader always answers and its absence never reads as no findings. ``None`` when
    no reader was named."""
    if reader is None:
        return None
    return FindingsReading(reader, READERS[reader], readable=False, reason=reason).as_dict()
