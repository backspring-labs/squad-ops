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
