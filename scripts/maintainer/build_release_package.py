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

# What counts as a closing reference lives in one place, shared with the pre-merge guard
# (#1135). This script used to match the RAW body with a narrower regex, which credited
# quoted text as closure — the v1.6.5 capture claimed #1114 closed #1096, #1106 and
# #999999, all lifted out of that PR's own test log — and under-credited the tenses
# GitHub honours. A package is committed as a snapshot the site never re-derives, so a
# wrong cell is permanent unless caught at preview.
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))
from closing_refs import closing_refs, quoted_refs  # noqa: E402


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


#: The subject GitHub writes for a merged pull request. Only these name a PR: a "merge
#: main" commit whose subject mentions a PR number is not that PR merging again (#1369 —
#: the v1.7.3 package listed #1328 twice).
_MERGE_SUBJECT = re.compile(r"^Merge pull request #(\d+)\b")


def merged_pr_numbers(subjects: list[str]) -> list[str]:
    """The PR numbers a list of merge-commit subjects names, each once, newest first."""
    return list(
        dict.fromkeys(m.group(1) for s in subjects if (m := _MERGE_SUBJECT.match(s.strip())))
    )


def merged_prs(previous: str | None, tag: str) -> list[dict]:
    """PRs merged in the range, newest first, with their linked issues."""
    span = f"{previous}..{tag}" if previous else tag
    subjects = run("git", "log", "--merges", "--format=%s", span).splitlines()
    numbers = merged_pr_numbers(subjects)
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
                "closes": closing_refs(data.get("body") or ""),
                "quoted_not_closed": quoted_refs(data.get("body") or ""),
                "merged_at": (data.get("mergedAt") or "")[:10],
            }
        )
    return prs


_FRONTMATTER_FIELD = re.compile(r"^(sip_uid|status):\s*'?\"?([^'\"\n]*)", re.M)


def _sip_frontmatter(ref: str, path: str) -> dict[str, str] | None:
    """The proposal's ``status`` and ``sip_uid`` at ``ref`` — the lifecycle fact itself,
    which lives in the frontmatter ``update_sip_status.py`` stamps — or None when the
    file is absent at that ref."""
    text = run("git", "show", f"{ref}:{path}", check=False)
    if not text:
        return None
    head = text[3:].split("\n---", 1)[0] if text.startswith("---") else ""
    return {key: value.strip() for key, value in _FRONTMATTER_FIELD.findall(head)}


def _sip_transitions(previous: str | None, tag: str) -> list[dict]:
    """Every proposal touched in the range with its status before and after.

    #1369: the v1.7.3 package reported three SIPs as ``new → implemented`` because they
    were *modified* under ``sips/implemented/`` — amended in place on that line — and the
    old reading took a modified file under a status directory as an arrival there. The
    transition is the frontmatter's ``status`` at each end of the range, never the path's
    presence in the diff; a promotion renames the file (it gains its number), so the two
    sides are paired by ``sip_uid``, the identity ``update_sip_status.py`` keeps.
    """
    if not previous:
        return []
    lines = run("git", "diff", "--name-status", f"{previous}..{tag}", "--", "sips/").splitlines()
    before: dict[str, tuple[str, str]] = {}  # sip_uid -> (stem, status) at previous
    after: dict[str, tuple[str, str]] = {}  # sip_uid -> (stem, status) at tag
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        code = parts[0]
        # A rename is a delete of the old path and an add of the new one.
        paths = parts[1:] if code.startswith("R") else [parts[-1]] * 2
        old_path, new_path = paths[0], paths[-1]
        for ref, path, side in ((previous, old_path, before), (tag, new_path, after)):
            bits = Path(path).parts
            # Proposals only — a .gitkeep or a registry edit is not a lifecycle move.
            if len(bits) < 3 or not path.endswith(".md"):
                continue
            if (code.startswith("A") and side is before) or (
                code.startswith("D") and side is after
            ):
                continue
            fm = _sip_frontmatter(ref, path)
            if fm is None:
                continue
            uid = fm.get("sip_uid") or f"path:{Path(path).stem}"
            side[uid] = (Path(path).stem, fm.get("status") or bits[1])
    transitions = []
    for uid in sorted(set(before) | set(after), key=lambda u: (after.get(u) or before[u])[0]):
        stem_before, status_before = before.get(uid, (None, None))
        stem_after, status_after = after.get(uid, (None, None))
        transitions.append(
            {
                "sip": stem_after or stem_before,
                "from": status_before,
                "to": status_after,
                "in_place": status_before == status_after and status_after is not None,
            }
        )
    return transitions


