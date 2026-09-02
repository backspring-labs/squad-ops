"""#1151: a release PR's body must record cut step 5 — the SIP promotion sweep.

The closure guard (`scripts/dev/check_pr_closure.sh`) is a shell script; these tests run
it with an opt-out body (no closing reference, so it never calls `gh`) and the head ref the
workflow passes. Bug caught: a `release/*` PR merging without a `SIP sweep:` line — the
unguarded step CLAUDE.md names, missed at every cut it was not written down for.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "check_pr_closure.sh"


def _run(body: str, head_ref: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PR_HEAD_REF": head_ref, "GH_REPO": "backspring-labs/squad-ops"}
    return subprocess.run(
        ["bash", str(SCRIPT)], input=body, capture_output=True, text=True, env=env, check=False
    )


@pytest.mark.parametrize("head_ref", ["release/1.7.1", "release/2.0.0"])
def test_a_release_pr_without_the_sweep_line_fails_by_name(head_ref):
    result = _run("No issue: the cut.\n", head_ref)
    assert result.returncode == 1
    assert "SIP sweep:" in result.stderr
    assert "step 5" in result.stderr


def test_a_release_pr_with_the_sweep_line_passes():
    body = "No issue: the cut.\n\nSIP sweep: nothing promoted — SIP-0106 stays accepted (§1.2a).\n"
    result = _run(body, "release/1.7.1")
    assert result.returncode == 0, result.stderr


def test_an_empty_sweep_line_does_not_count():
    result = _run("No issue: the cut.\nSIP sweep:   \n", "release/1.7.1")
    assert result.returncode == 1


def test_a_feature_pr_is_not_asked_for_a_sweep():
    result = _run("No issue: docs only.\n", "feat/1151-guards")
    assert result.returncode == 0, result.stderr
