"""The merge check both lanes merge through (`scripts/dev/safe_merge.sh`; the 2.9 plan §11).

Main's CI group cancels a run in progress when a newer commit lands, and two lanes merge to main.
Each refusal here is a merge that went wrong once:

- 2026-10-23: a "completed" read was the secret scan's, CI was still running, and the merge
  cancelled the other lane's run on main;
- 2026-10-24: a merge made 39 s after the other lane's, on a reading from the previous merge;
- 2026-11-04: a PR whose own CI run was still queued had no failing check row yet.

- 2026-11-26: two waiters released by the same run on main each merged as soon as its checks
  held, within seconds of each other. The merge lock is for that one.

The tests put a fake ``gh`` and a fake ``git`` first on PATH. Each answers the calls the script
makes with the reading the test sets, and ``gh`` logs every call, so a test can read whether the
merge was asked for and with which head. The lock is a file: the fake creates it for the API's
ref creation, refuses when it exists, and deletes it, as GitHub does a ref.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "safe_merge.sh"

HEAD = "a" * 40
TIP = "b" * 40
OLDER = "c" * 40
MERGE = f"pr merge 3249 --squash --delete-branch --match-head-commit {HEAD}"

_FAKE_GH = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG"
case "$*" in
  "pr view "*"state,isDraft,headRefOid"*) printf '%s\\n' "$FAKE_PR" ;;
  "run list --workflow CI --commit "*) printf '%s\\n' "$FAKE_HEAD_RUN" ;;
  "pr view "*"statusCheckRollup"*) printf '%s\\n' "$FAKE_CHECKS" ;;
  "run list --branch main "*)
    n=$(cat "$FAKE_MAIN_COUNT" 2>/dev/null || echo 0)
    n=$((n + 1))
    echo "$n" > "$FAKE_MAIN_COUNT"
    line=$(sed -n "${n}p" "$FAKE_MAIN_RUNS")
    [ -n "$line" ] || line=$(tail -n 1 "$FAKE_MAIN_RUNS")
    printf '%s\\n' "$line"
    ;;
  "pr merge "*) exit "${FAKE_MERGE_RC:-0}" ;;
  "pr view "*"state,mergeCommit"*) printf '%s\\n' "$FAKE_AFTER" ;;
  "api -X POST "*"/git/refs "*)
    [ -e "$FAKE_LOCK" ] && exit 1
    printf '%s' "${*##*sha=}" > "$FAKE_LOCK"
    ;;
  "api -X DELETE "*"/git/refs/heads/safe-merge-lock") rm "$FAKE_LOCK" 2>/dev/null || exit 1 ;;
  "api "*"/git/ref/heads/safe-merge-lock "*) cat "$FAKE_LOCK" 2>/dev/null || exit 1 ;;
  *) exit 1 ;;
esac
"""

_FAKE_GIT = """#!/usr/bin/env bash
case "$*" in
  "fetch -q origin main") exit 0 ;;
  "rev-parse origin/main") cat "$FAKE_TIP_FILE" ;;
  *) exit 1 ;;
esac
"""

#: The script's wait between polls. A test's ``between_polls`` is what the world does meanwhile.
_FAKE_SLEEP = """#!/usr/bin/env bash
[ -n "${FAKE_BETWEEN_POLLS:-}" ] && bash "$FAKE_BETWEEN_POLLS"
exit 0
"""


