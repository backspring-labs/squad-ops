"""What commit a deploy records (scripts/dev/ops/source_hash.sh, #80).

The runtime-api image stamps this value on every cycle it creates. Bug caught: a build from
a modified tree claiming the clean commit, so a cycle's lineage names code it did not run;
and the opposite, a docs edit marking every deploy dirty so the marker means nothing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "ops" / "source_hash.sh"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "plan.md").write_text("plan\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def _hash(cwd: Path) -> str:
    return subprocess.run(
        ["bash", str(SCRIPT)], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_a_clean_tree_records_the_commit(repo):
    assert _hash(repo) == _git(repo, "rev-parse", "--short", "HEAD")


@pytest.mark.parametrize(
    "change",
    [
        lambda r: (r / "src" / "app.py").write_text("x = 2\n"),  # modified
        lambda r: (r / "src" / "new.py").write_text("y = 1\n"),  # untracked
        lambda r: (r / "pyproject.toml").write_text("[project]\n"),  # a copied root file
    ],
    ids=["modified-source", "untracked-source", "root-pyproject"],
)
def test_a_change_to_what_the_images_copy_is_dirty(repo, change):
    change(repo)
    assert _hash(repo) == _git(repo, "rev-parse", "--short", "HEAD") + "-dirty"


def test_a_change_outside_the_images_is_not_dirty(repo):
    (repo / "docs" / "plan.md").write_text("revised\n")
    assert _hash(repo) == _git(repo, "rev-parse", "--short", "HEAD")


def test_outside_a_checkout_it_is_unknown(tmp_path):
    assert _hash(tmp_path) == "unknown"
