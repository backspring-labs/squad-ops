"""Shared scripts run on every bootstrap profile as it ships (#2402; CLAUDE.md, Structure).

`run_prose_lane.sh` exited 127 on the MacBook (`mapfile: command not found`): macOS ships bash 3.2,
and CI runs bash 5 on Ubuntu, so the lane was green in CI and broken on the box it serves. Bare
`sed -i` in bootstrap failed the same way (BSD sed reads the next argument as the backup suffix).
This guard runs on Ubuntu, so the Linux CI catches the Mac defect: a script under `scripts/` uses
only what bash 3.2 and the flags BSD and GNU share allow, unless its header declares the one box it
is for (`# Platform: local-spark`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_contracts]

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Each construct the rule refuses, and what it is. A comment line is never read.
REFUSED = (
    (re.compile(r"\bmapfile\b|\breadarray\b"), "mapfile/readarray (bash 4)"),
    (re.compile(r"\b(?:declare|local|typeset)\s+-[a-zA-Z]*A"), "an associative array (bash 4)"),
    (re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*(?:,,|\^\^)\}"), "a case-changing expansion (bash 4)"),
    (re.compile(r"\b(?:declare|local)\s+-[a-zA-Z]*n\b"), "a nameref (bash 4.3)"),
    (re.compile(r"\bwait\s+-n\b"), "wait -n (bash 4.3)"),
    (re.compile(r"\bshopt\s+-s\s+globstar\b"), "globstar (bash 4)"),
    (re.compile(r"\bcoproc\b"), "coproc (bash 4)"),
    (re.compile(r"\bgrep\s+(?:-[a-zA-Z]*P\b|--perl-regexp)"), "grep -P (GNU)"),
    (re.compile(r"\bsed\s+(?:-[a-zA-Z]+\s+)*-i(?:\s|$)"), "a bare sed -i (GNU)"),
    (re.compile(r"\breadlink\s+-f\b"), "readlink -f (GNU)"),
    (re.compile(r"\bdate\s+(?:-[a-zA-Z]+\s+)*-d\b"), "date -d (GNU)"),
    (re.compile(r"\bstat\s+-c\b"), "stat -c (GNU)"),
    (re.compile(r"\bsort\s+-[a-zA-Z]*V"), "sort -V (GNU)"),
    (re.compile(r"\bfind\b.*\s-printf\b"), "find -printf (GNU)"),
)
#: A header line naming the one box a script is for. Only its first lines are read.
PLATFORM = re.compile(r"^#\s*Platform:\s*\S", re.IGNORECASE)
HEADER_LINES = 20


def violations(path: Path, text: str) -> list[str]:
    """Each refused construct in ``text``, as ``path:line: what``, or none for a declared script."""
    lines = text.splitlines()
    if any(PLATFORM.match(line) for line in lines[:HEADER_LINES]):
        return []
    found = []
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            continue
        found.extend(
            f"{path}:{number}: {what}" for pattern, what in REFUSED if pattern.search(line)
        )
    return found


def test_every_shared_script_runs_on_every_profile():
    """Bug caught: a bash-4 construct or a GNU-only flag in a shared script, green on the Ubuntu CI
    and broken on the MacBook's stock bash 3.2 and BSD userland."""
    found = [
        v
        for path in sorted((REPO_ROOT / "scripts").rglob("*.sh"))
        for v in violations(path.relative_to(REPO_ROOT), path.read_text(errors="replace"))
    ]

    assert found == [], "\n".join(found)


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("#!/usr/bin/env bash\nmapfile -t xs < <(ls)\n", ["s.sh:2: mapfile/readarray (bash 4)"]),
        ("#!/usr/bin/env bash\n# Platform: local-spark\nmapfile -t xs < <(ls)\n", []),
        ('sed -i "s|a|b|" .env\n', ["s.sh:1: a bare sed -i (GNU)"]),
        ('sed -i.bak "s|a|b|" .env\n', []),
        ("uid=$(stat -c %u dir)\n", ["s.sh:1: stat -c (GNU)"]),
        ("# mapfile is bash 4, so this reads a loop\nwhile read -r f; do :; done\n", []),
        ('echo "${name,,}"\n', ["s.sh:1: a case-changing expansion (bash 4)"]),
    ],
    ids=["mapfile-undeclared", "mapfile-declared", "bare-sed-i", "sed-i-with-suffix", "stat-c",
         "a-comment-naming-it", "lowercase-expansion"],
)  # fmt: skip
def test_the_rule_refuses_and_accepts_by_the_construct_and_the_header(text, found):
    """The issue's accepted and refused cases. Bug caught: a declared script refused, so a Spark-only
    script must lie about its platform; or a comment, or an attached sed suffix, read as a use."""
    assert violations(Path("s.sh"), text) == found
