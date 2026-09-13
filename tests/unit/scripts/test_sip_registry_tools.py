"""The registry tooling behind #1144: the audit's timestamp rule, proposal indexing, and
acceptance updating an indexed proposal's row rather than adding a second one."""

from __future__ import annotations

import importlib
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_MAINTAINER = REPO_ROOT / "scripts" / "maintainer"
if str(_MAINTAINER) not in sys.path:
    sys.path.insert(0, str(_MAINTAINER))

audit = importlib.import_module("audit_sip_registry")
cleanup = importlib.import_module("cleanup_sip_registry")
update_status = importlib.import_module("update_sip_status")


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        # The nine findings #1144 reported against correct values: day precision.
        ("2026-02-23", True),
        ("2026-02-24T21:59:22.215709Z", True),
        ("2026-02-24T21:59:22Z", True),
        # YAML parses an unquoted date into an object, which the old rule called invalid.
        (date(2026, 7, 1), True),
        (datetime(2026, 7, 1, 12, 0, 0), True),
        # The legacy-migration corruption: prose scraped into the field.
        ("patterns in requirements doc.", False),
        ("Challenges**: Domain knowledge updates", False),
        # Half a date, a bare year and an empty field are not timestamps either.
        ("2026-02", False),
        ("2026", False),
        ("", False),
        (None, False),
    ],
)
def test_iso_timestamp_rule_accepts_day_precision_and_rejects_prose(value, valid):
    assert audit.is_valid_iso_timestamp(value) is valid


def _sip_tree(tmp_path: Path, monkeypatch) -> Path:
    """A minimal sips/ tree the audit and cleanup modules read as the repo's."""
    root = tmp_path / "repo"
    for folder in ("proposed", "accepted", "implemented", "deprecated"):
        (root / "sips" / folder).mkdir(parents=True)
    monkeypatch.setattr(audit, "REPO_ROOT", root)
    monkeypatch.setattr(audit, "REGISTRY_FILE", root / "sips" / "registry.yaml")
    for name in ("PROPOSED_DIR", "ACCEPTED_DIR", "IMPLEMENTED_DIR", "DEPRECATED_DIR"):
        monkeypatch.setattr(audit, name, root / "sips" / name.split("_")[0].lower())
    monkeypatch.setattr(
        audit,
        "STATUS_TO_FOLDER",
        {
            "proposed": audit.PROPOSED_DIR,
            "accepted": audit.ACCEPTED_DIR,
            "implemented": audit.IMPLEMENTED_DIR,
            "deprecated": audit.DEPRECATED_DIR,
        },
    )
    return root


def test_index_proposals_gives_an_unnumbered_draft_a_row_and_stamps_its_uid(tmp_path, monkeypatch):
    """The 7-vs-31 gap: a draft with frontmatter but no uid and no row."""
    root = _sip_tree(tmp_path, monkeypatch)
    draft = root / "sips" / "proposed" / "SIP-Some-Idea.md"
    draft.write_text(
        "---\ntitle: Some Idea\nstatus: proposed\nauthor: Jo\ncreated_at: 2026-07-01\n---\n"
        "# SIP: Some Idea\n",
        encoding="utf-8",
    )
    registry = {"last_assigned": 3, "sips": []}

    assert cleanup.index_proposals(registry) == 1

    (row,) = registry["sips"]
    assert row["sip_number"] is None
    assert row["status"] == "proposed"
    assert row["path"] == "sips/proposed/SIP-Some-Idea.md"
    assert row["created_at"] == "2026-07-01"
    assert row["updated_at"] is None, "a proposal has had no status transition"
    # The uid is stamped into the file so the row and the file share one stable key, and
    # nothing else in the frontmatter is reformatted.
    text = draft.read_text(encoding="utf-8")
    assert text.startswith(f"---\nsip_uid: '{row['sip_uid']}'\ntitle: Some Idea\n")
    assert audit.extract_metadata_from_file(draft)["sip_uid"] == row["sip_uid"]
    # Idempotent: the row now exists, so a second run indexes nothing.
    assert cleanup.index_proposals(registry) == 0
    assert len(registry["sips"]) == 1


