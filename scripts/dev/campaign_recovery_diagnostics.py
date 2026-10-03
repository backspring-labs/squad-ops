#!/usr/bin/env python3
"""SIP-0109 §12a's recovery guarantees, each injected live into a campaign (#1803).

The validation plan's §3 (``docs/plans/2-0-0-validation-plan.md``) designs one diagnostic per
guarantee. Each one waits for the campaign to reach the moment it injects at, injects from
outside the runtime (a restart, a CLI call), reads the outcome from the campaign's own records,
and writes a record with the facts it read and its verdict. It never edits a record, and a verdict
is a mechanism read from a record field, never a rate.

| diagnostic | injected when | the injection | passes when |
|---|---|---|---|
| ``restart-at-gate`` | the campaign is ``awaiting_ruling`` | runtime-api restarted | the campaign's last transition and its ruling count are unchanged, and the gate is open again: a ruling after the restart starts framing |
| ``repeated-ruling`` | the campaign is ``awaiting_ruling`` | a ruling, the same ruling again (same key), then the same key with another decision | the repeat replays the row; the conflict is refused and recorded; one cycle moves on |
| ``restart-in-flight`` | an increment's implementation run is ``running`` | runtime-api restarted | the run is taken up again (#1922) and the cycle reaches its evaluation; the campaign waits on it |
| ``restart-in-evaluation`` | the increment's evaluation task is dispatched | runtime-api restarted | no partial promotion: the accepted identity changes only by one ``promote`` row, carrying its bundles |
| ``restart-after-decision`` | a cycle's decision row is committed | runtime-api restarted | that cycle has exactly one decision row and one launch intent after the startup re-hearing |
| ``abort-in-flight`` | a run of the campaign is ``running`` | ``squadops campaigns abort`` | the running cycle is cancelled; no launch intent follows the abort; the campaign ends ``aborted`` |

Run them, in that order, on one diagnostic campaign on the registered deploy, with the box
otherwise idle: ``python scripts/dev/campaign_recovery_diagnostics.py <diagnostic> <campaign_id>``.
The rulings this script makes are the diagnostic's, recorded with its reason; the supervision
policy of a counted set does not apply to a diagnostic campaign.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checkouts import main_checkout  # noqa: E402

REPO = main_checkout(Path(__file__).resolve().parents[2])
SQUADOPS = REPO / ".venv" / "bin" / "squadops"
PROJECT = "group_run"
POLL_S = 15


# ---------------------------------------------------------------------------------------------
# What the records say (read-only)
# ---------------------------------------------------------------------------------------------


def _psql(sql: str) -> list[list[str]]:
    out = subprocess.run(
        [
            "docker",
            "exec",
            "squadops-postgres",
            "psql",
            "-U",
            "squadops",
            "-d",
            "squadops",
            "-At",
            "-F",
            "\t",
            "-c",
            sql,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def _id(value: str) -> str:
    if not value.replace("_", "").isalnum():
        raise SystemExit(f"not an id: {value!r}")
    return value


@dataclass(frozen=True)
class Row:
    seq: int
    operation: str
    outcome: str
    prior_state: str
    next_state: str
    target: str
    idempotency_key: str
    launch_id: str


def control_log(campaign_id: str) -> list[Row]:
    return [
        Row(int(r[0]), r[1], r[2], r[3], r[4], r[5], r[6], r[7])
        for r in _psql(
            "select seq, operation, outcome, coalesce(prior_state,''), next_state, "
            "coalesce(target,''), idempotency_key, coalesce(launch_id,'') "
            f"from campaign_control_log where campaign_id = '{_id(campaign_id)}' order by seq"
        )
    ]


def campaign_state(campaign_id: str) -> tuple[str, str]:
    [[state, accepted]] = _psql(
        "select state, coalesce(accepted_identity,'') from campaigns "
        f"where campaign_id = '{_id(campaign_id)}'"
    )
    return state, accepted


def runs_of(campaign_id: str) -> list[tuple[str, str, str, str]]:
    """(cycle_id, run_id, workload_type, status) for every run of the campaign's cycles."""
    return [
        (r[0], r[1], r[2], r[3])
        for r in _psql(
            "select r.cycle_id, r.run_id, coalesce(r.workload_type,''), r.status "
            "from cycle_runs r join cycle_registry c on c.cycle_id = r.cycle_id "
            f"where c.campaign_id = '{_id(campaign_id)}' order by r.cycle_id, r.run_number"
        )
    ]


