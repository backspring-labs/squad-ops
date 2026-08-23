#!/usr/bin/env python3
"""Capture a release's evidence package (maintainer-only, run once at the cut).

**Capture, not query.** The site build is hermetic — no database, no running
stack, no delivered apps. So this runs at the cut, snapshots what is true then,
and writes a package that is committed alongside the release. The site renders
it and never re-derives it.

That is the same rule the measurement windows follow, for the same reason: a
release page that re-queried a live system would silently change when the data
moved, and you would lose the ability to say what was true at the cut.

Usage (step 4g of the cut checklist, after the CHANGELOG rotation):

    python scripts/maintainer/build_release_package.py 1.6.1            # preview
    python scripts/maintainer/build_release_package.py 1.6.1 --write
    python scripts/maintainer/build_release_package.py 1.6.1 --write \
        --cycle cyc_8b569ce34074 --cycle cyc_18931c371a55

Screenshots are manual: drop them in the release's ``assets/`` directory and
re-run. Whatever is there is indexed; nothing is fabricated.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASES = REPO_ROOT / "site" / "content" / "releases"
CLOSES = re.compile(r"\b(?:closes|fixes|resolves)\s+#(\d+)", re.IGNORECASE)


def run(*args: str, check: bool = True) -> str:
    result = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(args)}\n{result.stderr.strip()}")
    return result.stdout.strip()


def previous_tag(tag: str) -> str | None:
    """The tag immediately before ``tag`` in version order."""
    tags = run("git", "tag", "--sort=-v:refname").splitlines()
    if tag not in tags:
        raise SystemExit(f"tag {tag} not found — is the release tagged yet?")
    index = tags.index(tag)
    return tags[index + 1] if index + 1 < len(tags) else None


def merged_prs(previous: str | None, tag: str) -> list[dict]:
    """PRs merged in the range, newest first, with their linked issues."""
    span = f"{previous}..{tag}" if previous else tag
    subjects = run("git", "log", "--merges", "--format=%s", span).splitlines()
    numbers = [m.group(1) for s in subjects if (m := re.search(r"#(\d+)", s))]
    prs: list[dict] = []
    for number in numbers:
        raw = run(
            "gh",
            "pr",
            "view",
            number,
            "--json",
            "number,title,author,labels,body,mergedAt",
            check=False,
        )
        if not raw:
            prs.append(
                {
                    "number": int(number),
                    "title": "(unavailable)",
                    "author": "",
                    "labels": [],
                    "closes": [],
                }
            )
            continue
        data = json.loads(raw)
        prs.append(
            {
                "number": data["number"],
                "title": data["title"],
                "author": (data.get("author") or {}).get("login", ""),
                "labels": [label["name"] for label in data.get("labels", [])],
                "closes": sorted({int(n) for n in CLOSES.findall(data.get("body") or "")}),
                "merged_at": (data.get("mergedAt") or "")[:10],
            }
        )
    return prs


def sip_moves(previous: str | None, tag: str) -> list[dict]:
    """Proposals that changed lifecycle status in the range.

    A promotion is a delete from one status directory and an add to another, so
    the same stem appearing on both sides is a transition rather than two edits.
    """
    if not previous:
        return []
    lines = run("git", "diff", "--name-status", f"{previous}..{tag}", "--", "sips/").splitlines()
    removed: dict[str, str] = {}
    added: dict[str, str] = {}
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        code, path = parts[0], parts[-1]
        bits = Path(path).parts
        # Proposals only — a .gitkeep or a registry edit is not a lifecycle move.
        if len(bits) < 3 or not path.endswith(".md"):
            continue
        status, stem = bits[1], Path(path).stem
        (removed if code.startswith("D") else added)[stem] = status
    moves = []
    for stem, to_status in sorted(added.items()):
        moves.append({"sip": stem, "from": removed.get(stem), "to": to_status})
    return moves


def changelog_section(version: str) -> str:
    """The release's own prose, straight from CHANGELOG.md — not regenerated."""
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[)", re.DOTALL | re.MULTILINE
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _absent(cycle_id: str, reason: str) -> dict:
    """A cycle whose evidence could not be captured, WITH why — never a silent gap."""
    return {"cycle_id": cycle_id, "captured": False, "reason": reason}


def _bearer_token() -> str:
    """The CLI's cached access token, or "" — the API requires one (#1076).

    Read from the same store `squadops login` writes, so a maintainer who can drive
    the CLI can capture a package without a second credential path.
    """
    try:
        from squadops.cli.auth import load_cached_token

        cached = load_cached_token()
        return cached.access_token if cached else ""
    except Exception:  # noqa: BLE001 - capture must degrade to a disclosed absence
        return ""