def test_index_proposals_skips_numbered_orphans_and_files_without_frontmatter(
    tmp_path, monkeypatch, capsys
):
    """A numbered file is --add-orphaned's case; a bare draft needs frontmatter first."""
    root = _sip_tree(tmp_path, monkeypatch)
    (root / "sips" / "proposed" / "SIP-0099-Numbered.md").write_text(
        "---\ntitle: Numbered\nstatus: proposed\nsip_number: 99\n---\n", encoding="utf-8"
    )
    (root / "sips" / "proposed" / "IDEA-Bare.md").write_text("# IDEA — Bare\n", encoding="utf-8")
    registry = {"last_assigned": 3, "sips": []}

    assert cleanup.index_proposals(registry) == 0
    assert registry["sips"] == []
    assert "skipped IDEA-Bare.md: no YAML frontmatter" in capsys.readouterr().out


def test_audit_reports_an_unindexed_proposal_as_data_quality(tmp_path, monkeypatch):
    """Under #1144 an unindexed draft is a finding, not an informational note."""
    root = _sip_tree(tmp_path, monkeypatch)
    (root / "sips" / "proposed" / "SIP-Unindexed.md").write_text(
        "---\ntitle: Unindexed\nstatus: proposed\n---\n", encoding="utf-8"
    )
    (root / "sips" / "registry.yaml").write_text("last_assigned: 0\nsips: []\n", encoding="utf-8")

    issues = audit.audit_registry()["issues"]

    assert [f["type"] for f in issues["data_quality"]] == ["unindexed_proposal"]
    assert "--index-proposals" in issues["data_quality"][0]["message"]
    assert issues["critical"] == []


def test_audit_reports_prose_in_a_file_date_field(tmp_path, monkeypatch):
    """The registry can be clean while the file it mirrors still carries scraped prose."""
    root = _sip_tree(tmp_path, monkeypatch)
    path = root / "sips" / "implemented" / "SIP-0007-Thing.md"
    path.write_text(
        "---\ntitle: Thing\nstatus: implemented\nsip_number: 7\nsip_uid: 'u7'\n"
        "created_at: patterns in requirements doc.\n---\n",
        encoding="utf-8",
    )
    (root / "sips" / "registry.yaml").write_text(
        "last_assigned: 7\nsips:\n- sip_number: 7\n  sip_uid: 'u7'\n  title: Thing\n"
        "  status: implemented\n  path: sips/implemented/SIP-0007-Thing.md\n"
        "  created_at: '2025-11-27T10:12:48Z'\n  updated_at: '2025-11-27T10:12:48Z'\n",
        encoding="utf-8",
    )

    findings = audit.audit_registry()["issues"]["data_quality"]

    assert [(f["type"], f["field"]) for f in findings] == [("invalid_file_timestamp", "created_at")]
    assert findings[0]["file"] == "sips/implemented/SIP-0007-Thing.md"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # SIP-0020 after #1144: the first line of a two-line created_at replaced, the
        # continuation left behind.
        (
            "---\ntitle: T\ncreated_at: '2025-12-07T19:51:00Z'\n  deployment (deploy existing)\n"
            "updated_at: '2025-12-07T19:51:00Z'\n---\n# T\n",
            "while parsing a block mapping",
        ),
        # A block that parses to something other than a mapping has no fields to check.
        ("---\n- a\n- b\n---\n# T\n", "frontmatter is a list, not a mapping"),
        # A hand-authored draft with no frontmatter is legitimate (#770), not a parse error.
        ("# SIP: Draft\n\n**Status:** Proposed\n", None),
        ("---\ntitle: T\nstatus: proposed\n---\n# T\n", None),
    ],
)
def test_frontmatter_parse_error_tells_a_broken_block_from_an_absent_one(tmp_path, text, expected):
    path = tmp_path / "SIP-Thing.md"
    path.write_text(text, encoding="utf-8")

    error = audit.frontmatter_parse_error(path)

    if expected is None:
        assert error is None
    else:
        assert error is not None and expected in error


