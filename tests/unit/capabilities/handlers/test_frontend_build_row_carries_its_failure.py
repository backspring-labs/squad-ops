"""A failed frontend build must say why, and the signature must be able to move (#1468).

Measured on the 1.7.5 deploy-A React shakeout (`cyc_a20d0a02be67`): `frontend_build` failed,
rejected the run, and recorded `reason: ""`. The boot audit then installed, built and booted
the same delivered application and passed. The cause of the build failure was unrecoverable
from every store — the row, the agent log, the vault.

Bug classes guarded:

- **a required check refusing a roll for a reason nobody can read.** The row dropped
  `exit_code`, `error` AND `stderr`, all of which `BuildCheckResult` carries, while the
  SKIP path recorded its reason — the useful case was the one thrown away;
- **a signature element that can never show progress.** `_reason_token` falls back to the
  bare status when `reason` is absent, so every build failure rendered the identical
  `frontend_build||failed`. An element that cannot vary pins round-over-round movement at
  REPEAT no matter what a repair fixed, and the run terminated `plan_defect` at round 1 on
  exactly that. This is the #878/#761 collapse on the check those fixes did not reach;
- **the stderr leaking into `reason`**, which would be the opposite defect: evidence text in
  a signature makes a genuine repeat read as a shift, so A4 never terminates and the run
  burns its whole budget. Over-discrimination is the expensive direction.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.cycle.qa_test import _frontend_build_row
from squadops.capabilities.handlers.test_runner import BuildCheckResult
from squadops.cycles.correction_signature import failure_signature
from squadops.cycles.verification_normalize import row_is_blocking_failure

pytestmark = [pytest.mark.unit, pytest.mark.domain_capabilities]


def _evidence(row: dict) -> dict:
    return {"validation_result": {"checks": [row]}}


class TestAFailedBuildSaysWhy:
    def test_the_row_carries_exit_code_error_and_stderr(self):
        fb = BuildCheckResult(
            ran=True,
            ok=False,
            exit_code=1,
            error="frontend build failed (exit 1)",
            stderr="Could not resolve './index.css' from 'src/main.jsx'",
        )

        row = _frontend_build_row(fb)

        assert row["passed"] is False
        assert row["exit_code"] == 1
        assert row["reason"] == "frontend build failed (exit 1)"
        assert "Could not resolve './index.css'" in row["detail"]

    def test_a_passing_build_carries_no_failure_evidence(self):
        """The control. A row that reports evidence on success would make every green build
        look like a diagnosis, and `passed` is what three readers key on."""
        row = _frontend_build_row(BuildCheckResult(ran=True, ok=True, exit_code=0))

        assert row == {"check": "frontend_build", "passed": True}
        assert not row_is_blocking_failure(row)

    def test_a_skipped_build_still_reports_its_not_executed_reason(self):
        """The #407 path must be unchanged — a skip is not a failure, and `missing_tooling`
        is the #306 case a required frontend_build has to block on."""
        row = _frontend_build_row(
            BuildCheckResult(ran=False, error="npm not found — Node.js not installed")
        )

        assert row["executed"] is False
        assert row["reason"] == "missing_tooling"
        assert "passed" not in row

    def test_the_failing_row_still_reads_as_a_blocking_failure(self):
        """`_frontend_build_failed` and the #650 target widening key on `passed is False`;
        so does `row_is_blocking_failure`. Adding fields must not disturb that."""
        row = _frontend_build_row(BuildCheckResult(ran=True, ok=False, exit_code=1))

        assert row_is_blocking_failure(row) is True


class TestTheSignatureCanMove:
    def test_two_different_build_failures_no_longer_collapse(self):
        """The consequence that cost the roll. Before the fix both rounds rendered
        `frontend_build||failed` and the element could never show progress."""
        round0 = _frontend_build_row(
            BuildCheckResult(
                ran=True, ok=False, exit_code=1, error="frontend build failed (exit 1)"
            )
        )
        round1 = _frontend_build_row(
            BuildCheckResult(
                ran=True, ok=False, exit_code=2, error="frontend build failed (exit 2)"
            )
        )

        assert failure_signature(_evidence(round0)) != failure_signature(_evidence(round1))

    def test_an_identical_failure_still_repeats_byte_for_byte(self):
        """The other half, and the one over-discrimination would break: a genuine repeat must
        stay identical or A4 never terminates and the run burns its whole budget."""
        fb = BuildCheckResult(
            ran=True, ok=False, exit_code=1, error="frontend build failed (exit 1)"
        )

        assert failure_signature(_evidence(_frontend_build_row(fb))) == failure_signature(
            _evidence(_frontend_build_row(fb))
        )

    def test_differing_stderr_alone_does_not_move_the_signature(self):
        """Evidence text must stay OUT of the signature. Two runs of one defect whose stderr
        differs only in a path or a timing must still read as a repeat."""
        a = _frontend_build_row(
            BuildCheckResult(
                ran=True,
                ok=False,
                exit_code=1,
                error="frontend build failed (exit 1)",
                stderr="build failed in 812ms\n/tmp/ws-a/src/x.jsx",
            )
        )
        b = _frontend_build_row(
            BuildCheckResult(
                ran=True,
                ok=False,
                exit_code=1,
                error="frontend build failed (exit 1)",
                stderr="build failed in 1104ms\n/tmp/ws-b/src/x.jsx",
            )
        )

        assert a["detail"] != b["detail"]
        assert failure_signature(_evidence(a)) == failure_signature(_evidence(b))

    def test_a_long_stderr_is_bounded(self):
        """Unbounded evidence on a row that is stored per round is how an artifact store
        grows without anyone deciding to."""
        row = _frontend_build_row(
            BuildCheckResult(ran=True, ok=False, exit_code=1, stderr="x" * 10_000)
        )

        assert len(row["detail"]) < 2200
        assert row["detail"].startswith("...")
