#!/usr/bin/env python3
"""Worktree and branch hygiene: find what merged, keep its records, remove the rest.

1.8.2 plan §3.2 item 9, written from the 2026-09-24 cleanup, which found 18 worktrees and 86
local branches whose work had long merged. Two of those driver worktrees held the only copies of
the 1.7.4 and 1.7.5 verification-set records, in a gitignored ``var/`` that ``git status``
never shows. A worktree is disposable; what a driver wrote into it may not be.

Previews by default. ``--apply``, for each worktree whose work is merged:

1. copies every ``var/`` file the main checkout lacks into the main checkout's ``var/``; a file
   that exists there with different bytes is kept beside it as ``<stem>.<worktree><suffix>``
2. archives the whole ``var/`` under ``--archive-root/<worktree>-var/``
3. verifies both copies byte for byte, and only then
4. removes the worktree (never ``--force``) and deletes its branch

Then it deletes the merged branches no worktree holds and prunes worktree entries whose
directory is gone. Nothing is touched if it has uncommitted work, an open PR, a PR closed
unmerged, commits its merged PR did not carry, a real ``data/``, or a lock. Each of those is
named with its reason.

"Merged" is read from the branch's PR, because a squash merge leaves the branch off main's
history. A branch with no PR, or a detached worktree, is merged only if its head is on the
base (``origin/main``, else ``main``).

    python scripts/dev/worktree_hygiene.py
    python scripts/dev/worktree_hygiene.py --apply \\
        --archive-root ~/squadops-deploy-logs/worktree-var-archive
"""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checkouts import main_checkout  # noqa: E402

#: The ignored directory whose contents are evidence and are preserved before removal.
RECORDS_DIR = "var"
#: A real (not symlinked) ``data/`` in a worktree is a deploy's volume or a copy of one. This
#: tool never moves one; the worktree is kept and named.
DATA_DIR = "data"
BASE_BRANCH = "main"


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str  # OPEN | CLOSED | MERGED
    head_oid: str


PrLookup = Callable[[str], "PullRequest | None"]


@dataclass(frozen=True)
class Worktree:
    path: Path
    head: str
    branch: str | None  # None when detached
    locked: bool = False
    prunable: bool = False


@dataclass(frozen=True)
class RecordFile:
    rel: str  # relative to the worktree's var/
    state: str  # same | missing | differs


@dataclass
class WorktreeFinding:
    worktree: Worktree
    remove: bool
    reason: str
    records: list[RecordFile] = field(default_factory=list)


@dataclass
class BranchFinding:
    branch: str
    head: str
    delete: bool
    reason: str


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} (in {cwd}) failed: {proc.stderr.strip()}")
    return proc


def gh_pr_lookup(main: Path) -> PrLookup:
    """The branch's PR from GitHub. An open PR outranks a newer closed or merged one, because a
    branch name reused for new work after an old PR merged still holds that new work."""

    def lookup(branch: str) -> PullRequest | None:
        proc = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--head",
                branch,
                "--state",
                "all",
                "--limit",
                "20",
                "--json",
                "number,state,headRefOid",
            ],
            cwd=main,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise SystemExit(
                f"gh pr list --head {branch} failed: {proc.stderr.strip()} — a squash merge is "
                "recognised only by its PR, so nothing is judged without it"
            )
        return pick_pr(json.loads(proc.stdout or "[]"))

    return lookup


def pick_pr(prs: list[dict]) -> PullRequest | None:
    if not prs:
        return None
    open_prs = [p for p in prs if p["state"] == "OPEN"]
    chosen = max(open_prs or prs, key=lambda p: p["number"])
    return PullRequest(int(chosen["number"]), str(chosen["state"]), str(chosen["headRefOid"]))


def list_worktrees(main: Path) -> list[Worktree]:
    """Every worktree except the main one (``git worktree list`` names it first)."""
    blocks = git("worktree", "list", "--porcelain", cwd=main).stdout.strip().split("\n\n")
    out: list[Worktree] = []
    for block in blocks[1:]:
        fields: dict[str, str] = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            fields[key] = value
        branch = fields.get("branch", "").removeprefix("refs/heads/") or None
        out.append(
            Worktree(
                path=Path(fields["worktree"]),
                head=fields.get("HEAD", ""),
                branch=branch,
                locked="locked" in fields,
                prunable="prunable" in fields,
            )
        )
    return out