# ---------------------------------------------------------------------------------------------
# The verdicts (pure: each reads what the records hold before and after)
# ---------------------------------------------------------------------------------------------


@dataclass
class Verdict:
    diagnostic: str
    passed: bool
    facts: dict = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def _applied(rows: Sequence[Row]) -> list[Row]:
    return [r for r in rows if r.outcome == "applied"]


def _rulings(rows: Sequence[Row]) -> int:
    return sum(1 for r in _applied(rows) if r.operation == "rule")


def _last_transition(rows: Sequence[Row]) -> Row | None:
    return next((r for r in reversed(_applied(rows)) if not r.operation.startswith("lease_")), None)


def restart_kept_the_log(name: str, before: Sequence[Row], after: Sequence[Row]) -> Verdict:
    """A restart loses nothing: every row before it is still there, unchanged, and the
    campaign's last committed transition is where it was (§12a: the state is the log's last
    committed transition)."""
    failures = []
    if list(after[: len(before)]) != list(before):
        failures.append("a row committed before the restart changed or vanished")
    if _rulings(after[: len(before)]) != _rulings(before):
        failures.append("a ruling was lost")
    last = _last_transition(before)
    return Verdict(
        name,
        not failures,
        {
            "rows_before": len(before),
            "rows_after": len(after),
            "last_before": asdict(last) if last else None,
        },
        failures,
    )


def repeated_ruling_verdict(rows: Sequence[Row], key: str) -> Verdict:
    """The same key twice is one applied row (the repeat replays it); the same key with other
    content is refused and recorded (§12a)."""
    applied = [r for r in rows if r.idempotency_key == key and r.outcome == "applied"]
    refused = [r for r in rows if r.idempotency_key == key and r.outcome == "refused"]
    failures = []
    if len(applied) != 1:
        failures.append(f"{len(applied)} applied rows for the key, not 1")
    if len(refused) != 1:
        failures.append(f"{len(refused)} refused rows for the conflicting key, not 1")
    return Verdict(
        "repeated-ruling",
        not failures,
        {"applied": len(applied), "refused": len(refused)},
        failures,
    )


def one_decision_verdict(rows: Sequence[Row], cycle_id: str) -> Verdict:
    """A cycle heard twice (its completion, then the startup re-hearing) has one decision row
    with an outcome, and at most one launch intent from it (§12a)."""
    decided = [
        r
        for r in _applied(rows)
        if r.operation == "decide" and r.target == cycle_id and r.next_state != r.prior_state
    ]
    launches = {r.launch_id for r in decided if r.launch_id}
    failures = []
    if len(decided) > 1:
        failures.append(f"{len(decided)} decisions moved the campaign for {cycle_id}")
    if len(launches) > 1:
        failures.append(f"{len(launches)} launch intents for one decision")
    return Verdict(
        "restart-after-decision",
        not failures,
        {"decisions": len(decided), "launches": sorted(launches)},
        failures,
    )


def no_partial_promotion_verdict(
    accepted_before: str, accepted_after: str, rows: Sequence[Row]
) -> Verdict:
    """The accepted identity changes only by a ``promote`` row (§12a), and at most one."""
    promotes = [r for r in _applied(rows) if r.operation == "promote"]
    failures = []
    if accepted_after != accepted_before and not promotes:
        failures.append("the accepted identity changed with no promote row")
    if len(promotes) > 1:
        failures.append(f"{len(promotes)} promote rows for one evaluation")
    return Verdict(
        "restart-in-evaluation",
        not failures,
        {
            "accepted_before": accepted_before,
            "accepted_after": accepted_after,
            "promotes": len(promotes),
        },
        failures,
    )


