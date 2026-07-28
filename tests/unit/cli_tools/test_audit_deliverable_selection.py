"""The FAY auditor's acceptance-aware artifact selection (audit_delivered_app).

The rule mirrors the executor's (pf-31 Fix E): per filename, latest artifact
whose producing_task_type is not a repair-candidate type. pf-54 is the trap
that makes this worth pinning: naive last-wins-by-time selects a REJECTED
repair that happens to boot, flipping the audit verdict from FAIL to PASS.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "audit_delivered_app.py"
_spec = importlib.util.spec_from_file_location("audit_delivered_app", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["audit_delivered_app"] = _mod
_spec.loader.exec_module(_mod)


def _store(tmp_path, art_id, filename, content, producing, created, artifact_type="source"):
    d = tmp_path / art_id
    (d / Path(filename).parent).mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(content)
    (d / "metadata.json").write_text(
        json.dumps(
            {
                "artifact_id": art_id,
                "artifact_type": artifact_type,
                "filename": filename,
                "created_at": created,
                "metadata": {"producing_task_type": producing},
            }
        )
    )


def test_rejected_repair_never_wins_even_when_newest(tmp_path):
    # The pf-54 shape: accepted original (broken) + newer rejected repairs (bootable).
    _store(
        tmp_path,
        "art_a",
        "backend/routes.py",
        "ACCEPTED",
        "development.develop",
        "2026-01-01T10:00",
    )
    _store(
        tmp_path,
        "art_b",
        "backend/routes.py",
        "REJECTED-1",
        "development.correction_repair",
        "2026-01-01T11:00",
    )
    _store(
        tmp_path,
        "art_c",
        "backend/routes.py",
        "REJECTED-2",
        "development.correction_repair",
        "2026-01-01T12:00",
    )
    files = _mod._select_deliverable(tmp_path)
    assert files["backend/routes.py"] == "ACCEPTED"


def test_accepted_repair_restored_under_task_type_wins(tmp_path):
    # The pf-50 shape: the #389 swap re-stores the accepted patch under the
    # failing task's own type — that copy IS the deliverable.
    _store(
        tmp_path,
        "art_a",
        "backend/routes.py",
        "ORIGINAL",
        "development.develop",
        "2026-01-01T10:00",
    )
    _store(
        tmp_path,
        "art_b",
        "backend/routes.py",
        "CANDIDATE",
        "development.correction_repair",
        "2026-01-01T11:00",
    )
    _store(tmp_path, "art_c", "backend/routes.py", "ACCEPTED-SWAP", "qa.test", "2026-01-01T11:01")
    files = _mod._select_deliverable(tmp_path)
    assert files["backend/routes.py"] == "ACCEPTED-SWAP"


def test_non_workspace_types_excluded(tmp_path):
    _store(
        tmp_path, "art_a", "backend/routes.py", "CODE", "development.develop", "2026-01-01T10:00"
    )
    _store(
        tmp_path,
        "art_b",
        "report.md",
        "REPORT",
        "qa.test",
        "2026-01-01T11:00",
        artifact_type="document",
    )
    files = _mod._select_deliverable(tmp_path)
    assert "report.md" not in files
    assert files == {"backend/routes.py": "CODE"}