def sip_moves(previous: str | None, tag: str) -> list[dict]:
    """Proposals whose lifecycle status changed in the range (frontmatter, not path)."""
    return [
        {"sip": t["sip"], "from": t["from"], "to": t["to"]}
        for t in _sip_transitions(previous, tag)
        if not t["in_place"]
    ]


def sip_amendments(previous: str | None, tag: str) -> list[dict]:
    """Proposals edited in the range whose status did not change — amended in place,
    listed apart so an amendment of an implemented SIP never reads as a promotion."""
    return [
        {"sip": t["sip"], "status": t["to"]}
        for t in _sip_transitions(previous, tag)
        if t["in_place"]
    ]


def changelog_section(version: str) -> str:
    """The release's own prose, straight from CHANGELOG.md — not regenerated."""
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[)", re.DOTALL | re.MULTILINE
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _absent(cycle_id: str, reason: str, role: str | None = None) -> dict:
    """A cycle whose evidence could not be captured, WITH why — never a silent gap."""
    entry = {"cycle_id": cycle_id, "captured": False, "reason": reason}
    if role:
        entry["role"] = role
    return entry


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


#: What a captured cycle WAS to the release — the page must say it, or a fault-injected
#: diagnostic's `rejected` reads as a failed roll. Named on the command line as
#: ``--cycle <id>:<role>``; a bare id is allowed for older captures and carries no role.
CYCLE_ROLES = ("counted", "shakeout", "diagnostic", "void")
_ROLE_NOTES = {
    "counted": "",
    "shakeout": " — non-counting: the deploy's shakeout, read for seam findings",
    "diagnostic": (
        " — fault-injected, non-counting: its verdict is not a verdict about the squad (#1251)"
    ),
    "void": " — void: the roll was stopped and the set restarted (the record's §0)",
}


def parse_cycle_arg(arg: str) -> tuple[str, str | None]:
    """``cyc_x`` → (``cyc_x``, None); ``cyc_x:diagnostic`` → (``cyc_x``, ``diagnostic``).
    An unknown role is refused naming the vocabulary — a typo would otherwise ship a page
    that labels a diagnostic as nothing at all."""
    cycle_id, sep, role = arg.partition(":")
    if not sep:
        return cycle_id, None
    if role not in CYCLE_ROLES:
        raise SystemExit(f"--cycle {arg}: unknown role {role!r}; one of {', '.join(CYCLE_ROLES)}")
    return cycle_id, role


