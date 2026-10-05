"""#1979: a PR that closes an issue carrying a SIP part changes that SIP's ledger, or says why not.

A fake ``gh`` first on PATH answers the issues API with a labelled open issue and the PR files API
from a fixture, so the whole guard runs as the closure workflow runs it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "check_pr_closure.sh"

_FAKE_GH = """#!/usr/bin/env bash
case "$*" in
  *pulls/*/commits*) echo "fix: something" ;;
  *pulls/*/files*) cat "$FAKE_FILES" ;;
  *issues/1884*) echo '{"state": "open", "labels": [{"name": "sip:0109"}, {"name": "bug"}]}' ;;
  *issues/*) echo '{"state": "open", "labels": []}' ;;
  *) exit 1 ;;
esac
"""


def _run(tmp_path: Path, body: str, files: list[str]) -> subprocess.CompletedProcess:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(_FAKE_GH)
    gh.chmod(0o755)
    fixture = tmp_path / "files.txt"
    fixture.write_text("\n".join(files) + "\n")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GH_REPO": "backspring-labs/squad-ops",
        "PR_HEAD_REF": "fix/x",
        "PR_TITLE": "fix: x",
        "PR_NUMBER": "2100",
        "FAKE_FILES": str(fixture),
    }
    return subprocess.run(
        ["bash", str(SCRIPT)], input=body, capture_output=True, text=True, env=env, check=False
    )


@pytest.mark.parametrize(
    ("body", "files", "passes"),
    [
        # The ledger changes with the issue: the row can move from placed to shipped.
        ("Closes #1884\n", ["src/x.py", "sips/accepted/SIP-0109-Campaign-Orchestration.md"], True),
        # The bug: a SIP part closed with its ledger left "placed".
        ("Closes #1884\n", ["src/x.py"], False),
        # Another SIP's ledger does not count.
        ("Closes #1884\n", ["sips/accepted/SIP-0105-Stack-Blueprint-Contract.md"], False),
        # A stated reason passes; an empty one does not.
        (
            "Closes #1884\nSIP ledger: n/a — the row was already shipped in #2012\n",
            ["src/x.py"],
            True,
        ),
        ("Closes #1884\nSIP ledger: n/a —\n", ["src/x.py"], False),
        # An issue with no sip: label asks for nothing.
        ("Closes #1999\n", ["src/x.py"], True),
    ],
)
def test_closing_a_sip_issue_needs_its_ledger_or_a_reason(tmp_path, body, files, passes):
    result = _run(tmp_path, body, files)

    assert (result.returncode == 0) is passes, result.stderr
    if not passes:
        assert "carries sip:0109" in result.stderr
