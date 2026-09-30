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
            # Only screenshots whose files were committed: a named file that is missing would
            # render a broken image here as it would on the release page.
            "screenshots": [
                name
                for name in data.get("screenshots") or []
                if (directory / "assets" / Path(name).name).is_file()
            ],
            "showcase": data.get("showcase") or {},
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


# --- What a cycle delivers (#1039) -------------------------------------------------------------
#
# The newest release whose cut captured screenshots, presented on their own page. Generated, not
# authored: screenshots dropped into a page by hand go stale the moment the next release ships,
# and these move with the packages. The pictures, the cycle they are of and the reason it was
# chosen are all the package's, recorded at its cut (`build_release_package.py --showcase`).

#: Screenshot filename prefix → the section it is shown under, in page order. The filenames are
#: written as captions at capture (CLAUDE.md, release cut step 7), so the prefix names the view.
SHOWCASE_SECTIONS = (
    (
        "delivered-app-",
        "The delivered application",
        "The application the cycle built, booted from its stored tree and seeded.",
    ),
    (
        "prefect-flow-run-",
        "The run, in Prefect",
        "The implementation run's timeline: each task, and each correction round, as it ran.",
    ),
)


def _caption(name: str) -> str:
    """The release page's caption rule (`build_release_package.render`): the filename's stem."""
    return Path(name).stem.replace("-", " ").replace("_", " ")


def _showcase_page(pkg: dict | None) -> list[str]:
    lines = ["# What a cycle delivers", ""]
    if pkg is None:
        return lines + [
            "No release has captured screenshots yet. Each release's evidence is on its "
            "[release page](releases/index.md).",
            "",
        ]
    tag = pkg["tag"]
    show = pkg["showcase"]
    released = f", released {pkg['date']}" if pkg["date"] else ""
    lines += [
        f"Screenshots from the newest release whose cut captured them: **{tag}**{released}.",
    ]
    if show.get("cycle_id"):
        role = f" (a {show['role']} cycle)" if show.get("role") else ""
        lines += [
            f"They are of one cycle, `{show['cycle_id']}`{role}. The release says why that one:",
            "",
            f"> {str(show.get('reason', '')).strip()}",
        ]
    lines += [
        "",
        "This page is generated when the site is built, from that release's package, and moves "
        "when a newer release captures its own. Every cycle the release cites, with its verdict "
        f"and checks, is on the [{tag} page](releases/{tag}/index.md).",
        "",
    ]
    placed: set[str] = set()
    for prefix, heading, intro in SHOWCASE_SECTIONS:
        shots = [n for n in pkg["screenshots"] if Path(n).name.startswith(prefix)]
        if not shots:
            continue
        lines += [f"## {heading}", "", intro, ""]
        for name in shots:
            lines += [
                f"![{_caption(name)}](releases/{tag}/assets/{Path(name).name})",
                f"*{_caption(name)}*",
                "",
            ]
            placed.add(name)
    others = [n for n in pkg["screenshots"] if n not in placed]
    if others:
        lines += ["## Other views", ""]
        for name in others:
            lines += [
                f"![{_caption(name)}](releases/{tag}/assets/{Path(name).name})",
                f"*{_caption(name)}*",
                "",
            ]
    return lines


showcased = next((pkg for pkg in packages if pkg["screenshots"]), None)
with mkdocs_gen_files.open("showcase.md", "w") as fh:
    fh.write("\n".join(_showcase_page(showcased)))

print(
    "gen_releases: showcase from "
    + (f"{showcased['tag']} ({len(showcased['screenshots'])} screenshots)" if showcased else "none")
)