def cycle_evidence(
    cycle_ids: list[str], api: str, project: str, roles: dict[str, str] | None = None
) -> list[dict]:
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
    roles = roles or {}
    for cycle_id in cycle_ids:
        role = roles.get(cycle_id)
        url = f"{api}/api/v1/projects/{project}/cycles/{cycle_id}"
        args = ["curl", "-s", "--max-time", "10"]
        if token:
            args += ["-H", f"Authorization: Bearer {token}"]
        raw = run(*args, url, check=False)

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            evidence.append(
                _absent(cycle_id, f"runtime API at {api} did not answer at capture time", role)
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
                    role,
                )
            )
            continue
        outcome = data.get("cycle_outcome") or {}
        if outcome.get("verdict") is None:
            evidence.append(
                _absent(cycle_id, f"cycle {cycle_id} carries no verification roll-up", role)
            )
            continue
        evidence.append(
            {
                "cycle_id": cycle_id,
                **({"role": role} if role else {}),
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


def cycle_count_line(cycles: list[dict]) -> str:
    """``9 cycles`` — and, when any carries a role, ``22 cycles (9 counted, 6 shakeout, …)``."""
    by_role: dict[str, int] = {}
    for cycle in cycles:
        if cycle.get("role"):
            by_role[cycle["role"]] = by_role.get(cycle["role"], 0) + 1
    line = f"{len(cycles)} cycles"
    if by_role:
        parts = [f"{by_role[r]} {r}" for r in CYCLE_ROLES if r in by_role]
        line += f" ({', '.join(parts)})"
    return line


def _sip_link(stem: str, current: set[str]) -> str:
    # A proposal is renamed when it is promoted (it gains its number), so a historical
    # move often names a file that no longer exists. The move is the fact and stays
    # recorded either way; the link is a convenience and is emitted only when the page
    # is actually there.
    return f"[{stem}](../../design/sips/{stem}.md)" if stem in current else stem


def _sip_sections(package: dict) -> list[str]:
    """The lifecycle moves and, apart from them, the in-place amendments (#1369)."""
    out: list[str] = []
    current = {path.stem for path in (REPO_ROOT / "sips").glob("*/*.md")}
    moves = package["sip_moves"]
    if moves:
        out += ["## Improvement proposals", "", "| Proposal | From | To |", "|---|---|---|"]
        for move in moves:
            out.append(
                f"| {_sip_link(move['sip'], current)} | {move['from'] or 'new'} | "
                f"{move['to'] or 'removed'} |"
            )
        out.append("")
    amendments = package.get("sip_amendments") or []
    if amendments:
        out += [
            "## Improvement proposals amended in place",
            "",
            "No lifecycle change — each was edited under the status it already had "
            "(a post-acceptance amendment, CLAUDE.md step 5a).",
            "",
            "| Proposal | Status |",
            "|---|---|",
        ]
        for amendment in amendments:
            out.append(f"| {_sip_link(amendment['sip'], current)} | {amendment['status']} |")
        out.append("")
    return out


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

    out += _sip_sections(package)

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
                f"**Verdict:** `{cycle.get('verdict')}` · **Runs:** {cycle.get('run_count')}"
                + (
                    f" · **Role:** {cycle['role']}{_ROLE_NOTES.get(cycle['role'], '')}"
                    if cycle.get("role")
                    else ""
                ),
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
    parsed = [parse_cycle_arg(a) for a in args.cycle]
    cycle_ids = [c for c, _ in parsed]
    cycle_roles = {c: r for c, r in parsed if r}
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
        "sip_amendments": sip_amendments(previous, tag),
        "cycles": (
            cycle_evidence(cycle_ids, args.api, args.project, cycle_roles) if cycle_ids else []
        ),
        "screenshots": screenshots,
    }

    page = render(version, tag, package)

    if not args.write:
        print(f"--- preview: {tag} ({previous or 'initial'}..{tag}) ---\n")
        print(page)
        print(
            f"\n--- {len(package['pull_requests'])} PRs, {len(package['sip_moves'])} SIP moves, "
            f"{len(package['sip_amendments'])} SIP amendments in place, "
            f"{cycle_count_line(package['cycles'])}, {len(screenshots)} screenshots ---"
        )
        # An empty Closes cell has two causes — the PR closed nothing, or it only quoted
        # the syntax. Naming the quoted ones makes the difference readable here, which is
        # the one place a wrong cell can still be caught (#1135).
        quoted = [(pr["number"], pr["quoted_not_closed"]) for pr in package["pull_requests"]]
        for number, refs in quoted:
            if refs:
                print(
                    f"note: PR #{number} mentions {' '.join(f'#{n}' for n in refs)} "
                    "inside quoted text — not credited as closures"
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

    # A preview diagnostic, not evidence: it says why a Closes cell is empty, which
    # only matters while someone can still act on it. Keeping it out of the snapshot
    # leaves the committed schema unchanged (#1135).
    for pr in package["pull_requests"]:
        pr.pop("quoted_not_closed", None)

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
