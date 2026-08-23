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


def _store(
    tmp_path,
    art_id,
    filename,
    content,
    producing,
    created,
    artifact_type="source",
    emission_status=None,
):
    d = tmp_path / art_id
    (d / Path(filename).parent).mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(content)
    metadata = {"producing_task_type": producing}
    if emission_status:
        metadata["emission_status"] = emission_status
    (d / "metadata.json").write_text(
        json.dumps(
            {
                "artifact_id": art_id,
                "artifact_type": artifact_type,
                "filename": filename,
                "created_at": created,
                "metadata": metadata,
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


def test_failed_emission_never_selected_even_as_only_copy(tmp_path):
    """#971 banks failed emissions; the auditor must never assemble one.

    The dangerous shape is not a failed emission losing to a good one — it is a
    failed emission being the ONLY copy of a file, which happens whenever the run
    dies before anything re-emits it. Naive latest-per-filename would then audit
    known-bad bytes and report on an application the run never actually produced.
    """
    _store(
        tmp_path,
        "art_failed",
        "app/api/runs/route.ts",
        "export async function POST(req) { const body = await req.js",
        "development.develop",
        "2026-01-01T10:00",
        emission_status="failed",
    )
    _store(
        tmp_path,
        "art_ok",
        "app/page.tsx",
        "export default function Page() { return null }",
        "development.develop",
        "2026-01-01T10:01",
    )

    selected = _mod._select_deliverable(tmp_path)

    assert "app/api/runs/route.ts" not in selected
    assert selected == {"app/page.tsx": "export default function Page() { return null }"}


def test_failed_emission_loses_to_the_successful_retry(tmp_path):
    """The pair is banked; only the passing member is deliverable.

    Ordering must not be what saves this: the failed emission is stored LATER than
    a hypothetical earlier good one in some retry shapes, so the exclusion has to be
    by marker, not by time.
    """
    _store(
        tmp_path,
        "art_ok",
        "app/api/runs/route.ts",
        "GOOD",
        "development.develop",
        "2026-01-01T10:00",
    )
    _store(
        tmp_path,
        "art_failed",
        "app/api/runs/route.ts",
        "TRUNCATED",
        "development.develop",
        "2026-01-01T11:00",
        emission_status="failed",
    )

    assert _mod._select_deliverable(tmp_path) == {"app/api/runs/route.ts": "GOOD"}
