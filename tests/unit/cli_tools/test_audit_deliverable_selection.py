"""The FAY auditor's deliverable selection (audit_delivered_app).

For a run's own files the rule mirrors the executor's (pf-31 Fix E): per filename, latest
artifact whose producing_task_type is not a repair-candidate type. pf-54 is the trap that makes
this worth pinning: naive last-wins-by-time selects a REJECTED repair that happens to boot,
flipping the audit verdict from FAIL to PASS. A promoted campaign increment is its accepted
tree instead (#2310), selected as the release capture selects it.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_DEV = Path(__file__).resolve().parents[3] / "scripts" / "dev"
_spec = importlib.util.spec_from_file_location(
    "audit_delivered_app", _DEV / "audit_delivered_app.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["audit_delivered_app"] = _mod
_spec.loader.exec_module(_mod)
# The audit selects through the capture's module, imported by name when it runs.
sys.path.insert(0, str(_DEV))


@pytest.fixture
def tmp_path(tmp_path, monkeypatch):
    """The vault root, ``<main>/data/artifacts``, as the capture reads it. Patched on the module
    the audit's import resolves to now: another test file may have registered its own copy."""
    capture = importlib.import_module("capture_delivered_app")
    vault = tmp_path / "data" / "artifacts"
    monkeypatch.setattr(capture, "VAULT", vault)
    monkeypatch.setattr(capture, "MAIN", tmp_path)
    return vault


def _store(
    vault,
    art_id,
    filename,
    content,
    producing,
    created,
    artifact_type="source",
    emission_status=None,
    cycle="cyc",
    run="run",
    scaffold_seeded=False,
):
    d = vault / "group_run" / cycle / run / art_id
    (d / Path(filename).parent).mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(content)
    metadata = {"producing_task_type": producing}
    if emission_status:
        metadata["emission_status"] = emission_status
    if scaffold_seeded:
        metadata["scaffold_seeded"] = True
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


def _select(vault, cycle="cyc", run="run"):
    files, _how = _mod._select_deliverable("group_run", cycle, run)
    return files


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
    files = _select(tmp_path)
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
    files = _select(tmp_path)
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
    files = _select(tmp_path)
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

    selected = _select(tmp_path)

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

    assert _select(tmp_path) == {"app/api/runs/route.ts": "GOOD"}


def test_a_promoted_increment_is_audited_as_its_accepted_tree_never_its_runs_stubs(tmp_path):
    """#2310, found by #2202's comparison: the increment changed only a view, so its run stored
    the scaffold's stub of ``backend/routes.py``, and its accepted tree named the calibration's
    working file. Bug caught: the run-only selection audited the stub, every route answering 501,
    while the cycle's own verification had passed on the real tree."""
    _store(
        tmp_path,
        "art_real",
        "backend/routes.py",
        "SORTS",
        "qa.test",
        "2026-10-14T22:46",
        cycle="cyc_cal",
        run="run_c",
    )
    _store(
        tmp_path,
        "art_stub",
        "backend/routes.py",
        "raise 501",
        "",
        "2026-10-14T23:00",
        cycle="cyc_inc",
        run="run_i",
        scaffold_seeded=True,
    )
    _store(
        tmp_path,
        "art_view",
        "frontend/src/views/RunList.jsx",
        "SHOWS DATETIME",
        "development.develop",
        "2026-10-14T23:02",
        cycle="cyc_inc",
        run="run_i",
    )
    tree = {"backend/routes.py": "art_real", "frontend/src/views/RunList.jsx": "art_view"}
    _store(
        tmp_path,
        "art_tree",
        "accepted_tree.json",
        json.dumps(tree),
        "",
        "2026-10-14T23:04",
        artifact_type="accepted_tree",
        cycle="cyc_inc",
        run="run_i",
    )

    files, how = _mod._select_deliverable("group_run", "cyc_inc", "run_i")

    assert files == {
        "backend/routes.py": "SORTS",
        "frontend/src/views/RunList.jsx": "SHOWS DATETIME",
    }
    assert how.startswith("the cycle's accepted tree art_tree")


def test_an_accepted_tree_the_vault_cannot_complete_is_refused_by_the_file_it_lacks(tmp_path):
    """Bug caught: an audit of a partial tree, booted with the missing file silently absent and
    reported as the app's failure (or worse, its pass)."""
    _store(
        tmp_path,
        "art_tree",
        "accepted_tree.json",
        json.dumps({"backend/routes.py": "art_gone"}),
        "",
        "2026-10-14T23:04",
        artifact_type="accepted_tree",
        cycle="cyc_inc",
        run="run_i",
    )

    with pytest.raises(SystemExit, match="backend/routes.py"):
        _mod._select_deliverable("group_run", "cyc_inc", "run_i")
