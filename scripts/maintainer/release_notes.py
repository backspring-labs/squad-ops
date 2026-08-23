#!/usr/bin/env python3
"""Derive a GitHub Release's title and body for a version (#1061).

Called by `.github/workflows/release.yml` on a `v*` tag push. Lives here rather
than inline in the workflow so the parsing is unit-testable and so a change to
the CHANGELOG or ROADMAP heading shape breaks a test rather than a release.

The body is the version's CHANGELOG section verbatim. That text is written
deliberately and reviewed in the release PR, and `test_docs_version_sync.py`
rule 4 already guarantees the section exists before a tag can be cut — so
publishing it automatically is publishing reviewed content, not unread content.

Usage:
    python scripts/maintainer/release_notes.py 1.6.1 --body-file notes.md
    python scripts/maintainer/release_notes.py 1.6.1 --print-title
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Same shape the docs-drift guard enforces (test_docs_version_sync.py). Both
# dash styles are present in the file's history, so both must parse.
SECTION = r"^## \[{v}\] +[—-] +\d{{4}}-\d{{2}}-\d{{2}}\s*$"
NEXT_SECTION = r"^## \["
# ROADMAP: "### v1.6.0 (2026-08-21) — the Authorship release"
ROADMAP_HEADING = r"^### v{v} \(\d{{4}}-\d{{2}}-\d{{2}}\)\s*—\s*(.+?)\s*$"


class NotFound(Exception):
    """A required section is missing — fail the release rather than publish a stub."""


def changelog_body(version: str, text: str) -> str:
    start = re.search(SECTION.format(v=re.escape(version)), text, re.MULTILINE)
    if not start:
        raise NotFound(
            f"CHANGELOG.md has no section for {version}. "
            "Rotate the changelog before tagging (see CLAUDE.md, Release cut)."
        )
    rest = text[start.end() :]
    end = re.search(NEXT_SECTION, rest, re.MULTILINE)
    body = (rest[: end.start()] if end else rest).strip()
    if not body:
        raise NotFound(f"CHANGELOG.md section for {version} is empty.")
    return body


def release_title(version: str, roadmap: str) -> str:
    """`v1.6.0 — the Authorship release`, or the bare tag if the ROADMAP is silent.

    A missing ROADMAP entry is not fatal: the release is still worth publishing,
    and a bare version title is honest. Only the body is load-bearing.
    """
    match = re.search(ROADMAP_HEADING.format(v=re.escape(version)), roadmap, re.MULTILINE)
    if not match:
        return f"v{version}"
    # "Current" is a transient marker on the newest entry; it is not part of the name.
    name = re.sub(r"^Current\s*—\s*", "", match.group(1)).strip()
    return f"v{version} — {name}" if name else f"v{version}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("version", help="version without the leading v, e.g. 1.6.1")
    ap.add_argument("--body-file", type=Path, help="write the release body here")
    ap.add_argument("--print-title", action="store_true", help="print the title to stdout")
    args = ap.parse_args()

    version = args.version.lstrip("v")
    try:
        body = changelog_body(version, (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
        title = release_title(
            version, (REPO_ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        )
    except NotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.body_file:
        args.body_file.write_text(body + "\n", encoding="utf-8")
    if args.print_title:
        print(title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