def base_ref(main: Path) -> str:
    remote = f"origin/{BASE_BRANCH}"
    found = git("rev-parse", "--verify", "--quiet", remote, cwd=main, check=False)
    return remote if found.returncode == 0 else BASE_BRANCH


def is_ancestor(main: Path, commit: str, of: str) -> bool:
    return git("merge-base", "--is-ancestor", commit, of, cwd=main, check=False).returncode == 0


def merged(
    main: Path, base: str, branch: str | None, head: str, pr_lookup: PrLookup
) -> tuple[bool, str]:
    pr = pr_lookup(branch) if branch else None
    if pr is not None:
        tag = f"PR #{pr.number}"
        if pr.state == "OPEN":
            return False, f"{tag} is open"
        if pr.state == "MERGED":
            if (
                head == pr.head_oid
                or is_ancestor(main, head, pr.head_oid)
                or is_ancestor(main, head, base)
            ):
                return True, f"{tag} merged"
            return False, f"{tag} merged, but the branch has commits it did not carry"
        if is_ancestor(main, head, base):
            return True, f"{tag} closed; its commits are on {base}"
        return False, f"{tag} closed unmerged"
    if is_ancestor(main, head, base):
        return True, f"no PR; its head is on {base}"
    return False, f"no PR, and its head is not on {base}"


def record_files(records: Path, main_records: Path) -> list[RecordFile]:
    out: list[RecordFile] = []
    for f in sorted(p for p in records.rglob("*") if p.is_file() and not p.is_symlink()):
        rel = f.relative_to(records).as_posix()
        twin = main_records / rel
        if not twin.exists():
            state = "missing"
        elif filecmp.cmp(f, twin, shallow=False):
            state = "same"
        else:
            state = "differs"
        out.append(RecordFile(rel, state))
    return out


def _real_dir_with_files(path: Path) -> int:
    if path.is_symlink() or not path.is_dir():
        return 0
    return sum(1 for p in path.rglob("*") if p.is_file())


def survey(main: Path, pr_lookup: PrLookup) -> tuple[list[WorktreeFinding], list[BranchFinding]]:
    base = base_ref(main)
    trees: list[WorktreeFinding] = []
    held = {git("branch", "--show-current", cwd=main).stdout.strip()}
    for wt in list_worktrees(main):
        if wt.branch:
            held.add(wt.branch)
        if wt.prunable:
            trees.append(WorktreeFinding(wt, True, "its directory is gone (prune)"))
            continue
        if wt.locked:
            trees.append(WorktreeFinding(wt, False, "locked"))
            continue
        dirty = git("status", "--porcelain", cwd=wt.path).stdout.splitlines()
        if dirty:
            trees.append(WorktreeFinding(wt, False, f"uncommitted work in {len(dirty)} paths"))
            continue
        data_files = _real_dir_with_files(wt.path / DATA_DIR)
        if data_files:
            trees.append(
                WorktreeFinding(
                    wt, False, f"a real {DATA_DIR}/ with {data_files} files; move it by hand"
                )
            )
            continue
        ok, reason = merged(main, base, wt.branch, wt.head, pr_lookup)
        records = wt.path / RECORDS_DIR
        found = (
            record_files(records, main / RECORDS_DIR)
            if records.is_dir() and not records.is_symlink()
            else []
        )
        trees.append(WorktreeFinding(wt, ok, reason, found))

    branches: list[BranchFinding] = []
    refs = git(
        "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads", cwd=main
    ).stdout.splitlines()
    for line in refs:
        name, _, head = line.partition(" ")
        if name == BASE_BRANCH or name in held:
            continue
        ok, reason = merged(main, base, name, head, pr_lookup)
        branches.append(BranchFinding(name, head, ok, reason))
    return trees, branches


def suffixed(rel: str, tag: str) -> str:
    """``a/roll-01.json`` → ``a/roll-01.<tag>.json``; ``a/.head_pin`` → ``a/.head_pin.<tag>``."""
    p = Path(rel)
    return (p.parent / f"{p.stem}.{tag}{p.suffix}").as_posix()


def _place(src: Path, dest: Path) -> str | None:
    """Copy ``src`` to ``dest`` unless an identical file is already there. A different file
    already at ``dest`` is never overwritten."""
    if dest.exists():
        return None if filecmp.cmp(src, dest, shallow=False) else f"{dest} exists and differs"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return None


