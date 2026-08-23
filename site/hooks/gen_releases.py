"""Build the releases index from the captured packages (mkdocs-gen-files).

This hook only PRESENTS. Each release's evidence was captured at its cut by
`scripts/maintainer/build_release_package.py` and committed; nothing here
queries a live system, so a release page says the same thing in a year that it
says today.

Only semver directories are listed. Pre-1.0 `warmboot` tags are development
milestones rather than releases, and the filter keeps them out even if someone
regenerates packages across every tag.
"""

from __future__ import annotations

import re
from pathlib import Path

import mkdocs_gen_files
import yaml

RELEASES = Path(__file__).resolve().parents[1] / "content" / "releases"
SEMVER = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def version_key(name: str) -> tuple[int, int, int]:
    major, minor, patch = SEMVER.match(name).groups()
    return int(major), int(minor), int(patch)


packages = []
for directory in RELEASES.iterdir() if RELEASES.is_dir() else []:
    if not directory.is_dir() or not SEMVER.match(directory.name):
        continue
    manifest = directory / "package.yaml"
    if not manifest.is_file():
        continue
    data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    packages.append(
        {
            "tag": directory.name,
            "version": data.get("version", directory.name.lstrip("v")),
            "date": data.get("date", ""),
            "prs": len(data.get("pull_requests") or []),
            "sips": len(data.get("sip_moves") or []),
            "cycles": len(data.get("cycles") or []),
        }
    )

packages.sort(key=lambda p: version_key(p["tag"]), reverse=True)

lines = [
    "# Releases",
    "",
    "Every release, with the pull requests that made it, the improvement proposals "
    "that changed status, and — where it was captured at the cut — the verification "
    "evidence from the cycles that validated it.",
    "",
    "Squad Ops follows semantic versioning with an even/odd convention on the minor: "
    "**even minors carry features**, led by a headline proposal; **odd minors are "
    "feature-free stabilisation releases**. Patches ship from either lane at any time.",
    "",
    "| Version | Released | PRs | Proposals | Cycles |",
    "|---|---|---:|---:|---:|",
]
for pkg in packages:
    lines.append(
        f"| [{pkg['tag']}]({pkg['tag']}/index.md) | {pkg['date'] or '—'} "
        f"| {pkg['prs']} | {pkg['sips'] or '—'} | {pkg['cycles'] or '—'} |"
    )
lines += [
    "",
    '!!! note "Why cycle evidence is thin on older releases"',
    "",
    "    A release package is captured at the cut, not reconstructed afterwards — the",
    "    verification evidence lives in a running system and is gone once the deploy",
    "    moves. Pull requests and proposal transitions are recoverable from git for",
    "    every release; cycle results only exist from the point capture began. The",
    "    gap is disclosed rather than backfilled with guesses.",
    "",
]

with mkdocs_gen_files.open("releases/index.md", "w") as fh:
    fh.write("\n".join(lines))

print(f"gen_releases: indexed {len(packages)} releases")
