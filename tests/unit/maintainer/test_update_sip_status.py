"""Unit tests for the body status-line rewrite in update_sip_status.py (#253).

The script already updates the frontmatter ``status:`` field; the bug was that the
human-readable body ``**Status:**`` line was left stale, so a promoted SIP's body
silently disagreed with its frontmatter/registry. ``update_sip_body_status`` closes
that gap. Bug classes guarded:

- the body status line not being rewritten at all (the original bug);
- a rewrite that clobbers the line's markdown or a trailing annotation
  (e.g. ``(umbrella / vision)``);
- the body regex reaching into the frontmatter and corrupting the YAML
  ``status:`` value (it must operate on the body only);
- replacing *every* "Status:" occurrence, mangling prose/historical notes — only
  the first declaration must change;
- silently "succeeding" (or corrupting the file) when there is no recognizable
  body status line.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "maintainer" / "update_sip_status.py"

_spec = importlib.util.spec_from_file_location("update_sip_status", _SCRIPT)
update_sip_status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(update_sip_status)

update_sip_body_status = update_sip_status.update_sip_body_status


_FRONTMATTER = "---\nsip_number: 89\nstatus: accepted\ntitle: Demo\n---\n\n"


def _write(tmp_path: Path, body: str) -> Path:
    f = tmp_path / "SIP-0089-Demo.md"
    f.write_text(_FRONTMATTER + body, encoding="utf-8")
    return f


def _write_bare(tmp_path: Path, body: str) -> Path:
    """A hand-authored draft: body only, no frontmatter block (#770)."""
    f = tmp_path / "SIP-Hand-Authored.md"
    f.write_text(body, encoding="utf-8")
    return f


def test_rewrites_canonical_body_line_without_touching_frontmatter(tmp_path):
    """The reported bug: accepted→implemented must flip the body line. The
    frontmatter ``status: accepted`` must be left exactly as-is (it's handled
    elsewhere and the body pass must not reach into it)."""
    f = _write(tmp_path, "# Demo\n\n**Status:** Accepted\n\nBody text.\n")

    assert update_sip_body_status(f, "implemented") is True

    content = f.read_text(encoding="utf-8")
    assert "**Status:** Implemented\n" in content
    assert "**Status:** Accepted" not in content
    # frontmatter value is lowercase and must be untouched by the body pass
    assert "status: accepted\n" in content


def test_preserves_trailing_annotation(tmp_path):
    """A trailing annotation (SIP-0088's ``(umbrella / vision)``) must survive —
    only the status word changes, never the rest of the line."""
    f = _write(tmp_path, "**Status:** Accepted (umbrella / vision)\n")

    assert update_sip_body_status(f, "implemented") is True
    assert "**Status:** Implemented (umbrella / vision)\n" in f.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("line", "new_status", "expected"),
    [
        ("**Status**: Draft", "accepted", "**Status**: Accepted"),
        ("- **Status:** Accepted", "implemented", "- **Status:** Implemented"),
        ("*Status: Draft*", "accepted", "*Status: Accepted*"),
        ("status: Proposed", "accepted", "status: Accepted"),
    ],
)
def test_preserves_line_formatting_variants(tmp_path, line, new_status, expected):
    """Bug class: the rewrite must recognize the formatting variants in the corpus
    and preserve their markdown (bold/italic/list prefix, trailing emphasis),
    changing only the status word."""
    f = _write(tmp_path, f"{line}\n\nMore body.\n")

    assert update_sip_body_status(f, new_status) is True
    assert f"{expected}\n" in f.read_text(encoding="utf-8")


def test_only_first_status_line_changes(tmp_path):
    """Bug class: replacing every match would corrupt later mentions. A historical
    note further down that also looks like a status line must be left intact."""
    f = _write(
        tmp_path,
        "**Status:** Accepted\n\n## History\n\n> Earlier this was **Status:** Draft (2024).\n",
    )

    assert update_sip_body_status(f, "implemented") is True
    content = f.read_text(encoding="utf-8")
    assert "**Status:** Implemented\n" in content
    assert "**Status:** Draft (2024)." in content  # historical note untouched


def test_prose_mentions_of_status_are_not_matched(tmp_path):
    """Bug class: prose/code lines containing the word "status" must not be
    mistaken for the declaration. With no real status line, return False and leave
    the file byte-for-byte unchanged."""
    body = (
        "# Demo\n\n"
        "This SIP tracks deployment status across agents.\n"
        "    if response.status != 200:\n"
    )
    f = _write(tmp_path, body)
    before = f.read_text(encoding="utf-8")

    assert update_sip_body_status(f, "implemented") is False
    assert f.read_text(encoding="utf-8") == before


def test_header_only_status_is_noop(tmp_path):
    """Bug class: a ``## Status`` header with no inline ``<keyword>`` has nothing to
    rewrite — must report False (so the caller warns) and not alter the file."""
    f = _write(tmp_path, "## 📌 Status\n\nSome explanation, not a keyword.\n")
    before = f.read_text(encoding="utf-8")

    assert update_sip_body_status(f, "implemented") is False
    assert f.read_text(encoding="utf-8") == before


def test_frontmatter_status_is_never_rewritten_as_body(tmp_path):
    """Critical: when the body has no status line, the frontmatter ``status:``
    must NOT be picked up and rewritten (which would corrupt the YAML casing to
    ``Implemented`` and double-source the value). Returns False, file unchanged."""
    f = _write(tmp_path, "# Demo\n\nNo status declaration in the body at all.\n")
    before = f.read_text(encoding="utf-8")

    assert update_sip_body_status(f, "implemented") is False
    assert f.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# #770 — frontmatter derivation for hand-authored drafts