def preserve(main: Path, finding: WorktreeFinding, archive_root: Path) -> list[str]:
    """Copy the records into the main checkout and the archive, then verify both copies.
    Returns the problems; an empty list means the worktree may go."""
    wt = finding.worktree
    records = wt.path / RECORDS_DIR
    tag = wt.path.name
    archive = archive_root / f"{tag}-{RECORDS_DIR}"
    problems: list[str] = []
    for rf in finding.records:
        src = records / rf.rel
        home = main / RECORDS_DIR / (suffixed(rf.rel, tag) if rf.state == "differs" else rf.rel)
        for dest in (home, archive / rf.rel):
            problem = _place(src, dest)
            if problem:
                problems.append(problem)
            elif not filecmp.cmp(src, dest, shallow=False):
                problems.append(f"{dest} does not match {src} after the copy")
    return problems


def check_archive_root(archive_root: Path, main: Path, trees: Sequence[WorktreeFinding]) -> None:
    root = archive_root.expanduser().resolve()
    for checkout in (main, *(f.worktree.path for f in trees)):
        if root == checkout or checkout in root.parents:
            raise SystemExit(
                f"--archive-root {root} is inside the checkout {checkout}; an archive there dies "
                "with it (or with `git clean -X`)"
            )


def apply(
    main: Path,
    trees: Sequence[WorktreeFinding],
    branches: Sequence[BranchFinding],
    archive_root: Path,
) -> list[str]:
    check_archive_root(archive_root, main, trees)
    archive_root = archive_root.expanduser().resolve()
    problems: list[str] = []
    for f in trees:
        if not f.remove:
            continue
        if f.worktree.prunable:
            git("worktree", "prune", cwd=main)
            continue
        kept = preserve(main, f, archive_root)
        if kept:
            problems += [f"{f.worktree.path} kept: {p}" for p in kept]
            continue
        removed = git("worktree", "remove", str(f.worktree.path), cwd=main, check=False)
        if removed.returncode != 0:
            problems.append(f"{f.worktree.path} kept: {removed.stderr.strip()}")
            continue
        if f.worktree.branch:
            git("branch", "-D", f.worktree.branch, cwd=main)
    for b in branches:
        if b.delete:
            git("branch", "-D", b.branch, cwd=main)
    return problems


def render(trees: Sequence[WorktreeFinding], branches: Sequence[BranchFinding]) -> str:
    lines = [f"WORKTREES ({len(trees)} besides the main checkout)"]
    for f in trees:
        wt = f.worktree
        what = wt.branch or f"detached {wt.head[:8]}"
        verdict = "REMOVE" if f.remove else "keep  "
        lines.append(f"  {verdict} {wt.path}  [{what}]  {f.reason}")
        if f.records:
            counts = {s: sum(1 for r in f.records if r.state == s) for s in ("missing", "differs")}
            lines.append(
                f"         {RECORDS_DIR}/: {len(f.records)} files; {counts['missing']} missing "
                f"from the main checkout, {counts['differs']} differ (kept suffixed)"
            )
    lines.append(f"BRANCHES ({len(branches)} held by no worktree)")
    for b in branches:
        lines.append(f"  {'DELETE' if b.delete else 'keep  '} {b.branch}  {b.reason}")
    return "\n".join(lines)


def main(
    argv: Sequence[str] | None = None,
    *,
    cwd: Path | None = None,
    pr_lookup: PrLookup | None = None,
) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="act; without it, only preview")
    ap.add_argument(
        "--archive-root",
        type=Path,
        help="required with --apply: where each worktree's var/ is archived, outside any checkout",
    )
    args = ap.parse_args(argv)
    if args.apply and args.archive_root is None:
        ap.error("--apply requires --archive-root")
    main_path = main_checkout(cwd or Path.cwd())
    trees, branches = survey(main_path, pr_lookup or gh_pr_lookup(main_path))
    print(render(trees, branches))
    if not args.apply:
        print("\npreview only; --apply --archive-root <dir> acts")
        return 0
    problems = apply(main_path, trees, branches, args.archive_root)
    for p in problems:
        print(f"  ✗ {p}")
    print(f"\napplied; {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
