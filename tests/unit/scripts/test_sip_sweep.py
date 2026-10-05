"""#1980: the cut's SIP sweep, read from the delivery ledgers.

On a SIP tree of its own (``SIP_SWEEP_ROOT``): one SIP whose every row shipped or dropped, one with
a part placed in the release and still open, one whose issue closed with its row still placed, and
one placed in a later release. Then ``check_pr_closure.sh`` on a release branch, as the workflow
runs it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "maintainer"))
import sip_sweep  # noqa: E402

_TABLE = (
    "## Delivery ledger (current as of 2026-10-05)\n\n| part | status | where |\n|---|---|---|\n"
)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    accepted = tmp_path / "sips" / "accepted"
    accepted.mkdir(parents=True)
    (accepted / "SIP-0001-Done.md").write_text(
        "# A\n\n" + _TABLE + "| a | **shipped** | v2.0.0 |\n| b | **dropped** by §5a | — |\n"
    )
    (accepted / "SIP-0002-Open.md").write_text(
        "# B\n\n"
        + _TABLE
        + "| due now | **placed** | 2.1.0, #10 |\n"
        + "| closed | **placed** | 2.1.0, #11 |\n"
        + "| later | **placed** | 2.2.0, #12 |\n"
    )
    (tmp_path / "sips" / "open-issues.json").write_text(
        '{"refreshed": "x", "open": {"10": [], "12": []}}'
    )
    monkeypatch.setenv("SIP_SWEEP_ROOT", str(tmp_path))
    return tmp_path


def test_the_sweep_reads_promotion_re_placement_and_stale_rows(tree):
    """Bugs caught: a SIP with nothing left not offered for promotion; a part placed in the
    release and unshipped passing the cut unnoticed; a shipped part whose row still says placed;
    and a later release's part reported as overdue."""
    s = sip_sweep.sweep("2.1.0", tree)

    assert s.promotable == ["SIP-0001"]
    assert s.replace == [("SIP-0002", 10)]
    assert s.stale == [("SIP-0002", 11)]
    assert s.outstanding() == ["#10", "#11", "SIP-0001"]


def _closure(body: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PR_HEAD_REF": "release/2.1.0", "GH_REPO": "backspring-labs/squad-ops"}
    return subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / "dev" / "check_pr_closure.sh")],
        input=body,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.mark.parametrize(
    ("line", "missing"),
    [
        ("SIP sweep: promote SIP-0001; re-place SIP-0002 #10 to 2.3.0; move #11 to shipped", None),
        ("SIP sweep: promote SIP-0001; move #11 to shipped", "#10"),
        ("SIP sweep: nothing — all current", "#10 #11 SIP-0001"),
    ],
)
def test_a_release_prs_sweep_line_names_everything_outstanding(tree, line, missing):
    """Bug caught: a hand-written sweep line that leaves out what the ledgers say, the cut step
    #1151's presence check could not see."""
    result = _closure(f"No issue: the cut.\n{line}\n")

    assert (result.returncode == 0) is (missing is None), result.stderr
    if missing:
        assert f"outstanding: {missing}" in result.stderr
