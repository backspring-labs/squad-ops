"""The work envelope, read from the deploy's stored campaign packages (SIP-0113 §4.6; #2418)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "aor_reading.py"
_spec = importlib.util.spec_from_file_location("aor_reading", _SCRIPT)
reading = importlib.util.module_from_spec(_spec)
sys.modules["aor_reading"] = reading
_spec.loader.exec_module(reading)

from tests.unit.outcomes.test_aor import _package  # noqa: E402


def _store(vault: Path, art: str, doc: dict, created: str) -> None:
    d = vault / "group_run" / "_unattached" / art
    d.mkdir(parents=True)
    filename = f"campaign-{doc['campaign']['campaign_id']}-package.json"
    (d / filename).write_text(json.dumps(doc))
    meta = {
        "artifact_type": "campaign_evidence",
        "filename": filename,
        "created_at": created,
        "metadata": {"campaign_id": doc["campaign"]["campaign_id"], "part": "package"},
    }
    (d / "metadata.json").write_text(json.dumps(meta))


def test_each_campaigns_latest_package_is_read_and_its_class_reported(tmp_path, capsys):
    """Bug caught: a campaign counted twice for its two packages, its older package read in
    place of the one written at close, or a digest artifact read as a package."""
    _store(tmp_path, "art_old", _package("cmp_a", outcome=None), "2026-10-19T01:00:00")
    _store(tmp_path, "art_new", _package("cmp_a", outcome="exhausted"), "2026-10-19T02:00:00")
    _store(tmp_path, "art_b", _package("cmp_b"), "2026-10-19T03:00:00")
    digest = tmp_path / "group_run" / "_unattached" / "art_digest"
    digest.mkdir(parents=True)
    (digest / "metadata.json").write_text(
        json.dumps(
            {
                "artifact_type": "campaign_evidence",
                "filename": "d.md",
                "metadata": {"part": "digest"},
            }
        )
    )

    assert reading.main(["--vault", str(tmp_path)]) == 0

    out = capsys.readouterr().out
    assert "| tier-1, unattended, 3 | 2 | 0 | 1 | 1 | not yet read |" in out
    assert "- `cmp_b` (tier-1, unattended, 3): every quality baseline held" in out


def test_a_vault_with_no_package_says_so(tmp_path, capsys):
    assert reading.main(["--vault", str(tmp_path)]) == 1
    assert "no campaign package" in capsys.readouterr().err
