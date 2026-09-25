"""The worktree hygiene sweep (1.8.2 plan §3.2 item 9), on a fixture of the 2026-09-24 cleanup.

What bug would these catch? The cleanup's two risks: removing a worktree whose gitignored
``var/`` held the only copy of a line's records (1.7.4 and 1.7.5 were one command from gone),
and removing work that was not merged. A squash-merged branch is off main's history, so a sweep
that judges by ancestry alone either keeps everything or, loosened, deletes live work.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "worktree_hygiene", REPO_ROOT / "scripts" / "dev" / "worktree_hygiene.py"
)
hygiene = importlib.util.module_from_spec(_spec)
sys.modules["worktree_hygiene"] = hygiene  # dataclasses resolve annotations via it
_spec.loader.exec_module(hygiene)


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(cwd: Path, name: str) -> str:
    (cwd / name).write_text(name)
    _git("add", name, cwd=cwd)
    _git("commit", "-q", "-m", name, cwd=cwd)
    return _git("rev-parse", "HEAD", cwd=cwd)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def cleanup(tmp_path):
    """The 2026-09-24 shape in miniature. A driver worktree holds records the main checkout
    lacks, one that differs and one it shares. Merged, open, dirty and run-on worktrees sit
    beside it, one holds a real data/, and there are stale branches of each kind."""
    main = tmp_path / "squad-ops"
    main.mkdir()
    _git("init", "-q", "-b", "main", cwd=main)
    (main / ".gitignore").write_text("var/\ndata/\n__pycache__/\n")
    _git("add", ".gitignore", cwd=main)
    _git("commit", "-q", "-m", "init", cwd=main)
    sets = "verification_sets/1-7-4-fastapi-react"
    _write(main / "var" / sets / "roll-01.json", "shared")
    _write(main / "var" / sets / "roll-02.json", "main's copy")

    def add(name: str, *, branch: str | None = None) -> Path:
        path = tmp_path / name
        where = ["-b", branch, str(path)] if branch else ["--detach", str(path), "main"]
        _git("worktree", "add", "-q", *where, cwd=main)
        return path

    driver = add("driver-1-7-4")
    _write(driver / "var" / sets / "roll-01.json", "shared")
    _write(driver / "var" / sets / "roll-02.json", "the driver's copy")
    _write(driver / "var" / sets / "roll-03.json", "only here")
    _write(driver / "var" / sets / ".head_pin", "abc1234")
    _write(driver / "__pycache__" / "x.pyc", "disposable")

    heads: dict[str, str] = {}
    for name, branch in (
        ("feat-merged", "feature/merged"),
        ("feat-open", "feature/open"),
        ("feat-dirty", "feature/dirty"),
        ("feat-late", "feature/late"),
    ):
        wt = add(name, branch=branch)
        heads[branch] = _commit(wt, f"{name}.txt")
    (tmp_path / "feat-dirty" / "notes.txt").write_text("unsaved")
    heads["feature/late@pr"] = heads["feature/late"]
    heads["feature/late"] = _commit(tmp_path / "feat-late", "after-the-merge.txt")
    _write(add("deploy-copy") / "data" / "artifacts" / "a.json", "{}")

    for branch in ("old/merged-pr", "old/ancestor", "old/unmerged", "old/closed"):
        _git("branch", branch, "main", cwd=main)
    for branch in ("old/merged-pr", "old/unmerged", "old/closed"):
        _git("switch", "-q", branch, cwd=main)
        heads[branch] = _commit(main, f"{branch.replace('/', '-')}.txt")
    _git("switch", "-q", "main", cwd=main)

    prs = {
        "feature/merged": hygiene.PullRequest(1, "MERGED", heads["feature/merged"]),
        "feature/open": hygiene.PullRequest(2, "OPEN", heads["feature/open"]),
        "feature/dirty": hygiene.PullRequest(3, "MERGED", heads["feature/dirty"]),
        "feature/late": hygiene.PullRequest(4, "MERGED", heads["feature/late@pr"]),
        "old/merged-pr": hygiene.PullRequest(5, "MERGED", heads["old/merged-pr"]),
        "old/closed": hygiene.PullRequest(6, "CLOSED", heads["old/closed"]),
    }
    return main, tmp_path, prs.get


def _worktrees(main: Path) -> set[str]:
    return {w.path.name for w in hygiene.list_worktrees(main)}


def _branches(main: Path) -> set[str]:
    return set(_git("for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=main).split())


def test_apply_reproduces_the_cleanup(cleanup, tmp_path):
    """The whole sweep, entered at ``main`` as the operator runs it. Bug this catches: a
    worktree removed before its records exist elsewhere, a differing record overwritten in the
    main checkout, or unmerged work swept with the merged."""
    main, root, lookup = cleanup
    archive = tmp_path / "archive"
    sets = Path("verification_sets/1-7-4-fastapi-react")

    rc = hygiene.main(["--apply", "--archive-root", str(archive)], cwd=main, pr_lookup=lookup)

    assert rc == 0
    var = main / "var" / sets
    assert (var / "roll-03.json").read_text() == "only here"
    assert (var / ".head_pin").read_text() == "abc1234"
    assert (var / "roll-02.json").read_text() == "main's copy"
    assert (var / "roll-02.driver-1-7-4.json").read_text() == "the driver's copy"
    kept = archive / "driver-1-7-4-var" / sets
    assert {p.name: p.read_text() for p in kept.iterdir()} == {
        "roll-01.json": "shared",
        "roll-02.json": "the driver's copy",
        "roll-03.json": "only here",
        ".head_pin": "abc1234",
    }
    assert _worktrees(main) == {"feat-open", "feat-dirty", "feat-late", "deploy-copy"}
    assert _branches(main) == {
        "main",
        "feature/open",
        "feature/dirty",
        "feature/late",
        "old/unmerged",
        "old/closed",
    }


def test_the_preview_names_every_reason_and_changes_nothing(cleanup, capsys):
    """Bug this catches: a preview that acts, or one that says "keep" without the reason a
    person needs to decide what to do by hand."""
    main, _, lookup = cleanup
    before = (_worktrees(main), _branches(main), sorted((main / "var").rglob("*")))

    assert hygiene.main([], cwd=main, pr_lookup=lookup) == 0

    assert (_worktrees(main), _branches(main), sorted((main / "var").rglob("*"))) == before
    out = capsys.readouterr().out
    for expected in (
        "PR #2 is open",
        "uncommitted work in 1 paths",
        "PR #4 merged, but the branch has commits it did not carry",
        "a real data/ with 1 files",
        "PR #6 closed unmerged",
        "no PR, and its head is not on main",
        "no PR; its head is on main",
        "4 files; 2 missing from the main checkout, 1 differ",
    ):
        assert expected in out, expected


def test_a_record_that_cannot_be_placed_keeps_the_worktree(cleanup, tmp_path, capsys):
    """Bug this catches: removal after a failed preservation. An archive that already holds a
    different file under the same name must not be overwritten, and the worktree must stay."""
    main, root, lookup = cleanup
    archive = tmp_path / "archive"
    _write(archive / "driver-1-7-4-var/verification_sets/1-7-4-fastapi-react/roll-03.json", "other")

    rc = hygiene.main(["--apply", "--archive-root", str(archive)], cwd=main, pr_lookup=lookup)

    assert rc == 1
    assert "driver-1-7-4" in _worktrees(main)
    assert "roll-03.json exists and differs" in capsys.readouterr().out


def test_an_archive_inside_a_checkout_is_refused(cleanup):
    """Bug this catches: an archive under the main checkout's ``var/``, which ``git clean -X``
    removes along with the records it was meant to back up."""
    main, _, lookup = cleanup
    with pytest.raises(SystemExit, match="is inside the checkout"):
        hygiene.main(
            ["--apply", "--archive-root", str(main / "var" / "archive")],
            cwd=main,
            pr_lookup=lookup,
        )
    assert "driver-1-7-4" in _worktrees(main)


def test_apply_without_an_archive_root_is_refused(cleanup):
    main, _, lookup = cleanup
    with pytest.raises(SystemExit):
        hygiene.main(["--apply"], cwd=main, pr_lookup=lookup)


@pytest.mark.parametrize(
    ("prs", "expected"),
    [
        ([], None),
        (
            [
                {"number": 9, "state": "MERGED", "headRefOid": "a"},
                {"number": 7, "state": "OPEN", "headRefOid": "b"},
            ],
            hygiene.PullRequest(7, "OPEN", "b"),
        ),
        (
            [
                {"number": 3, "state": "MERGED", "headRefOid": "a"},
                {"number": 8, "state": "CLOSED", "headRefOid": "c"},
            ],
            hygiene.PullRequest(8, "CLOSED", "c"),
        ),
    ],
)
def test_an_open_pr_outranks_a_newer_closed_one(prs, expected):
    """Bug this catches: a branch name reused for new work after its first PR merged, judged by
    the old merged PR and swept while the new one is open."""
    assert hygiene.pick_pr(prs) == expected


def test_a_failed_pr_lookup_refuses_rather_than_guessing(monkeypatch, tmp_path):
    """Bug this catches: gh unavailable read as "no PR", which turns every squash-merged
    branch into "not on main" at best and, if ancestry were loosened, live work into "merged"."""
    monkeypatch.setattr(
        hygiene.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout="", stderr="auth required"),
    )
    with pytest.raises(SystemExit, match="auth required"):
        hygiene.gh_pr_lookup(tmp_path)("feature/x")