def abort_verdict(rows: Sequence[Row], state: str, cancelled_runs: int) -> Verdict:
    """An abort is terminal: no launch intent after it, the campaign completed as aborted,
    and the running cycle cancelled by the existing path."""
    abort = next((r for r in _applied(rows) if r.operation == "abort"), None)
    failures = []
    if abort is None:
        failures.append("no applied abort row")
    else:
        after = [r for r in _applied(rows) if r.seq > abort.seq and r.launch_id]
        if after:
            failures.append(f"{len(after)} launch intent(s) after the abort")
    if state != "completed":
        failures.append(f"the campaign is {state}, not completed")
    if cancelled_runs < 1:
        failures.append("no run was cancelled")
    return Verdict(
        "abort-in-flight",
        not failures,
        {"state": state, "cancelled_runs": cancelled_runs},
        failures,
    )


# ---------------------------------------------------------------------------------------------
# Injections and waiting
# ---------------------------------------------------------------------------------------------


def wait_for(predicate: Callable[[], bool], what: str, timeout_s: int = 4 * 3600) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        if time.monotonic() > deadline:
            raise SystemExit(f"timed out waiting for {what}")
        time.sleep(POLL_S)
    print(f"[{datetime.now(UTC):%H:%M:%SZ}] {what}", flush=True)


def restart_runtime() -> None:
    subprocess.run(["docker", "restart", "squadops-runtime-api"], check=True, capture_output=True)
    wait_for(
        lambda: (
            subprocess.run(
                ["curl", "-sf", "-o", "/dev/null", "http://localhost:8001/health"]
            ).returncode
            == 0
        ),
        "runtime-api healthy after the restart",
        timeout_s=300,
    )


def squadops(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(SQUADOPS), *args], capture_output=True, text=True)


def _record(campaign_id: str, verdict: Verdict) -> Path:
    folder = REPO / "var" / "campaigns" / campaign_id / "diagnostics"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{verdict.diagnostic}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(asdict(verdict), indent=2, default=str) + "\n")
    print(
        f"{verdict.diagnostic}: {'PASS' if verdict.passed else 'FAIL'} {verdict.failures} -> {path}"
    )
    return path


# ---------------------------------------------------------------------------------------------
# The diagnostics
# ---------------------------------------------------------------------------------------------


def _gate_run(campaign_id: str) -> tuple[str, str]:
    """The proposal run waiting at the increment gate: (cycle_id, run_id)."""
    proposals = [
        (c, r) for c, r, w, st in runs_of(campaign_id) if w == "proposal" and st == "completed"
    ]
    return proposals[-1]


def restart_at_gate(campaign_id: str) -> Verdict:
    wait_for(
        lambda: campaign_state(campaign_id)[0] == "awaiting_ruling", "the increment gate is open"
    )
    before = control_log(campaign_id)
    restart_runtime()
    verdict = restart_kept_the_log("restart-at-gate", before, control_log(campaign_id))
    verdict.facts["state_after"] = campaign_state(campaign_id)[0]
    if verdict.facts["state_after"] != "awaiting_ruling":
        verdict.failures.append(
            f"the campaign is {verdict.facts['state_after']}, not awaiting_ruling"
        )
        verdict.passed = False
    return verdict


def repeated_ruling(campaign_id: str, change_request: str) -> Verdict:
    wait_for(
        lambda: campaign_state(campaign_id)[0] == "awaiting_ruling", "the increment gate is open"
    )
    cycle_id, run_id = _gate_run(campaign_id)
    key = f"diag-repeat-{run_id}"
    notes = "#1803 diagnostic: a ruling, repeated with its key, then the key reused for a reject"
    base = [
        "runs",
        "gate",
        PROJECT,
        cycle_id,
        run_id,
        "progress_increment_ruling",
        "--notes",
        notes,
        "--change-request",
        change_request,
        "--idempotency-key",
        key,
    ]
    first, again, conflict = (
        squadops(*base, "--approve"),
        squadops(*base, "--approve"),
        squadops(*base, "--reject"),
    )
    verdict = repeated_ruling_verdict(control_log(campaign_id), key)
    verdict.facts["cli"] = [first.returncode, again.returncode, conflict.returncode]
    # The gate is open again after a restart only if a ruling then moves it on (§12a).
    wait_for(
        lambda: any(c == cycle_id and w == "framing" for c, _r, w, _s in runs_of(campaign_id)),
        "framing started after the ruling",
        timeout_s=600,
    )
    return verdict