def test_audit_reports_frontmatter_it_cannot_parse(tmp_path, monkeypatch):
    """Before this check the audit read SIP-0020's broken block as "no metadata" and skipped
    every consistency check on the file, so the defect sat in a green regression gate from
    2026-09-02 to 2026-09-13. The indexed draft with no frontmatter beside it is not a finding."""
    root = _sip_tree(tmp_path, monkeypatch)
    (root / "sips" / "deprecated" / "SIP-0020-Thing.md").write_text(
        "---\ntitle: Thing\nstatus: deprecated\nsip_number: 20\nsip_uid: 'u20'\n"
        "created_at: '2025-12-07T19:51:00Z'\n  deployment (deploy existing)\n"
        "updated_at: '2025-12-07T19:51:00Z'\n---\n# SIP-020: Thing\n",
        encoding="utf-8",
    )
    (root / "sips" / "proposed" / "SIP-Draft.md").write_text(
        "# SIP: Draft\n\n**Status:** Proposed\n", encoding="utf-8"
    )
    (root / "sips" / "registry.yaml").write_text(
        "last_assigned: 20\nsips:\n"
        "- sip_number: 20\n  sip_uid: 'u20'\n  title: Thing\n  status: deprecated\n"
        "  path: sips/deprecated/SIP-0020-Thing.md\n"
        "  created_at: '2025-12-07T19:51:00Z'\n  updated_at: '2025-12-07T19:51:00Z'\n"
        "- sip_number: null\n  sip_uid: 'ud'\n  title: Draft\n  status: proposed\n"
        "  path: sips/proposed/SIP-Draft.md\n  created_at: null\n  updated_at: null\n",
        encoding="utf-8",
    )

    findings = audit.audit_registry()["issues"]["data_quality"]

    assert [(f["type"], f["file"]) for f in findings] == [
        ("unparseable_frontmatter", "sips/deprecated/SIP-0020-Thing.md")
    ]
    assert "while parsing a block mapping" in findings[0]["message"]


def test_acceptance_updates_an_indexed_proposals_row_instead_of_appending():
    """With proposals indexed, an unconditional append made every acceptance a duplicate uid."""
    registry = {
        "last_assigned": 5,
        "sips": [
            {"sip_number": 5, "sip_uid": "u5", "status": "implemented"},
            {"sip_number": None, "sip_uid": "u-draft", "status": "proposed", "updated_at": None},
        ],
    }
    accepted = {
        "sip_uid": "u-draft",
        "sip_number": 6,
        "status": "accepted",
        "path": "sips/accepted/SIP-0006-Draft.md",
        "updated_at": "2026-09-02T00:00:00Z",
    }

    assert update_status.upsert_registry_entry(registry, accepted) is True

    assert len(registry["sips"]) == 2
    row = next(r for r in registry["sips"] if r["sip_uid"] == "u-draft")
    assert row["sip_number"] == 6
    assert row["status"] == "accepted"
    assert row["updated_at"] == "2026-09-02T00:00:00Z"


def test_acceptance_appends_when_no_row_carries_the_uid():
    """A draft that was never indexed (or has no uid) still gets its row."""
    registry = {"last_assigned": 5, "sips": [{"sip_number": 5, "sip_uid": "u5"}]}

    assert (
        update_status.upsert_registry_entry(registry, {"sip_uid": None, "sip_number": 6}) is False
    )
    assert (
        update_status.upsert_registry_entry(registry, {"sip_uid": "new", "sip_number": 7}) is False
    )
    assert [r["sip_number"] for r in registry["sips"]] == [5, 6, 7]


def test_registry_sorts_numbered_rows_first_and_proposals_last():
    rows = [
        {"sip_number": None, "sip_uid": "draft"},
        {"sip_number": 3, "variant": "v3"},
        {"sip_number": 3, "variant": "v2"},
        {"sip_number": 1},
    ]
    rows.sort(key=update_status.registry_sort_key)
    assert [(r.get("sip_number"), r.get("variant")) for r in rows] == [
        (1, None),
        (3, "v2"),
        (3, "v3"),
        (None, None),
    ]
