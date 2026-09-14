"""The pre-memory rejection baseline emitter, over a real vault (#1562).

Entry point: the script's ``_cycle_baseline`` over a real ``FilesystemArtifactVault``, the port
the deploy's vault implements. The script had never imported, so it is loaded by path here and
an import break fails CI the day it lands.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from squadops.cycles.models import ArtifactRef
from tests.unit.capabilities._stack_fixtures import manifest_dict_for_stack

REPO = Path(__file__).resolve().parents[3]
T0 = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def emitter():
    path = REPO / "scripts" / "dev" / "emit_rejection_baseline.py"
    spec = importlib.util.spec_from_file_location("emit_rejection_baseline", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["emit_rejection_baseline"] = module
    spec.loader.exec_module(module)
    return module


async def _store(vault, artifact_id, run_id, artifact_type, filename, content):
    await vault.store(
        ArtifactRef(
            artifact_id=artifact_id,
            project_id="group_run",
            artifact_type=artifact_type,
            filename=filename,
            content_hash="",
            size_bytes=0,
            media_type="text/plain",
            created_at=T0,
            cycle_id="cyc_1",
            run_id=run_id,
        ),
        content.encode("utf-8"),
    )


@pytest.fixture
async def vault(tmp_path):
    vault = FilesystemArtifactVault(tmp_path / "vault")
    # Framing run 1 refused at the plan gate; framing run 2 (the re-roll) authored a manifest
    # after one rejected attempt; the implementation run stored an ordinary document.
    await _store(
        vault,
        "art_rej",
        "run_f1",
        "rejection_record",
        "rejection_record.json",
        json.dumps({"gate": "progress_plan_review", "classes": {"validate_criteria_scope": 2}}),
    )
    manifest = manifest_dict_for_stack("fullstack_fastapi_react")
    manifest["provenance"] = {"attempts": 2, "revisions": [{"attempt": 1, "classes": {"lint": 1}}]}
    await _store(
        vault,
        "art_man",
        "run_f2",
        "interface_manifest",
        "interface_manifest.yaml",
        yaml.safe_dump(manifest),
    )
    await _store(vault, "art_doc", "run_i1", "document", "notes.md", "implementation notes")
    return vault


async def test_a_cycles_classes_attempts_and_framing_rerolls_come_from_its_stored_records(
    emitter, vault
):
    """Bug caught: the implementation run counted as a framing re-roll (every cycle read at
    least one), or a record's classes lost between the vault and the baseline."""
    baseline = await emitter._cycle_baseline(vault, "cyc_1", project_id="group_run")

    assert baseline.to_dict() == {
        "cycle_id": "cyc_1",
        "attempts": 2,
        "rerolls": 1,
        "classes": [
            {"class": "lint", "occurrences": 1, "attempts": 2, "rerolls": 1},
            {"class": "validate_criteria_scope", "occurrences": 2, "attempts": 2, "rerolls": 1},
        ],
    }


@pytest.mark.parametrize(
    ("break_it", "names"),
    [
        (lambda root: next(root.rglob("rejection_record.json")).write_text("{not json"), "art_rej"),
        (lambda root: (root / "_index.json").write_text("{}"), "could not be read"),
    ],
    ids=["a record that is not JSON", "a vault that cannot resolve the record"],
)
async def test_an_input_the_baseline_cannot_read_stops_the_emission(
    emitter, vault, tmp_path, break_it, names
):
    """#1562. Bug caught: an unread rejection record skipped, so the emitted baseline reads zero
    classes — a hollow capture indistinguishable from a cycle that was never refused."""
    break_it(tmp_path / "vault")
    reread = FilesystemArtifactVault(tmp_path / "vault")

    with pytest.raises(emitter.BaselineInputUnreadable, match=names):
        await emitter._cycle_baseline(reread, "cyc_1", project_id="group_run")