def cycle_evidence(cycle_ids: list[str], api: str, project: str) -> list[dict]:
    """Verification roll-up per named cycle, or a recorded reason it is absent.

        Absence is disclosed, never silently omitted — an unreachable API and a cycle that
        genuinely produced nothing must not look the same later.

        That promise was not kept, and the failure was invisible in exactly the way the
        docstring warns about (#1076). Four defects compounded, each silent:

          - the route was `/api/v1/cycles/{id}`; the real one is project-scoped
          - no Authorization header, and the API requires one
          - the roll-up field is `cycle_outcome`, not `outcome`
          - and the guard caught only `JSONDecodeError` — so `{"detail": "Not Found"}`,
            being perfectly valid JSON, was recorded as `captured: True` with every
            field null

    The fourth is what hid the first three. A capture that cannot distinguish "the API
    said no" from "the cycle produced nothing" is not a disclosure mechanism, so the
    shape check below is the guard: the roll-up must actually be present, or this is
    recorded as absent WITH the reason.
    """
    evidence = []
    token = _bearer_token()
    for cycle_id in cycle_ids:
        url = f"{api}/api/v1/projects/{project}/cycles/{cycle_id}"
        args = ["curl", "-s", "--max-time", "10"]
        if token:
            args += ["-H", f"Authorization: Bearer {token}"]
        raw = run(*args, url, check=False)

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            evidence.append(
                _absent(cycle_id, f"runtime API at {api} did not answer at capture time")
            )
            continue
        if not isinstance(data, dict) or "cycle_outcome" not in data:
            detail = data.get("detail") if isinstance(data, dict) else None
            evidence.append(
                _absent(
                    cycle_id,
                    f"runtime API at {api} returned no cycle roll-up"
                    + (f" ({detail})" if detail else "")
                    + (" — no cached CLI token; run `squadops login`" if not token else ""),
                )
            )
            continue
        outcome = data.get("cycle_outcome") or {}
        if outcome.get("verdict") is None:
            evidence.append(_absent(cycle_id, f"cycle {cycle_id} carries no verification roll-up"))
            continue
        evidence.append(
            {
                "cycle_id": cycle_id,
                "captured": True,
                "status": data.get("status"),
                "verdict": outcome.get("verdict"),
                "verified": sorted(set(outcome.get("verified", []))),
                "failed": outcome.get("failed", []),
                "required_unmet": outcome.get("required_unmet", []),
                "unverified": [
                    u.get("check_id") or u.get("check") for u in outcome.get("unverified", [])
                ],
                "run_count": outcome.get("run_count") or len(data.get("runs", [])),
            }
        )
    return evidence


