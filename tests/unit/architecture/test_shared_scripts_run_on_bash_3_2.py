"""A shared shell script runs under macOS's ``/bin/bash``, which is 3.2 (#2402).

The MacBook lane's box ships bash 3.2.57; CI's ``ubuntu-latest`` ships bash 5. So a bash-4
construct is green in CI and fails on the Mac: ``run_prose_lane.sh``'s ``mapfile`` exited 127
there on 2026-10-17, and the lane CI runs on every PR couldn't be run on the box whose PRs it
gates. This guard reads every shell script a developer's box runs for the constructs bash 3.2
lacks, and fails naming the file, the line and the construct. It runs in the regression suite on
Linux, so the Linux CI catches the Mac's failure.

A script written for one box is exempt when its header says so: ``# Platform: local-spark``
names the bootstrap profiles (``scripts/bootstrap/profiles/``) it runs on. A declaration that
includes ``dev-mac``, or names a profile that doesn't exist, exempts nothing.

Bug classes guarded:

- a bash-4-only construct (``mapfile``, an associative array, a case-changing expansion, ...)
  in a script the Mac runs;
- a scan that reads the scripts' own comments as code, which pressures the next author to
  delete the explanation of why a construct isn't used;
- a mistyped platform declaration (``lcoal-spark``) that silently exempts a shared script.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

_REPO = Path(__file__).resolve().parents[3]
#: Where the scripts a developer's box runs live. ``infra/`` is left out: its scripts run inside
#: the Postgres container, whose bash is the image's. ``tests/fixtures`` holds data, not scripts.
_ROOTS = ("scripts", "tests", ".claude/hooks")
_SKIP_PARTS = {"__pycache__", "node_modules", ".venv", "fixtures"}
_MAC = "dev-mac"
_SHEBANG = re.compile(r"#!\S*(?:/|env\s+)(?:ba)?sh\b")
_PLATFORM = re.compile(r"#\s*Platform:\s*(.+)")

#: (what bash 3.2 lacks, the bash release that added it, how to find it on a line of code).
CONSTRUCTS = [
    ("mapfile", "4.0", re.compile(r"\bmapfile\b")),
    ("readarray", "4.0", re.compile(r"\breadarray\b")),
    ("an associative array", "4.0", re.compile(r"\b(?:declare|local|typeset)\s+-[a-zA-Z]*A")),
    ("a nameref", "4.3", re.compile(r"\b(?:declare|local|typeset)\s+-[a-zA-Z]*n")),
    (
        "a case-changing expansion",
        "4.0",
        re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*(?:\[[^]]*\])?(?:\^|,)"),
    ),
    ("|& (a pipe of stderr too)", "4.0", re.compile(r"\|&")),
    ("&>> (an append of both streams)", "4.0", re.compile(r"&>>")),
    ("wait -n", "4.3", re.compile(r"\bwait\s+-n\b")),
    ("globstar", "4.0", re.compile(r"\bglobstar\b")),
    ("coproc", "4.0", re.compile(r"\bcoproc\b")),
]


def _profiles() -> set[str]:
    return {p.stem for p in (_REPO / "scripts" / "bootstrap" / "profiles").glob("*.sh")}


def _is_shell_script(path: Path) -> bool:
    if path.suffix in {".sh", ".bash"}:
        return True
    if path.suffix:
        return False
    with path.open("rb") as f:
        first = f.readline(200).decode("utf-8", "replace")
    return bool(_SHEBANG.match(first))


def _shell_scripts() -> list[Path]:
    found = []
    for root in _ROOTS:
        for path in (_REPO / root).rglob("*"):
            rel = path.relative_to(_REPO)
            if path.is_file() and not _SKIP_PARTS & set(rel.parts) and _is_shell_script(path):
                found.append(path)
    return sorted(found)


def _declared_platforms(text: str) -> list[str] | None:
    """The profiles a script's header names (``# Platform: local-spark``), or ``None``."""
    for line in text.splitlines():
        if line.startswith("#!"):
            continue
        if not line.startswith("#"):
            return None
        found = _PLATFORM.match(line)
        if found:
            return [p for p in re.split(r"[\s,]+", found.group(1).strip()) if p]
    return None


def bash_3_2_findings(name: str, text: str, profiles: set[str]) -> list[str]:
    """Every bash-4-only construct in ``text`` a Mac would run, as ``name:line: construct``.

    Comments are not code: a script may explain why it doesn't use ``mapfile``.
    """
    platforms = _declared_platforms(text)
    if platforms is not None:
        unknown = sorted(set(platforms) - profiles)
        if unknown:
            return [
                f"{name}: declares {unknown}, which no bootstrap profile is: {sorted(profiles)}"
            ]
        if _MAC not in platforms:
            return []
    findings = []
    for number, line in enumerate(text.splitlines(), start=1):
        code = line.split(" #", 1)[0]
        if code.lstrip().startswith("#"):
            continue
        for construct, since, pattern in CONSTRUCTS:
            if pattern.search(code):
                findings.append(f"{name}:{number}: {construct} (bash {since}; macOS has 3.2)")
    return findings


