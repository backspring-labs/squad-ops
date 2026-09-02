#!/usr/bin/env python3
"""Every released tag has a captured, non-hollow release package (#1151, cut step 7).

CLAUDE.md's release-cut procedure says of itself that step 7 — capturing the release
package into ``site/content/releases/v<tag>/`` — is unguarded. Its record: #789 (six
releases tagged and never advertised) and #1076 (a capture that "succeeded" and wrote a
roll-up of nulls, because ``{"detail": "Not Found"}`` is valid JSON). A step with that
history needs a check, not a restatement.

Why this runs on pushes to main and PRs rather than on the tag push: the package is
captured AFTER the tag by procedure — the script reads the tag range, so step 7 must
follow step 6 — and lands in a later commit. A check at tag time can only ever fail. Run
here, main goes red the moment a tag is pushed without its package and green again when
the capture lands; the interval is the signal.

Two rules per semver tag (``vMAJOR.MINOR.PATCH``; the ``v0.x-warmboot-*`` tags predate
the packaging convention and are not releases in this sense):

1. ``site/content/releases/<tag>/`` exists with ``index.md`` and ``package.yaml``, and
   the package names that tag.
2. From ``v1.6.2`` — the first release whose package carries cycle evidence; earlier
   packages were backfilled from git alone (#789) and have none — the ``cycles`` list is
   non-empty and at least one row was actually captured: ``captured: true`` with a verdict
   and a positive run count. A row with ``captured: true`` and every field null is the
   #1076 shape and fails by name. Rows recorded absent WITH a reason are disclosure, not
   evidence; they are allowed beside a captured row, never instead of one.

Usage:
    python scripts/dev/check_release_packages.py            # every semver tag in the repo
    python scripts/dev/check_release_packages.py --tag v1.7.0
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASES = REPO_ROOT / "site" / "content" / "releases"

SEMVER_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

#: The first release whose package carries cycle evidence. Packages before it were
#: backfilled from git after the fact (#789) and legitimately hold ``cycles: []``.
CYCLE_EVIDENCE_SINCE = (1, 6, 2)
#: The first release the site packages at all. The v0.1.x tags predate `site/` and the
#: capture script; they are releases in git only, and no package will ever be written for
#: them. Everything from here is checked.
PACKAGED_SINCE = (1, 0, 0)

CAPTURE_COMMAND = (
    "python scripts/maintainer/build_release_package.py {version} --cycle <cycle-id> "
    "--project <project>   # preview first, read the verdict and run count, then --write"
)


def version_of(tag: str) -> tuple[int, int, int] | None:
    match = SEMVER_TAG.match(tag)
    return tuple(int(part) for part in match.groups()) if match else None  # type: ignore[return-value]


def semver_tags(tags: list[str]) -> list[str]:
    """The plain ``vX.Y.Z`` tags among ``tags``, in version order."""
    return sorted((t for t in tags if version_of(t)), key=version_of)  # type: ignore[arg-type]


def repo_tags() -> list[str]:
    out = subprocess.run(
        ["git", "tag", "-l", "v*"], capture_output=True, text=True, check=True, cwd=REPO_ROOT
    )
    return out.stdout.split()


def _load_yaml(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def package_problems(tag: str, releases: Path = RELEASES) -> list[str]:
    """Every way the package for ``tag`` fails the two rules, as messages a person acts on."""
    version = version_of(tag)
    if version is None:
        return [f"{tag}: not a vMAJOR.MINOR.PATCH release tag — nothing to check"]
    if version < PACKAGED_SINCE:
        return []
    version_text = ".".join(str(part) for part in version)
    rel = f"site/content/releases/{tag}"
    capture = CAPTURE_COMMAND.format(version=version_text)
    target = releases / tag

    if not target.is_dir():
        return [
            f"{tag}: no release package at {rel}/ — cut step 7 was not done. Capture it:\n"
            f"    {capture}"
        ]
    problems = [
        f"{tag}: {rel}/{name} is missing — re-run the capture:\n    {capture}"
        for name in ("index.md", "package.yaml")
        if not (target / name).is_file()
    ]
    if problems:
        return problems

    try:
        package = _load_yaml(target / "package.yaml")
    except Exception as exc:  # noqa: BLE001 - a package that does not parse is a finding
        return [f"{tag}: {rel}/package.yaml does not parse: {exc}"]
    if package.get("tag") != tag:
        problems.append(f"{tag}: {rel}/package.yaml names tag {package.get('tag')!r}, not {tag}")
    if version >= CYCLE_EVIDENCE_SINCE:
        problems.extend(_cycle_evidence_problems(tag, rel, capture, package.get("cycles") or []))
    return problems


def _cycle_evidence_problems(tag: str, rel: str, capture: str, cycles: list) -> list[str]:
    """Rule 2: at least one cycle row was actually captured, and none of the captured rows is
    the #1076 hollow shape."""
    if not cycles:
        return [
            f"{tag}: {rel}/package.yaml carries no cycle evidence (cycles: []) — a release "
            f"is gated on a cycle, and the deploy it ran on is gone once it moves. Capture:\n"
            f"    {capture}"
        ]
    problems: list[str] = []
    captured = [row for row in cycles if row.get("captured") is True]
    absent = [row for row in cycles if row.get("captured") is not True]
    if not captured:
        reasons = "; ".join(
            f"{r.get('cycle_id')}: {r.get('reason') or 'no reason'}" for r in absent
        )
        problems.append(
            f"{tag}: every cycle row in {rel}/package.yaml is recorded absent ({reasons}) — "
            f"disclosure of a failed capture is not evidence. Re-capture while the deploy "
            f"is still up:\n    {capture}"
        )
    for row in captured:
        hollow = _hollow_fields(row)
        if hollow:
            problems.append(
                f"{tag}: cycle {row.get('cycle_id') or '<no cycle_id>'} in {rel}/package.yaml "
                f"is a hollow capture ({', '.join(hollow)}) — the #1076 shape: captured: true "
                f"with nothing captured. Re-capture with a running runtime API, a current "
                f"`squadops login` and the right --project:\n    {capture}"
            )
    return problems


def _hollow_fields(row: dict) -> list[str]:
    hollow = []
    if row.get("verdict") is None:
        hollow.append("verdict is null")
    run_count = row.get("run_count")
    if not isinstance(run_count, int) or isinstance(run_count, bool) or run_count < 1:
        hollow.append(f"run_count is {run_count!r}")
    if not isinstance(row.get("verified"), list):
        hollow.append("verified is not a list")
    return hollow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--tag", action="append", default=[], help="a tag to check (repeatable); default: all"
    )
    parser.add_argument(
        "--releases-dir", type=Path, default=RELEASES, help=argparse.SUPPRESS
    )  # for tests
    args = parser.parse_args(argv)

    tags = args.tag or semver_tags(repo_tags())
    problems: list[str] = []
    for tag in tags:
        problems.extend(package_problems(tag, args.releases_dir))

    if problems:
        print("release-packages: FAIL", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "  (CLAUDE.md, Release cut, step 7 — the package is captured AFTER the tag "
            "and committed; main stays red until it lands)",
            file=sys.stderr,
        )
        return 1
    print(f"release-packages: ok — {len(tags)} tag(s) have a captured package")
    return 0


if __name__ == "__main__":
    sys.exit(main())
