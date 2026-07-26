"""Operation evidence journal (SIP-0102 §7 item 11 / #427 — phase 102.1 slice b)."""

from squadops.execution.evidence import OperationEvidenceJournal, result_to_dict
from squadops.execution.models import BuildResult, OperationName, OperationStatus


def _result(**overrides) -> BuildResult:
    base = {
        "operation": OperationName.BUILD_FRONTEND,
        "workspace_revision_id": "rev1",
        "status": OperationStatus.SUCCEEDED,
        "ran": True,
    }
    return BuildResult(**{**base, **overrides})


def test_records_persist_across_journal_instances(tmp_path):
    """Bug caught: buffered/in-memory evidence — an orchestration crash after
    the op would lose the result (#427's exact class)."""
    OperationEvidenceJournal(tmp_path).record("cyc_1", _result())
    entries = OperationEvidenceJournal(tmp_path).read("cyc_1")
    assert len(entries) == 1
    assert entries[0]["operation"] == OperationName.BUILD_FRONTEND
    assert entries[0]["result_type"] == "BuildResult"


def test_truncated_final_line_does_not_poison_the_journal(tmp_path):
    """Bug caught: one crash-truncated line making every prior entry
    unreadable — evidence must degrade by at most the line being written."""
    journal = OperationEvidenceJournal(tmp_path)
    journal.record("cyc_1", _result())
    journal.record("cyc_1", _result(status=OperationStatus.FAILED))
    path = tmp_path / "cyc_1" / "evidence" / "operations.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write('{"operation": "build_fr')  # crash mid-write
    entries = journal.read("cyc_1")
    assert [e["status"] for e in entries] == ["succeeded", "failed"]


def test_result_to_dict_carries_op_specific_fields(tmp_path):
    """Bug caught: serialization flattening subclass fields away — journal
    readers could no longer interpret op-specific evidence."""
    payload = result_to_dict(_result(warning_count=3, diagnostics=("W1",)))
    assert payload["warning_count"] == 3
    assert payload["diagnostics"] == ("W1",)
    assert payload["result_type"] == "BuildResult"