def render(version: str, tag: str, package: dict) -> str:
    """The release page. Prose comes from CHANGELOG; the rest is enumerated."""
    date = package["date"]
    out = [
        "---",
        f"title: v{version}",
        "---",
        "",
        f"# v{version}",
        "",
        f"**Released {date}** · [tag `{tag}`](https://github.com/backspring-labs/"
        f"squad-ops/releases/tag/{tag})",
        "",
    ]

    if package["narrative"]:
        out += [package["narrative"], ""]

    prs = package["pull_requests"]
    out += [f"## Merged pull requests ({len(prs)})", ""]
    if prs:
        out += ["| PR | Title | Closes |", "|---|---|---|"]
        for pr in prs:
            closes = " ".join(
                f"[#{n}](https://github.com/backspring-labs/squad-ops/issues/{n})"
                for n in pr["closes"]
            )
            link = f"[#{pr['number']}](https://github.com/backspring-labs/squad-ops/pull/{pr['number']})"
            out.append(f"| {link} | {pr['title']} | {closes or '—'} |")
        out.append("")

    moves = package["sip_moves"]
    if moves:
        out += ["## Improvement proposals", "", "| Proposal | From | To |", "|---|---|---|"]
        # A proposal is renamed when it is promoted (it gains its number), so a
        # historical move often names a file that no longer exists. The move is
        # the fact and stays recorded either way; the link is a convenience and
        # is emitted only when the page is actually there.
        current = {path.stem for path in (REPO_ROOT / "sips").glob("*/*.md")}
        for move in moves:
            label = (
                f"[{move['sip']}](../../design/sips/{move['sip']}.md)"
                if move["sip"] in current
                else move["sip"]
            )
            out.append(f"| {label} | {move['from'] or 'new'} | {move['to']} |")
        out.append("")

    cycles = package["cycles"]
    if cycles:
        out += ["## Cycle evidence", ""]
        for cycle in cycles:
            out.append(f"### `{cycle['cycle_id']}`")
            out.append("")
            if not cycle.get("captured"):
                out += [
                    '!!! warning "Not captured"',
                    "",
                    f"    {cycle.get('reason', 'no evidence recorded')}",
                    "",
                ]
                continue
            out += [
                f"**Verdict:** `{cycle.get('verdict')}` · **Runs:** {cycle.get('run_count')}",
                "",
                "| | Checks |",
                "|---|---|",
                f"| Verified | {', '.join(cycle.get('verified') or []) or '—'} |",
                f"| Failed | {', '.join(cycle.get('failed') or []) or '—'} |",
                f"| Required unmet | {', '.join(cycle.get('required_unmet') or []) or '—'} |",
                f"| Never executed | {', '.join(cycle.get('unverified') or []) or '—'} |",
                "",
            ]

    shots = package["screenshots"]
    if shots:
        out += ["## Screenshots", ""]
        for shot in shots:
            caption = Path(shot).stem.replace("-", " ").replace("_", " ")
            out += [f"![{caption}](assets/{Path(shot).name})", f"*{caption}*", ""]

    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="release version, e.g. 1.6.1")
    parser.add_argument("--previous", help="previous tag (auto-detected if omitted)")
    parser.add_argument(
        "--cycle",
        action="append",
        default=[],
        help="cycle id representing this release; repeatable",
    )
    parser.add_argument("--api", default="http://localhost:8001", help="runtime API base URL")
    parser.add_argument("--project", default="group_run", help="project the --cycle ids belong to")
    parser.add_argument(
        "--write", action="store_true", help="write the package; default is a preview to stdout"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing package (see the immutability note in the write path)",
    )
    args = parser.parse_args()

    version = args.version.lstrip("v")
    tag = f"v{version}"
    previous = args.previous or previous_tag(tag)
    target = RELEASES / tag

    assets = target / "assets"
    screenshots = sorted(
        p.name for p in assets.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )

    package = {
        "version": version,
        "tag": tag,
        "previous_tag": previous,
        "date": run("git", "log", "-1", "--format=%ad", "--date=short", tag),
        "commit": run("git", "rev-list", "-n", "1", tag),
        "narrative": changelog_section(version),
        "pull_requests": merged_prs(previous, tag),
        "sip_moves": sip_moves(previous, tag),
        "cycles": cycle_evidence(args.cycle, args.api, args.project) if args.cycle else [],
        "screenshots": screenshots,
    }

    page = render(version, tag, package)

    if not args.write:
        print(f"--- preview: {tag} ({previous or 'initial'}..{tag}) ---\n")
        print(page)
        print(
            f"\n--- {len(package['pull_requests'])} PRs, {len(package['sip_moves'])} SIP moves, "
            f"{len(package['cycles'])} cycles, {len(screenshots)} screenshots ---"
        )
        print("re-run with --write to commit the package")
        return 0

    import yaml

    # A captured package is immutable evidence, so overwriting one is a
    # deliberate act. Everything except the cycle section regenerates
    # deterministically from git, which makes an accidental re-run look correct
    # while silently dropping the one part that cannot be recovered: the cycle
    # evidence lived in a deploy that has since moved.
    existing_path = target / "package.yaml"
    if existing_path.is_file() and not args.force:
        raise SystemExit(
            f"{existing_path.relative_to(REPO_ROOT)} already exists.\n"
            "A captured package is evidence, not a build artifact — re-running would "
            "re-derive the git-recoverable parts and lose anything captured live.\n"
            "Pass --force to overwrite (previously captured cycle evidence is carried "
            "forward when this run supplies none)."
        )

    if existing_path.is_file():
        prior = yaml.safe_load(existing_path.read_text(encoding="utf-8")) or {}
        prior_cycles = prior.get("cycles") or []
        if prior_cycles and not package["cycles"]:
            package["cycles"] = prior_cycles
            page = render(version, tag, package)
            print(
                f"--force: carried forward {len(prior_cycles)} captured cycle(s) — "
                "this run supplied none"
            )

    target.mkdir(parents=True, exist_ok=True)
    assets.mkdir(exist_ok=True)
    (target / "index.md").write_text(page, encoding="utf-8")
    existing_path.write_text(
        yaml.safe_dump(package, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    print(f"wrote {target.relative_to(REPO_ROOT)}/index.md and package.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
