"""``scripts/dev/hooks/pre-push``: which commits it scans for a held-out step value
(``heldout_text_scan.py``), entered with git's own hook input in a throwaway repository and a
fake interpreter that records the range it's asked to scan.

What bugs would these catch?
- a branch rebased onto main, then force-pushed, scanned over main's own history since its old
  base, so a word main added and the branch never touched refuses the push (#2551, 2026-10-22);
- a fast-forward scanned from main rather than from its last push;
- a new branch scanned from anywhere but where it leaves main.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "hooks" / "pre-push"
ZERO = "0" * 40


def _git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x"}  # fmt: skip
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env
    ).stdout.strip()


def _commit(repo: Path, name: str, text: str) -> str:
    (repo / name).write_text(text)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    """main at m1; the branch b1 on it, pushed; main moves to m2; the branch rebased onto m2 (b2)
    and fast-forwarded on m2 (b3)."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    m1 = _commit(r, "base.txt", "base\n")
    _git(r, "checkout", "-q", "-b", "branch")
    b1 = _commit(r, "branch.txt", "the branch's own line\n")
    _git(r, "checkout", "-q", "main")
    m2 = _commit(r, "main.txt", "a line main added after the branch left it\n")
    _git(r, "checkout", "-q", "branch")
    _git(r, "rebase", "-q", "main")
    b2 = _git(r, "rev-parse", "HEAD")
    b3 = _commit(r, "more.txt", "the branch's next line\n")
    _git(r, "update-ref", "refs/remotes/origin/main", m2)
    return r, {"m1": m1, "b1": b1, "m2": m2, "b2": b2, "b3": b3}


def _run(repo: Path, tmp_path: Path, line: str) -> list[str]:
    seen = tmp_path / "ranges"
    fake = tmp_path / "python"
    fake.write_text(f'#!/bin/sh\nfor a; do last="$a"; done\necho "$last" >> "{seen}"\n')
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    env = {
        **os.environ,
        "SQUADOPS_HELDOUT_SUITES": "/nowhere/suite.yaml",
        "SQUADOPS_PYTHON": str(fake),
    }
    done = subprocess.run(
        ["bash", str(HOOK)], cwd=repo, input=line + "\n", capture_output=True, text=True, env=env
    )
    assert done.returncode == 0, done.stderr
    return seen.read_text().split() if seen.exists() else []


@pytest.mark.parametrize(
    ("local", "remote", "scanned"),
    [
        ("b2", "b1", "origin/main...{b2}"),
        ("b3", "b2", "{b2}..{b3}"),
        ("b2", None, "origin/main...{b2}"),
    ],
    ids=[
        "a-rebased-branch-is-scanned-from-main",
        "a-fast-forward-from-its-last-push",
        "a-new-branch-from-main",
    ],
)
def test_the_hook_scans_what_the_push_adds(repo, tmp_path, local, remote, scanned):
    r, sha = repo
    remote_sha = sha[remote] if remote else ZERO
    line = f"refs/heads/branch {sha[local]} refs/heads/branch {remote_sha}"

    assert _run(r, tmp_path, line) == [scanned.format(**sha)]


def test_a_deletion_scans_nothing_and_no_suite_means_no_scan(repo, tmp_path):
    r, sha = repo
    assert _run(r, tmp_path, f"(delete) {ZERO} refs/heads/branch {sha['b1']}") == []
    done = subprocess.run(
        ["bash", str(HOOK)], cwd=r, input=f"refs/heads/branch {sha['b2']} refs/heads/branch {sha['b1']}\n",
        capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "SQUADOPS_HELDOUT_SUITES"},
    )  # fmt: skip
    assert done.returncode == 0


def test_from_a_worktree_with_no_venv_the_hook_finds_the_main_checkouts_and_scans(repo, tmp_path):
    """#2800: in a worktree with no ``.venv`` the hook reads the main worktree from ``git worktree
    list``. It stopped reading after the first line, so with a long listing git died of SIGPIPE,
    ``pipefail`` failed the assignment, and the hook exited 141 before its scan, saying nothing.
    The push failed with only git's "failed to push some refs" (2026-10-29)."""
    r, sha = repo
    linked = tmp_path / "linked"
    _git(r, "worktree", "add", "-q", "--detach", str(linked), sha["b2"])
    seen = tmp_path / "ranges"
    (r / ".venv" / "bin").mkdir(parents=True)
    fake = r / ".venv" / "bin" / "python"
    fake.write_text(f'#!/bin/sh\nfor a; do last="$a"; done\necho "$last" >> "{seen}"\n')
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    real_git = subprocess.run(["which", "git"], capture_output=True, text=True).stdout.strip()
    shim = tmp_path / "bin"
    shim.mkdir()
    # A listing far past a pipe's buffer, as a checkout with many worktrees gives: the main
    # worktree first, as git lists it.
    (shim / "git").write_text(
        "#!/bin/sh\n"
        'case "$*" in *"worktree list"*)\n'
        f'  echo "worktree {r}"\n'
        '  i=0; while [ $i -lt 20000 ]; do echo "worktree /elsewhere/$i"; echo "HEAD 0"; echo; i=$((i+1)); done\n'
        "  exit 0;;\n"
        "esac\n"
        f'exec {real_git} "$@"\n'
    )
    (shim / "git").chmod(0o755)
    env = {
        **{k: v for k, v in os.environ.items() if k != "SQUADOPS_PYTHON"},
        "SQUADOPS_HELDOUT_SUITES": "/nowhere/suite.yaml",
        "PATH": f"{shim}:{os.environ['PATH']}",
    }
    line = f"refs/heads/branch {sha['b2']} refs/heads/branch {ZERO}"
    done = subprocess.run(
        ["bash", str(HOOK)], cwd=linked, input=line + "\n", capture_output=True, text=True, env=env
    )

    assert done.returncode == 0, (done.returncode, done.stderr)
    assert seen.read_text().split() == [f"origin/main...{sha['b2']}"]
