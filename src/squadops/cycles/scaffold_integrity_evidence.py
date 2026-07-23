"""SIP-0100 Phase 3 (Task 3.3) — structured scaffold write-authority evidence.

Turns the executor's bare "frozen path restored" WARNING into a structured,
queryable record — one per authority event. Review #10 requires three cases be
kept *separate*, never collapsed into one message; this model separates them on
two axes:

- ``kind`` — **what class of event this is**:
  - ``attempted_emission`` — a producer emitted a scaffold-owned path (recorded
    with the 0.5 reason code: ``frozen_path_emission`` / ``unauthorized_slot_emission``
    / ``undeclared_path_emission``). Producer-correctable.
  - ``post_write_integrity_fault`` — frozen bytes changed *after* materialization
    with no accepted emission (``post_write_integrity_fault``, plan D4): a system
    fault (bypass / concurrent writer / bug), not producer misconduct.
- ``disposition`` — **what the enforcer did** (``restored`` / ``dropped`` /
  ``stopped`` / ``allowed``): the *system restoration*, never conflated with the
  attempt that triggered it.

Pure model (no I/O): the executor builds and emits these. Reason codes are taken
from ``task_outcome.ContractComplianceViolation`` — this module never mints its own.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from squadops.cycles.bound_scaffold_record import BoundScaffoldRecord
from squadops.cycles.task_outcome import ContractComplianceViolation
from squadops.cycles.write_authorization import normalize_ws_path

# ``kind`` values — the event-class axis (Review #10). Kept distinct from the 0.5
# reason codes (which say *why* a path was unauthorized) and from ``disposition``
# (which says what the system did).
KIND_ATTEMPTED_EMISSION = "attempted_emission"
KIND_POST_WRITE_INTEGRITY_FAULT = "post_write_integrity_fault"

# ``disposition`` values — the system-action axis.
DISPOSITION_RESTORED = "restored"
DISPOSITION_DROPPED = "dropped"
DISPOSITION_STOPPED = "stopped"
DISPOSITION_ALLOWED = "allowed"


def sha256_of(content: Any) -> str | None:
    """SHA-256 hex of artifact content (``str``/``bytes``), or ``None`` if not hashable.

    Shares the encoding convention with materialization: text is UTF-8. Non-text,
    non-bytes content (a structured artifact with no file body) hashes to ``None``."""
    if isinstance(content, str):
        data: bytes = content.encode("utf-8")
    elif isinstance(content, (bytes, bytearray)):
        data = bytes(content)
    else:
        return None
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class ScaffoldIntegrityEvidence:
    """One scaffold write-authority event (plan Task 3.3 / review #10).

    Immutable. ``to_dict`` is the wire/log/event shape; field order there is stable
    so downstream (run report, telemetry, 3.4 counter) can rely on it.
    """

    # Producer + stage
    producer_task_id: str
    producer_task_type: str
    stage: str  # where enforcement ran, e.g. "artifact_storage"
    # Event-class axis (Review #10) + the 0.5 reason code
    kind: str
    violation_code: str
    # What was attempted
    attempted_path: str  # raw, exactly as the producer emitted it
    normalized_path: str | None  # D7 canonical target (None = unnormalizable/escaping)
    # Bound identity — which scaffold binding this was evaluated against
    bound_run_id: str
    bound_attempt_id: str
    manifest_hash: str
    # Integrity comparison
    expected_sha256: str | None  # scaffold's bytes for a frozen path
    attempted_sha256: str | None  # the producer's emitted bytes
    # Disposition + retention
    disposition: str  # system action taken (never conflated with the attempt)
    siblings_retained: int  # sibling artifacts in the SAME response left untouched
    # Set by 3.4 when a targeted correction is issued for this violation.
    correction_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "producer_task_id": self.producer_task_id,
            "producer_task_type": self.producer_task_type,
            "stage": self.stage,
            "kind": self.kind,
            "violation_code": self.violation_code,
            "attempted_path": self.attempted_path,
            "normalized_path": self.normalized_path,
            "bound_run_id": self.bound_run_id,
            "bound_attempt_id": self.bound_attempt_id,
            "manifest_hash": self.manifest_hash,
            "expected_sha256": self.expected_sha256,
            "attempted_sha256": self.attempted_sha256,
            "disposition": self.disposition,
            "siblings_retained": self.siblings_retained,
            "correction_requested": self.correction_requested,
        }


def frozen_restore_evidence(
    *,
    producer_task_id: str,
    producer_task_type: str,
    record: BoundScaffoldRecord,
    attempted_path: str,
    normalized_path: str,
    attempted_content: Any,
    siblings_retained: int,
    stage: str = "artifact_storage",
) -> ScaffoldIntegrityEvidence:
    """Build the evidence for the current 2.4 case: a producer emitted a frozen path
    and the enforcer **restored** it to the bound scaffold bytes.

    ``expected_sha256`` comes from the bound record's persisted hash for that path
    (D2 — the authority is the bound bytes, never a re-derivation). Frozen paths are
    normalized to the D7 canonical identity so the lookup matches ``normalized_path``,
    exactly as the enforcer keys its restore map."""
    frozen_sha = {
        n: fa.sha256 for fa in record.frozen if (n := normalize_ws_path(fa.path)) is not None
    }
    return ScaffoldIntegrityEvidence(
        producer_task_id=producer_task_id,
        producer_task_type=producer_task_type,
        stage=stage,
        kind=KIND_ATTEMPTED_EMISSION,
        violation_code=ContractComplianceViolation.FROZEN_PATH_EMISSION,
        attempted_path=attempted_path,
        normalized_path=normalized_path,
        bound_run_id=record.run_id,
        bound_attempt_id=record.attempt_id,
        manifest_hash=record.manifest_hash,
        expected_sha256=frozen_sha.get(normalized_path),
        attempted_sha256=sha256_of(attempted_content),
        disposition=DISPOSITION_RESTORED,
        siblings_retained=siblings_retained,
    )


def unauthorized_slot_evidence(
    *,
    producer_task_id: str,
    producer_task_type: str,
    record: BoundScaffoldRecord,
    attempted_path: str,
    normalized_path: str,
    attempted_content: Any,
    siblings_retained: int,
    stage: str = "artifact_storage",
) -> ScaffoldIntegrityEvidence:
    """Build the evidence for the 3.1 case: a producer emitted a path that is writable *in
    principle* but belongs to a **different** producer's slot (e.g. a QA task writing dev's
    ``routes.py``). The enforcer **drops** the emission — the owning producer's version stays.

    ``expected_sha256`` is ``None``: a fill slot has no canonical scaffold bytes to compare
    against (its legitimate content is the owner's implementation, not a scaffold constant).
    Only the attempted bytes are recorded, for forensics."""
    return ScaffoldIntegrityEvidence(
        producer_task_id=producer_task_id,
        producer_task_type=producer_task_type,
        stage=stage,
        kind=KIND_ATTEMPTED_EMISSION,
        violation_code=ContractComplianceViolation.UNAUTHORIZED_SLOT_EMISSION,
        attempted_path=attempted_path,
        normalized_path=normalized_path,
        bound_run_id=record.run_id,
        bound_attempt_id=record.attempt_id,
        manifest_hash=record.manifest_hash,
        expected_sha256=None,
        attempted_sha256=sha256_of(attempted_content),
        disposition=DISPOSITION_DROPPED,
        siblings_retained=siblings_retained,
    )