def test_no_script_a_mac_runs_uses_what_bash_3_2_lacks():
    profiles = _profiles()
    scripts = _shell_scripts()
    assert _REPO / "scripts" / "dev" / "run_prose_lane.sh" in scripts

    findings = [
        finding
        for path in scripts
        for finding in bash_3_2_findings(
            str(path.relative_to(_REPO)), path.read_text(encoding="utf-8"), profiles
        )
    ]

    assert findings == [], (
        "rewrite these in a form bash 3.2 runs (a `while read` loop for mapfile; "
        '${a[@]+"${a[@]}"} for an array that may be empty under set -u), or declare the '
        "script's platform in its header (`# Platform: local-spark`) when it is written for one "
        "box (#2402)"
    )


_PROFILES = {"dev-mac", "dev-pc", "local-spark"}


@pytest.mark.parametrize(
    ("line", "named"),
    [
        ("mapfile -t selected < <(grep -rl x tests | sort)", "mapfile (bash 4.0"),
        ("readarray -t rows < file", "readarray (bash 4.0"),
        ("declare -A seen=()", "an associative array (bash 4.0"),
        ("  local -A by_name", "an associative array (bash 4.0"),
        ("declare -n ref=$1", "a nameref (bash 4.3"),
        ('echo "${profile,,}"', "a case-changing expansion (bash 4.0"),
        ('[ "${ANSWER^^}" = YES ]', "a case-changing expansion (bash 4.0"),
        ("make 2>&1 |& tee build.log", "|& (a pipe of stderr too) (bash 4.0"),
        ("run &>> deploy.log", "&>> (an append of both streams) (bash 4.0"),
        ("wait -n", "wait -n (bash 4.3"),
        ("shopt -s globstar", "globstar (bash 4.0"),
        ("coproc reader { cat; }", "coproc (bash 4.0"),
    ],
)
def test_each_construct_bash_3_2_lacks_is_refused_by_name(line, named):
    text = f"#!/usr/bin/env bash\nset -euo pipefail\n{line}\n"

    assert bash_3_2_findings("s.sh", text, _PROFILES) == [f"s.sh:3: {named}; macOS has 3.2)"]


def test_the_forms_bash_3_2_runs_and_the_comments_explaining_them_pass():
    """Edge: the replacements must not read as the constructs they replace, and a comment that
    names a construct is not a use of it."""
    text = (
        "#!/usr/bin/env bash\n"
        "# No mapfile here: macOS's bash is 3.2, so a read loop instead (declare -A is 4.0 too).\n"
        "selected=()\n"
        'while IFS= read -r file; do selected+=("$file"); done < <(grep -rl x tests)\n'
        'printf "%s\\n" ${selected[@]+"${selected[@]}"} | grep -qxF "$must"  # not mapfile\n'
        'echo "${#selected[@]} ${HOME:-/} ${name%,*}" &>/dev/null || exit 1\n'
    )

    assert bash_3_2_findings("s.sh", text, _PROFILES) == []


@pytest.mark.parametrize(
    ("header", "refused"),
    [
        ("# Platform: local-spark", []),
        ("# Platform: local-spark, dev-pc", []),
        ("# Platform: dev-mac, local-spark", ["s.sh:4: mapfile (bash 4.0; macOS has 3.2)"]),
        (
            "# Platform: lcoal-spark",
            [
                "s.sh: declares ['lcoal-spark'], which no bootstrap profile is: "
                "['dev-mac', 'dev-pc', 'local-spark']"
            ],
        ),
        (
            "# The local-spark box only, but undeclared.",
            ["s.sh:4: mapfile (bash 4.0; macOS has 3.2)"],
        ),
    ],
    ids=["one box", "two boxes, neither the Mac", "the Mac among them", "a typo", "undeclared"],
)
def test_only_a_script_that_declares_it_never_runs_on_the_mac_is_exempt(header, refused):
    text = f"#!/usr/bin/env bash\n{header}\n#\nmapfile -t rows < <(ls)\n"

    assert bash_3_2_findings("s.sh", text, _PROFILES) == refused


def test_the_platform_declaration_is_read_only_from_the_header():
    """Edge: a ``# Platform:`` line below the first command is a comment in the body, and
    exempts nothing."""
    text = "#!/usr/bin/env bash\nset -eu\n# Platform: local-spark\nmapfile -t rows < <(ls)\n"

    assert bash_3_2_findings("s.sh", text, _PROFILES) == [
        "s.sh:4: mapfile (bash 4.0; macOS has 3.2)"
    ]
