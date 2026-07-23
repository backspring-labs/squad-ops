"""SIP-0100 Task 3.3 — scaffold write-authority evidence model."""

from __future__ import annotations

import hashlib

from squadops.cycles.bound_scaffold_record import BoundScaffoldRecord, FrozenArtifact
from squadops.cycles.scaffold_integrity_evidence import (
    DISPOSITION_RESTORED,
    KIND_ATTEMPTED_EMISSION,
    frozen_restore_evidence,
    sha256_of,
)
from squadops.cycles.task_outcome import ContractComplianceViolation


def _record(*frozen: FrozenArtifact) -> BoundScaffoldRecord:
    return BoundScaffoldRecord(
        run_id="run_1",
        attempt_id="att_1",
        stack="fullstack_fastapi_react",
        manifest_hash="mh_abc",
        contract_hash="ch",
        expander_id="exp",
        created_at="",
        frozen=tuple(frozen),
        fill_slots=("backend/routes.py",),
        qa_namespace=("backend/tests/",),
    )


def _frozen(path: str, content: str) -> FrozenArtifact:
    return FrozenArtifact(
        path=path, sha256=hashlib.sha256(content.encode()).hexdigest(), content=content
    )


def test_frozen_restore_evidence_captures_the_full_record():
    rec = _record(_frozen("backend/main.py", "SCAFFOLD BYTES"))
    ev = frozen_restore_evidence(
        producer_task_id="t1",
        producer_task_type="qa.test",
        record=rec,
        attempted_path="./backend/main.py",  # un-normalized as emitted
        normalized_path="backend/main.py",
        attempted_content="QA OVERWRITE",
        siblings_retained=3,
    )
    assert ev.violation_code == ContractComplianceViolation.FROZEN_PATH_EMISSION
    assert ev.kind == KIND_ATTEMPTED_EMISSION
    assert ev.disposition == DISPOSITION_RESTORED
    assert ev.producer_task_type == "qa.test"
    assert ev.attempted_path == "./backend/main.py"  # raw preserved
    assert ev.normalized_path == "backend/main.py"
    assert ev.bound_run_id == "run_1"
    assert ev.bound_attempt_id == "att_1"
    assert ev.manifest_hash == "mh_abc"
    assert ev.siblings_retained == 3
    assert ev.correction_requested is False  # 3.4 populates this
    # Expected hash is the bound record's persisted scaffold hash; attempted is the emitted bytes.
    assert ev.expected_sha256 == hashlib.sha256(b"SCAFFOLD BYTES").hexdigest()
    assert ev.attempted_sha256 == hashlib.sha256(b"QA OVERWRITE").hexdigest()


def test_expected_hash_matches_via_normalized_frozen_path():
    """The record stores an un-normalized frozen path; the lookup must still resolve it so the
    expected hash is populated (else every restore would report expected=None)."""
    rec = _record(_frozen("./backend/main.py", "S"))  # stored with a leading ./
    ev = frozen_restore_evidence(
        producer_task_id="t",
        producer_task_type="development.develop",
        record=rec,
        attempted_path="backend/main.py",
        normalized_path="backend/main.py",
        attempted_content="X",
        siblings_retained=0,
    )
    assert ev.expected_sha256 == hashlib.sha256(b"S").hexdigest()


def test_unhashable_attempted_content_yields_none_hash():
    """A structured artifact with no text/bytes body must not crash evidence building."""
    rec = _record(_frozen("backend/main.py", "S"))
    ev = frozen_restore_evidence(
        producer_task_id="t",
        producer_task_type="development.develop",
        record=rec,
        attempted_path="backend/main.py",
        normalized_path="backend/main.py",
        attempted_content={"structured": "no body"},
        siblings_retained=0,
    )
    assert ev.attempted_sha256 is None
    assert ev.expected_sha256 is not None  # the scaffold side is still known


def test_to_dict_is_stable_and_complete():
    rec = _record(_frozen("conftest.py", "client fixture"))
    d = frozen_restore_evidence(
        producer_task_id="t",
        producer_task_type="qa.test",
        record=rec,
        attempted_path="conftest.py",
        normalized_path="conftest.py",
        attempted_content="tampered",
        siblings_retained=1,
    ).to_dict()
    assert set(d) == {
        "producer_task_id",
        "producer_task_type",
        "stage",
        "kind",
        "violation_code",
        "attempted_path",
        "normalized_path",
        "bound_run_id",
        "bound_attempt_id",
        "manifest_hash",
        "expected_sha256",
        "attempted_sha256",
        "disposition",
        "siblings_retained",
        "correction_requested",
    }
    assert d["stage"] == "artifact_storage"


def test_sha256_of_handles_str_bytes_and_non_hashable():
    assert sha256_of("abc") == hashlib.sha256(b"abc").hexdigest()
    assert sha256_of(b"abc") == hashlib.sha256(b"abc").hexdigest()
    assert sha256_of("abc") == sha256_of(b"abc")  # str/bytes converge on UTF-8
    assert sha256_of(None) is None
    assert sha256_of(42) is None