def _run(
    tmp_path,
    *args: str,
    main_runs: tuple[str, ...] | None = None,
    lock: str | None = None,
    between_polls: str | None = None,
    **readings: str,
):
    """Run the script against the readings given. Unnamed readings are a green PR on a settled
    main with no merge lock out. ``lock`` is the commit another merge's lock sits at, and
    ``between_polls`` a shell script run at each of the script's waits."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name, text in (("gh", _FAKE_GH), ("git", _FAKE_GIT), ("sleep", _FAKE_SLEEP)):
        tool = bin_dir / name
        tool.write_text(text)
        tool.chmod(0o755)
    log = tmp_path / "gh.log"
    log.unlink(missing_ok=True)  # each run's calls are read alone
    runs = tmp_path / "main_runs.txt"
    runs.write_text("\n".join(main_runs or (f"{TIP}\tcompleted\tsuccess",)) + "\n")
    (tmp_path / "tip").write_text(TIP + "\n")
    if lock is not None:
        (tmp_path / "lock").write_text(lock)
    if between_polls is not None:
        (tmp_path / "between_polls.sh").write_text(between_polls)
        readings["FAKE_BETWEEN_POLLS"] = str(tmp_path / "between_polls.sh")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "FAKE_LOG": str(log),
        "FAKE_MAIN_RUNS": str(runs),
        "FAKE_MAIN_COUNT": str(tmp_path / "main_count"),
        "FAKE_TIP_FILE": str(tmp_path / "tip"),
        "FAKE_LOCK": str(tmp_path / "lock"),
        "FAKE_PR": f"OPEN\tfalse\t{HEAD}",
        "FAKE_HEAD_RUN": "completed\tsuccess",
        "FAKE_CHECKS": "0\t",
        "FAKE_AFTER": "MERGED\tdeadbeef",
        "SAFE_MERGE_POLL_SECONDS": "0",
        **readings,
    }
    result = subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, check=False
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return result, calls


def test_a_green_pr_on_a_settled_main_is_merged_at_the_head_given(tmp_path):
    result, calls = _run(tmp_path, "3249", HEAD)

    assert result.returncode == 0, result.stderr
    assert [c for c in calls if c.startswith("pr merge")] == [MERGE]
    assert "merged PR #3249 as deadbeef" in result.stdout


@pytest.mark.parametrize(
    ("readings", "main_runs", "reason"),
    [
        ({"FAKE_PR": f"MERGED\tfalse\t{HEAD}"}, None, "PR #3249 is MERGED"),
        ({"FAKE_PR": f"OPEN\ttrue\t{HEAD}"}, None, "PR #3249 is a draft"),
        ({"FAKE_PR": f"OPEN\tfalse\t{OLDER}"}, None, "it moved after you read it"),
        # 2026-11-04: a queued run has no check rows, so "no failed check" proves nothing.
        ({"FAKE_HEAD_RUN": "queued\t"}, None, "the head's CI run is 'queued'"),
        ({"FAKE_HEAD_RUN": "none\t"}, None, "the head's CI run is 'none'"),
        ({"FAKE_HEAD_RUN": "completed\tfailure"}, None, "the head's CI run concluded 'failure'"),
        ({"FAKE_CHECKS": "0\tintegration, dependency audit"}, None, "failed checks: integration"),
        ({"FAKE_CHECKS": "2\t"}, None, "2 check(s) still running"),
        # 2026-10-24: main's newest run is the previous merge's; the tip's hasn't started.
        ({}, (f"{OLDER}\tcompleted\tsuccess",), "the tip's run hasn't started"),
        # 2026-10-23: main's run on its tip is still going, and a merge would cancel it.
        ({}, (f"{TIP}\tin_progress\t",), "a merge now would cancel it"),
        ({}, (f"{TIP}\tcompleted\tfailure",), "Fix main first"),
    ],
)
def test_a_merge_that_isnt_safe_is_refused_and_never_asked_for(
    tmp_path, readings, main_runs, reason
):
    result, calls = _run(tmp_path, "3249", HEAD, main_runs=main_runs, **readings)

    assert result.returncode == 1
    assert reason in result.stderr
    assert not [c for c in calls if c.startswith("pr merge")]


def test_the_fix_for_a_red_main_merges_over_that_red_and_says_so(tmp_path):
    result, calls = _run(
        tmp_path, "3249", HEAD, "--fixes-red-main", main_runs=(f"{TIP}\tcompleted\tfailure",)
    )

    assert result.returncode == 0, result.stderr
    assert MERGE in calls
    assert "given as its fix" in result.stderr


def test_the_fix_for_a_red_main_still_waits_for_mains_run_to_end(tmp_path):
    """The flag forgives a failure. It doesn't license cancelling a run in progress."""
    result, calls = _run(
        tmp_path, "3249", HEAD, "--fixes-red-main", main_runs=(f"{TIP}\tin_progress\t",)
    )

    assert result.returncode == 1
    assert "a merge now would cancel it" in result.stderr
    assert MERGE not in calls


