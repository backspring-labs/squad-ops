"""#1621: the closure guard reads what the squash merge closes, not only the PR body.

GitHub's squash merge makes the PR title the commit subject and the PR's commit messages its
body, and a closing keyword in either closes the issue whatever the body says. #1620's body
said ``Refs #1619 — remaining: …`` and passed; a ``Closes #1619`` trailer in a revision commit
closed #1619 on merge, and it was reopened by hand.

The shell tests put a fake ``gh`` first on PATH, answering the commits API from a fixture and
the issues API as open, so the whole guard runs as CI runs it.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_DEV = Path(__file__).resolve().parents[3] / "scripts" / "dev"
SCRIPT = _DEV / "check_pr_closure.sh"
_spec = importlib.util.spec_from_file_location("closing_refs", _DEV / "closing_refs.py")
closing_refs = importlib.util.module_from_spec(_spec)
sys.modules["closing_refs"] = closing_refs
_spec.loader.exec_module(closing_refs)

_FAKE_GH = """#!/usr/bin/env bash
case "$*" in
  *pulls/*/commits*) [ -f "$FAKE_COMMITS" ] && cat "$FAKE_COMMITS" || exit 1 ;;
  *issues/*) echo '{"state": "open"}' ;;
  *) exit 1 ;;
esac
"""


def _run(tmp_path, body: str, title: str, commits: str | None) -> subprocess.CompletedProcess:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(_FAKE_GH)
    gh.chmod(0o755)
    fixture = tmp_path / "commits.txt"
    if commits is not None:
        fixture.write_text(commits)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GH_REPO": "backspring-labs/squad-ops",
        "PR_HEAD_REF": "feature/x",
        "PR_TITLE": title,
        "PR_NUMBER": "1620",
        "FAKE_COMMITS": str(fixture),
    }
    return subprocess.run(
        ["bash", str(SCRIPT)], input=body, capture_output=True, text=True, env=env, check=False
    )


def test_a_commit_trailer_that_closes_what_the_body_refs_fails(tmp_path):
    """The #1620 shape, entered at the script as the workflow runs it. Bug this catches: the
    guard passing a body that deliberately refs an issue while a commit trailer closes it."""
    body = "Refs #1619 — remaining: the deploy still serves the old caps.\n"
    commits = "fix(caps): flat cap\n\nCloses #1619\n\nrevise: say what remains\n"

    result = _run(tmp_path, body, "fix(caps): the flat cap", commits)

    assert result.returncode == 1
    assert "a commit message closes #1619 but the PR body does not" in result.stderr


def test_a_title_that_names_an_issue_after_a_closing_keyword_fails_however_negated(tmp_path):
    """Bug this catches: "does not close #N" in a title, which is the squash commit's subject
    and closes #N on merge."""
    result = _run(tmp_path, "No issue: tooling.\n", "chore: does not close #1619", "chore\n")

    assert result.returncode == 1
    assert "the PR title closes #1619" in result.stderr


def test_commits_that_agree_with_the_body_pass(tmp_path):
    body = "Closes #1621\n"
    commits = "fix(closure): read the commits\n\nCloses #1621\n"

    result = _run(tmp_path, body, "fix(closure): read the commits", commits)

    assert result.returncode == 0, result.stderr


def test_unreadable_commits_refuse_rather_than_pass(tmp_path):
    """Bug this catches: a failed commits read treated as "no commit closes anything"."""
    result = _run(tmp_path, "No issue: tooling.\n", "chore: x", None)

    assert result.returncode == 1
    assert "could not read PR #1620's commit messages" in result.stderr


@pytest.mark.parametrize(
    ("body", "title", "commits", "expected"),
    [
        # A quoted closure in the body is not a closure, so the commit contradicts it.
        ("See `Closes #7`.\nNo issue: x\n", "t", "Closes #7", ["commit message closes #7"]),
        # Backticks in a commit message protect nothing: the commit text is not rendered.
        ("No issue: x\n", "t", "quoting `Fixes #8` here", ["commit message closes #8"]),
        ("Closes #9\n", "t", "Resolved: #9", []),
        ("No issue: x\n", "fixes: #10 and #11", "", ["title closes #10"]),
    ],
)
def test_merge_contradictions(body, title, commits, expected):
    problems = closing_refs.merge_contradictions(body, title, commits)
    assert len(problems) == len(expected)
    for fragment, problem in zip(expected, problems, strict=True):
        assert fragment in problem