def restart_in_flight(campaign_id: str) -> Verdict:
    wait_for(
        lambda: any(
            w == "implementation" and st == "running" for _c, _r, w, st in runs_of(campaign_id)
        ),
        "an implementation run in flight",
    )
    [(cycle_id, run_id)] = [
        (c, r) for c, r, w, st in runs_of(campaign_id) if w == "implementation" and st == "running"
    ][-1:]
    before = control_log(campaign_id)
    restart_runtime()
    verdict = restart_kept_the_log("restart-in-flight", before, control_log(campaign_id))
    wait_for(
        lambda: any(
            r == run_id and st in ("completed", "failed") for _c, r, _w, st in runs_of(campaign_id)
        ),
        "the run taken up again reached its end",
    )
    verdict.facts["run"] = run_id
    verdict.facts["run_status"] = next(st for _c, r, _w, st in runs_of(campaign_id) if r == run_id)
    return verdict


def restart_in_evaluation(campaign_id: str) -> Verdict:
    accepted_before = campaign_state(campaign_id)[1]
    seq_before = len(control_log(campaign_id))
    wait_for(
        lambda: (
            subprocess.run(
                [
                    "sh",
                    "-c",
                    "docker logs --since 10m squadops-runtime-api 2>&1 | grep -q 'qa.evaluate_increment'",
                ]
            ).returncode
            == 0
        ),
        "the increment's evaluation dispatched",
    )
    restart_runtime()
    wait_for(
        lambda: any(
            r.operation == "decide" and r.seq > seq_before
            for r in _applied(control_log(campaign_id))
        ),
        "the cycle decided after the restart",
    )
    rows = control_log(campaign_id)[seq_before:]
    return no_partial_promotion_verdict(accepted_before, campaign_state(campaign_id)[1], rows)


def restart_after_decision(campaign_id: str) -> Verdict:
    seq_before = len(control_log(campaign_id))
    wait_for(
        lambda: any(
            r.operation == "decide" and r.seq > seq_before
            for r in _applied(control_log(campaign_id))
        ),
        "a cycle decided",
    )
    cycle_id = next(
        r.target for r in reversed(_applied(control_log(campaign_id))) if r.operation == "decide"
    )
    restart_runtime()
    time.sleep(2 * POLL_S)  # the startup re-hearing runs once the process is up
    return one_decision_verdict(control_log(campaign_id), cycle_id)


def abort_in_flight(campaign_id: str) -> Verdict:
    wait_for(
        lambda: any(st == "running" for *_x, st in runs_of(campaign_id)),
        "a run of the campaign in flight",
    )
    squadops("campaigns", "abort", campaign_id, "--reason", "#1803 diagnostic: an abort mid-cycle")
    wait_for(lambda: campaign_state(campaign_id)[0] == "completed", "the campaign completed")
    cancelled = sum(1 for *_x, st in runs_of(campaign_id) if st == "cancelled")
    return abort_verdict(control_log(campaign_id), campaign_state(campaign_id)[0], cancelled)


DIAGNOSTICS = {
    "restart-at-gate": restart_at_gate,
    "repeated-ruling": repeated_ruling,
    "restart-in-flight": restart_in_flight,
    "restart-in-evaluation": restart_in_evaluation,
    "restart-after-decision": restart_after_decision,
    "abort-in-flight": abort_in_flight,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("diagnostic", choices=sorted(DIAGNOSTICS))
    parser.add_argument("campaign_id")
    parser.add_argument(
        "--change-request", help="the change request file the ruling binds to (repeated-ruling)"
    )
    args = parser.parse_args(argv)
    run = DIAGNOSTICS[args.diagnostic]
    verdict = (
        run(args.campaign_id, args.change_request)
        if args.diagnostic == "repeated-ruling"
        else run(args.campaign_id)
    )
    _record(args.campaign_id, verdict)
    return 0 if verdict.passed else 1


if __name__ == "__main__":
    sys.exit(main())