def test_wait_reads_main_again_until_its_run_ends_then_merges(tmp_path):
    result, calls = _run(
        tmp_path,
        "3249",
        HEAD,
        "--wait",
        main_runs=(
            f"{OLDER}\tcompleted\tsuccess",
            f"{TIP}\tin_progress\t",
            f"{TIP}\tcompleted\tsuccess",
        ),
    )

    assert result.returncode == 0, result.stderr
    # Three readings until main's run ends, and one more under the lock before the merge.
    assert len([c for c in calls if c.startswith("run list --branch main")]) == 4
    assert calls.count(MERGE) == 1


def test_wait_doesnt_wait_on_a_failure(tmp_path):
    result, calls = _run(tmp_path, "3249", HEAD, "--wait", FAKE_HEAD_RUN="completed\tfailure")

    assert result.returncode == 1
    assert len([c for c in calls if "--commit" in c]) == 1
    assert MERGE not in calls


def test_wait_gives_up_at_its_deadline_with_the_reason(tmp_path):
    result, calls = _run(
        tmp_path,
        "3249",
        HEAD,
        "--wait",
        main_runs=(f"{TIP}\tin_progress\t",),
        SAFE_MERGE_WAIT_SECONDS="0",
    )

    assert result.returncode == 1
    assert "a merge now would cancel it" in result.stderr
    assert MERGE not in calls


def test_a_dry_run_runs_every_check_and_asks_for_no_merge(tmp_path):
    result, calls = _run(tmp_path, "3249", HEAD, "--dry-run")

    assert result.returncode == 0
    assert f"gh {MERGE}" in result.stdout
    assert MERGE not in calls
    assert any(c.startswith("run list --branch main") for c in calls)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("3249", HEAD[:8]), "full 40-character sha"),
        (("3249", HEAD.upper()), "full 40-character sha"),
        (("#3249", HEAD), "the PR number is digits"),
        (("3249", HEAD, "--force"), "unknown option '--force'"),
        (("3249", HEAD, "extra"), "too many arguments"),
    ],
)
def test_a_malformed_call_is_a_usage_error_before_anything_is_read(tmp_path, args, message):
    result, calls = _run(tmp_path, *args)

    assert result.returncode == 2
    assert message in result.stderr
    assert calls == []


def test_a_merge_whose_local_branch_gh_couldnt_delete_still_counts(tmp_path):
    """gh exits non-zero when another worktree holds the branch. The PR's state is the fact."""
    result, calls = _run(tmp_path, "3249", HEAD, FAKE_MERGE_RC="1", FAKE_AFTER="MERGED\tdeadbeef")

    assert result.returncode == 0, result.stderr
    assert "merged PR #3249 as deadbeef" in result.stdout


def test_a_merge_github_refuses_is_reported_as_refused(tmp_path):
    result, calls = _run(tmp_path, "3249", HEAD, FAKE_MERGE_RC="1", FAKE_AFTER="OPEN\t")

    assert result.returncode == 1
    assert "refused by GitHub: PR #3249 is OPEN" in result.stderr


# ------------------------------------------------------------------ the merge lock


def test_the_merge_is_made_holding_the_lock_and_the_lock_is_given_back(tmp_path):
    result, calls = _run(tmp_path, "3249", HEAD)

    taken = next(i for i, c in enumerate(calls) if c.startswith("api -X POST"))
    merged = calls.index(MERGE)
    given_back = next(i for i, c in enumerate(calls) if c.startswith("api -X DELETE"))
    assert result.returncode == 0, result.stderr
    assert calls[taken].endswith(f"ref=refs/heads/safe-merge-lock -f sha={TIP}")
    # Main is read again between taking the lock and merging.
    assert any(c.startswith("run list --branch main") for c in calls[taken:merged])
    assert taken < merged < given_back
    assert not (tmp_path / "lock").exists()


