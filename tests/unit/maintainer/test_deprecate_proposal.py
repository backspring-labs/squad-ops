"""#1968: ``proposed → deprecated`` through ``update_sip_status``, on a SIP tree of its own.

The 2026-10-04 portfolio audit ruled 12 proposed SIPs deprecated (Q14), and the maintainer flow
had no path for them. Two of them are warm-boot drafts sharing the number 18.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "maintainer" / "update_sip_status.py"


@pytest.fixture
def tool(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("update_sip_status_1968", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sips = tmp_path / "sips"
    for d in ("proposed", "accepted", "implemented", "deprecated"):
        (sips / d).mkdir(parents=True)
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "REGISTRY_FILE", sips / "registry.yaml")
    for name in ("PROPOSED", "ACCEPTED", "IMPLEMENTED", "DEPRECATED"):
        monkeypatch.setattr(mod, f"{name}_DIR", sips / name.lower())
    monkeypatch.setattr(
        mod,
        "STATUS_TO_FOLDER",
        {s: sips / s for s in ("proposed", "accepted", "implemented", "deprecated")},
    )
    monkeypatch.setenv("SQUADOPS_MAINTAINER", "1")
    return mod, tmp_path


def _proposal(root: Path, name: str, number: int | None, uid: str) -> Path:
    head = {"sip_uid": uid, "title": name, "status": "proposed", "author": "a"}
    if number is not None:
        head["sip_number"] = number
    path = root / "sips" / "proposed" / f"{name}.md"
    path.write_text(f"---\n{yaml.safe_dump(head)}---\n\n# {name}\n\n**Status:** Proposed\n")
    return path


def _registry(root: Path, rows: list[dict]) -> None:
    (root / "sips" / "registry.yaml").write_text(
        yaml.safe_dump({"last_assigned": 110, "sips": rows})
    )


def _rows(root: Path) -> list[dict]:
    return yaml.safe_load((root / "sips" / "registry.yaml").read_text())["sips"]


def test_a_proposal_is_deprecated_unnumbered_with_its_row(tool):
    mod, root = tool
    sip = _proposal(root, "SIP-Superseded-Draft", None, "uid-a")
    _registry(
        root,
        [
            {
                "sip_uid": "uid-a",
                "sip_number": None,
                "path": "sips/proposed/SIP-Superseded-Draft.md",
                "status": "proposed",
            }
        ],
    )

    assert mod.update_sip_status(sip, "deprecated")

    moved = root / "sips" / "deprecated" / "SIP-Superseded-Draft.md"
    assert not sip.exists() and moved.exists()
    text = moved.read_text()
    assert "status: deprecated" in text and "**Status:** Deprecated" in text
    [row] = _rows(root)
    assert row["status"] == "deprecated" and row["sip_number"] is None
    assert row["path"] == "sips/deprecated/SIP-Superseded-Draft.md"


def test_of_two_drafts_sharing_a_number_only_the_one_named_moves(tool):
    """Bug caught: a lookup by number (``find_sip_in_registry``'s way) rewriting the other
    draft's row, so the registry points at a file that never moved."""
    mod, root = tool
    _proposal(root, "SIP-0018-Enterprise-Process", 18, "uid-18a")
    second = _proposal(root, "SIP-0018-v2-Squad-Context", 18, "uid-18b")
    _registry(
        root,
        [
            {
                "sip_uid": "uid-18a",
                "sip_number": 18,
                "path": "sips/proposed/SIP-0018-Enterprise-Process.md",
                "status": "proposed",
            },
            {
                "sip_uid": "uid-18b",
                "sip_number": 18,
                "path": "sips/proposed/SIP-0018-v2-Squad-Context.md",
                "status": "proposed",
            },
        ],
    )

    assert mod.update_sip_status(second, "deprecated")

    rows = {r["sip_uid"]: r for r in _rows(root)}
    assert rows["uid-18a"]["status"] == "proposed"
    assert rows["uid-18a"]["path"] == "sips/proposed/SIP-0018-Enterprise-Process.md"
    assert rows["uid-18b"]["status"] == "deprecated" and rows["uid-18b"]["sip_number"] == 18


def test_a_proposal_with_no_row_gets_one(tool):
    mod, root = tool
    sip = _proposal(root, "SIP-Never-Indexed", None, "uid-new")
    _registry(root, [])

    assert mod.update_sip_status(sip, "deprecated")

    [row] = _rows(root)
    assert (row["sip_uid"], row["status"], row["sip_number"]) == ("uid-new", "deprecated", None)


def test_a_proposal_cannot_skip_to_implemented(tool, capsys):
    mod, root = tool
    sip = _proposal(root, "SIP-Draft", None, "uid-d")
    _registry(root, [])

    assert not mod.update_sip_status(sip, "implemented")
    assert "Invalid transition: proposed → implemented" in capsys.readouterr().out
    assert sip.exists()