#
# Bug classes guarded: promotion dying on "Could not extract metadata" for a
# draft whose body already states everything the frontmatter needs (12 of 13
# proposed SIPs at the time this landed); a deriver that INVENTS a status rather
# than failing when none is declared; the heading-form status declaration being
# left stale after promotion (the #253 class, one form down — SIP-0103 had this
# exact shape); and a rewrite that eats the emphasis around an emphasised value.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "expected_title", "expected_status"),
    [
        # the three real H1 shapes in sips/proposed/
        (
            "# SIP-0XXX: API Contract Hardening\n\n**Status:** Proposed\n",
            "API Contract Hardening",
            "proposed",
        ),
        (
            "# SIP: Stack Blueprint Contract\n\n## Status\nDraft (proposed)\n",
            "Stack Blueprint Contract",
            "proposed",
        ),
        (
            "# SIP-0103: Squad-Authored Manifest\n\n**Status:** Accepted\n",
            "Squad-Authored Manifest",
            "accepted",
        ),
        # emphasised value under a heading — the shape that failed the first
        # implementation and was only caught by running over the real corpus
        (
            "# SIP: Post-Retest Review\n\n## Status\n\n**Proposed** (draft, 2026-08-07).\n",
            "Post-Retest Review",
            "proposed",
        ),
        # parenthetical annotations must not leak into the keyword
        (
            "# SIP-0XXX: Planning Sequence\n\n**Status:** Proposed (stub)\n",
            "Planning Sequence",
            "proposed",
        ),
        (
            "# SIP: Skill Layer\n\n**Status**: Proposed (concept reservation)\n",
            "Skill Layer",
            "proposed",
        ),
    ],
)
def test_derives_title_and_status_from_real_body_shapes(
    tmp_path, body, expected_title, expected_status
):
    f = _write_bare(tmp_path, body)
    derived, _detail = update_sip_status.derive_frontmatter_from_body(f)
    assert derived["title"] == expected_title
    assert derived["status"] == expected_status


def test_derives_author_and_created_when_the_body_states_them(tmp_path):
    f = _write(
        tmp_path,
        "# SIP: Cross-Cycle Memory\n\n## Status\nDraft (proposed)\n\n"
        "**Author:** Jason Ladd\n**Created:** 2026-08-03\n",
    )
    derived, _ = update_sip_status.derive_frontmatter_from_body(f)
    assert derived["author"] == "Jason Ladd"
    assert derived["created_at"] == "2026-08-03T00:00:00Z"


def test_missing_author_and_created_are_omitted_not_invented(tmp_path):
    """The promotion path already defaults these; a guessed value is worse than
    an absent one because it looks authoritative."""
    f = _write_bare(tmp_path, "# SIP: Bare\n\n**Status:** Proposed\n")
    derived, _ = update_sip_status.derive_frontmatter_from_body(f)
    assert "author" not in derived
    assert "created_at" not in derived


def test_underivable_status_fails_with_an_actionable_message(tmp_path):
    """The one field with no sane fallback: promoting from an unknown state
    would be a guess about intent."""
    f = _write_bare(tmp_path, "# SIP: No Status Here\n\nJust prose about a design.\n")
    derived, detail = update_sip_status.derive_frontmatter_from_body(f)
    assert derived is None
    assert "**Status:**" in detail and "## Status" in detail


def test_ensure_frontmatter_stamps_a_parsable_block(tmp_path):
    """End-to-end: a draft that previously died at 'Could not extract metadata'
    now round-trips through the real extractor."""
    f = _write_bare(tmp_path, "# SIP: Stack Blueprint Contract\n\n## Status\nDraft (proposed)\n")
    assert update_sip_status.extract_metadata_from_file(f) is None

    meta = update_sip_status.ensure_frontmatter(f)
    assert meta["status"] == "proposed"

    reparsed = update_sip_status.extract_metadata_from_file(f)
    assert reparsed["status"] == "proposed"
    assert reparsed["title"] == "Stack Blueprint Contract"
    assert f.read_text(encoding="utf-8").startswith("---\n")


def test_ensure_frontmatter_leaves_an_existing_block_alone(tmp_path):
    """Derivation must never overwrite what a maintainer hand-wrote."""
    f = _write(tmp_path, "# SIP: Already Stamped\n\n**Status:** Proposed\n")
    before = f.read_text(encoding="utf-8")

    meta = update_sip_status.ensure_frontmatter(f)

    assert meta["title"] == "Demo"  # from the frontmatter, not the H1
    assert meta["sip_number"] == 89
    assert f.read_text(encoding="utf-8") == before


def test_heading_form_body_status_is_rewritten_on_promotion(tmp_path):
    """The #253 class one form down: SIP-0103 declared status as a '## Status'
    heading, so its body would have kept saying Draft while the frontmatter and
    registry said accepted.
    """
    f = _write(tmp_path, "# SIP: Demo\n\n## Status\nProposed\n\nBody text.\n")
    assert update_sip_body_status(f, "accepted") is True
    assert "## Status\nAccepted\n" in f.read_text(encoding="utf-8")


def test_heading_form_rewrite_preserves_emphasis_and_annotation(tmp_path):
    f = _write(tmp_path, "# SIP: Demo\n\n## Status\n\n**Proposed** (draft, 2026-08-07).\n")
    assert update_sip_body_status(f, "accepted") is True
    assert "**Accepted** (draft, 2026-08-07)." in f.read_text(encoding="utf-8")