@pytest.mark.parametrize("args", [(), ("--wait",)], ids=["once", "at-its-deadline"])
def test_a_lock_at_mains_tip_is_another_merge_and_is_never_cleared_by_a_waiter(tmp_path, args):
    """A waiter can't tell a lock left by a killed process from a merge in flight. Bug caught:
    it clears the lock, and merges into the other lane's merge."""
    result, calls = _run(tmp_path, "3249", HEAD, *args, lock=TIP, SAFE_MERGE_WAIT_SECONDS="0")

    assert result.returncode == 1
    assert f"another merge holds the lock: the branch safe-merge-lock is at main's tip, {TIP}" in (
        result.stderr
    )
    assert "--clear-lock" in result.stderr
    assert MERGE not in calls
    assert (tmp_path / "lock").read_text() == TIP


def test_a_second_waiter_released_by_the_same_run_waits_for_the_run_the_first_merge_starts(
    tmp_path,
):
    """2026-11-26. Two waiters see main settled on the same reading. The first holds the lock and
    merges, which moves main's tip and starts a run on it. Bug caught: the second merges on its
    own reading from a moment before, and cancels that run."""
    newer = "d" * 40
    world = tmp_path
    first_merges = f"""
if [ -e "{world}/lock" ]; then
  rm "{world}/lock"
  echo {newer} > "{world}/tip"
  printf '%s\\n' "{newer}\tin_progress\t" "{newer}\tcompleted\tsuccess" > "{world}/main_runs.txt"
  echo 0 > "{world}/main_count"
fi
"""
    result, calls = _run(tmp_path, "3249", HEAD, "--wait", lock=TIP, between_polls=first_merges)

    main_reads = [i for i, c in enumerate(calls) if c.startswith("run list --branch main")]
    assert result.returncode == 0, result.stderr
    assert calls.count(MERGE) == 1
    # One reading on the old tip (refused the lock), one of the new run in progress, one of it
    # completed, and one under the lock. The merge follows them all.
    assert len(main_reads) == 4
    assert calls.index(MERGE) > main_reads[-1]
    assert (tmp_path / "tip").read_text().strip() == newer


def test_a_lock_main_has_moved_past_is_cleared_and_the_merge_goes_on(tmp_path):
    """Its holder merged and was stopped before it gave the lock back. Bug caught: every later
    merge waiting out its deadline on a lock nobody holds."""
    result, calls = _run(tmp_path, "3249", HEAD, "--wait", lock=OLDER)

    assert result.returncode == 0, result.stderr
    assert f"clearing a merge lock left at {OLDER}" in result.stderr
    assert calls.count(MERGE) == 1
    assert not (tmp_path / "lock").exists()


def test_main_moving_between_the_check_and_the_lock_gives_the_lock_back_and_merges_nothing(
    tmp_path,
):
    """The reading under the lock is the one that counts. Bug caught: a merge on the first
    reading, or a refusal that keeps the lock and blocks every merge after it."""
    result, calls = _run(
        tmp_path,
        "3249",
        HEAD,
        main_runs=(f"{TIP}\tcompleted\tsuccess", f"{TIP}\tin_progress\t"),
    )

    assert result.returncode == 1
    assert "a merge now would cancel it" in result.stderr
    assert MERGE not in calls
    assert not (tmp_path / "lock").exists()


def test_a_dry_run_takes_no_lock(tmp_path):
    result, calls = _run(tmp_path, "3249", HEAD, "--dry-run", lock=TIP)

    assert result.returncode == 0
    assert not [c for c in calls if c.startswith("api ")]
    assert (tmp_path / "lock").read_text() == TIP


def test_clear_lock_deletes_the_lock_and_does_nothing_else(tmp_path):
    cleared, calls = _run(tmp_path, "--clear-lock", lock=TIP)
    none_left, _ = _run(tmp_path, "--clear-lock")
    misused, misused_calls = _run(tmp_path, "--clear-lock", "3249", lock=TIP)

    assert (cleared.returncode, cleared.stdout.strip()) == (
        0,
        f"safe_merge: cleared the merge lock left at {TIP}",
    )
    assert not [c for c in calls if not c.startswith("api ")]
    assert (none_left.returncode, none_left.stdout.strip()) == (
        0,
        "safe_merge: there is no merge lock to clear",
    )
    assert (misused.returncode, misused_calls) == (2, [])
    assert "--clear-lock is given alone" in misused.stderr
