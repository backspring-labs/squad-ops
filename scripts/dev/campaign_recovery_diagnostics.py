#!/usr/bin/env python3
"""SIP-0109 §12a's recovery guarantees, each injected live into a campaign (#1803).

The validation plan's §3 (``docs/plans/2-0-0-validation-plan.md``) designs one diagnostic per
guarantee. Each one waits for the campaign to reach the moment it injects at, injects from
outside the runtime (a restart, a kill, a CLI call), reads the outcome from the campaign's own
records, and writes a record with the facts it read and its verdict. It never edits a record, and
a verdict is a mechanism read from a record field, never a rate.

| diagnostic | injected when | the injection | passes when |
|---|---|---|---|
| ``restart-at:<state>`` | the campaign is in ``<state>``, with its run in flight when the state has one | runtime-api restarted | every row before the restart is unchanged, ruling count included; the campaign resumes from its last committed transition; every run in flight is taken up again (#1922) |
| ``restart-paused`` | any state that can pause | ``campaigns pause``, a restart, then ``campaigns resume`` | as above, the campaign still ``paused`` after the restart, and the resume applies |
| ``repeated-ruling`` | ``awaiting_ruling`` | a ruling, the same ruling again (same key), then the same key with another decision | the repeat replays (one applied row); the conflict is refused and recorded; neither launches |
| ``kill-before-promotion`` | an increment's implementation run logs its completion: the evaluator's last line | runtime-api killed (SIGKILL), then started | the accepted identity is the old one or the new one, the new one only with its one ``promote`` row |
| ``duplicate-completion`` | a cycle's continuation decision is committed | runtime-api restarted: its startup re-hearing hears every launched cycle again | each decision step of each cycle is one row; the cycle has one continuation decision; each launch intent is one cycle |
| ``abort-in-flight`` | a run of the campaign is ``running`` | ``campaigns abort`` | the running cycle is cancelled; no launch intent follows the abort; the campaign ends ``aborted`` |

Every restart and kill also re-hears every cycle the campaign already decided (``rehear_ended``
hears each launched cycle of a live campaign), so each record carries the duplicate-completion
check over the whole log, not only the cycle it targets.

**The live run is two diagnostic campaigns on the registered deploy, with the box otherwise
idle.** Pass the campaign and its diagnostics in order:
``python scripts/dev/campaign_recovery_diagnostics.py <campaign_id> <diagnostic> ...``.

1. **The blocked legs.** A campaign with ``launch_blocked_attempts: 1``, started with a small foreign
   model resident (the free memory read before and after, plan §3's stated risk):
   ``restart-at:launch_blocked restart-at:escalated``. Then unload the model and resume it, and
   run ``restart-at:calibrating abort-in-flight``.
2. **The increment legs.** A campaign of one increment:
   ``restart-at:at_proposal restart-at:awaiting_ruling repeated-ruling restart-paused
   restart-at:building kill-before-promotion duplicate-completion abort-in-flight``. The first
   restart re-hears the calibration just decided; ``duplicate-completion`` targets the
   increment's decision; the abort lands on the next proposal run.

The rulings this script makes are the diagnostic's, recorded with its reason. The supervision
policy of a counted set does not apply to a diagnostic campaign.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checkouts import main_checkout  # noqa: E402
from verification_set_driver import login  # noqa: E402

from squadops.campaigns.models import CampaignState  # noqa: E402

REPO = main_checkout(Path(__file__).resolve().parents[2])
SQUADOPS = REPO / ".venv" / "bin" / "squadops"
PROJECT = "group_run"
RUNTIME = "squadops-runtime-api"
POLL_S = 15
#: The states a campaign holds while a run of it is in flight: a restart there must take it up.
_RUN_IN_FLIGHT = frozenset({"calibrating", "at_proposal", "building", "repairing", "retrying"})


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


def cycles_per_launch(campaign_id: str) -> dict[str, int]:
    """How many cycles each launch intent of the campaign created (§12b: exactly one)."""
    return {
        r[0]: int(r[1])
        for r in _psql(
            "select source_launch_id, count(*) from cycle_registry "
            f"where campaign_id = '{_id(campaign_id)}' and source_launch_id is not null "
            "group by source_launch_id"
        )
    }


def _running(campaign_id: str) -> list[str]:
    return [r for _c, r, _w, st in runs_of(campaign_id) if st == "running"]


# ---------------------------------------------------------------------------------------------
# The verdicts (pure: each reads what the records hold before and after)
# ---------------------------------------------------------------------------------------------


@dataclass
class Verdict:
    diagnostic: str
    passed: bool
    facts: dict = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def fail(self, failures: Sequence[str]) -> Verdict:
        self.failures.extend(failures)
        self.passed = self.passed and not failures
        return self


def _applied(rows: Sequence[Row]) -> list[Row]:
    return [r for r in rows if r.outcome == "applied"]


def _rulings(rows: Sequence[Row]) -> int:
    return sum(1 for r in _applied(rows) if r.operation == "rule")


def _last_transition(rows: Sequence[Row]) -> Row | None:
    return next((r for r in reversed(_applied(rows)) if not r.operation.startswith("lease_")), None)


def _continuations(rows: Sequence[Row], cycle_id: str) -> list[Row]:
    """A cycle's continuation decision: the ``decide`` row that leaves ``evaluating`` (or, for a
    calibration, the one decision it has). Hearing the cycle's end is its own ``decide`` row,
    into ``evaluating``, so a healthy increment has two decide rows and one continuation."""
    return [
        r
        for r in _applied(rows)
        if r.operation == "decide" and r.target == cycle_id and r.next_state != "evaluating"
    ]


def decided_once(rows: Sequence[Row], launched: Mapping[str, int]) -> list[str]:
    """§12a over the whole log: each decision step of each cycle (keyed by the state it left)
    is one applied row, each cycle has at most one continuation decision, and each launch
    intent created at most one cycle (§12b). A cycle heard twice breaks the first two; a second
    launch for one intent breaks the third."""
    decides = [r for r in _applied(rows) if r.operation == "decide"]
    steps = Counter((r.target, r.prior_state) for r in decides)
    continuations = Counter(r.target for r in decides if r.next_state != "evaluating")
    return [
        *(
            f"{c}: the decision from {s} taken {n} times"
            for (c, s), n in sorted(steps.items())
            if n > 1
        ),
        *(f"{c}: {n} continuation decisions" for c, n in sorted(continuations.items()) if n > 1),
        *(f"{lnc}: launched as {n} cycles" for lnc, n in sorted(launched.items()) if n > 1),
    ]


def restart_kept_the_log(
    name: str, before: Sequence[Row], after: Sequence[Row], state_after: str
) -> Verdict:
    """A restart loses nothing: every row before it is still there, unchanged, and the campaign
    resumes from its last committed transition (§12a: the state is the log's last committed
    transition) — the first row after the restart leaves that state, or, with none, the
    campaign is still in it."""
    failures = []
    if list(after[: len(before)]) != list(before):
        failures.append("a row committed before the restart changed or vanished")
    if _rulings(after[: len(before)]) != _rulings(before):
        failures.append("a ruling was lost")
    last = _last_transition(before)
    resumed = [r for r in _applied(after[len(before) :]) if not r.operation.startswith("lease_")]
    if last is not None:
        if resumed and resumed[0].prior_state != last.next_state:
            failures.append(
                f"resumed from {resumed[0].prior_state}, not the last committed {last.next_state}"
            )
        if not resumed and state_after != last.next_state:
            failures.append(
                f"the campaign is {state_after}, not the last committed {last.next_state}"
            )
    return Verdict(
        name,
        not failures,
        {
            "rows_before": len(before),
            "rows_after": len(after),
            "last_before": asdict(last) if last else None,
            "state_after": state_after,
        },
        failures,
    )


def reattach_verdict(in_flight: Sequence[str], taken_up: Sequence[str]) -> list[str]:
    """#1922: every run in flight at the restart is executed again after it."""
    return [f"{run}: not taken up after the restart" for run in in_flight if run not in taken_up]


def repeated_ruling_verdict(rows: Sequence[Row], key: str) -> Verdict:
    """The same key twice is one applied row (the repeat replays it); the same key with other
    content is refused and recorded (§12a); nothing either one writes launches."""
    applied = [r for r in rows if r.idempotency_key == key and r.outcome == "applied"]
    refused = [r for r in rows if r.idempotency_key == key and r.outcome == "refused"]
    failures = []
    if len(applied) != 1:
        failures.append(f"{len(applied)} applied rows for the key, not 1")
    if len(refused) != 1:
        failures.append(f"{len(refused)} refused rows for the conflicting key, not 1")
    if any(r.launch_id for r in [*applied, *refused]):
        failures.append("a ruling row carries a launch intent")
    return Verdict(
        "repeated-ruling",
        not failures,
        {"applied": len(applied), "refused": len(refused)},
        failures,
    )


def duplicate_completion_verdict(
    rows: Sequence[Row], cycle_id: str, launched: Mapping[str, int]
) -> Verdict:
    """The cycle a restart re-heard right after its decision is decided once: one continuation
    decision, and the intent it launched is one cycle (§12a, §12b). The whole log's check is
    ``decided_once``, which every restart runs."""
    continuations = _continuations(rows, cycle_id)
    launches = sorted({r.launch_id for r in _applied(rows) if r.target == cycle_id and r.launch_id})
    failures = []
    if len(continuations) != 1:
        failures.append(f"{len(continuations)} continuation decisions for {cycle_id}, not 1")
    failures.extend(
        f"{lnc}: launched as {launched.get(lnc, 0)} cycles, not 1"
        for lnc in launches
        if launched.get(lnc, 0) != 1
    )
    return Verdict(
        "duplicate-completion",
        not failures,
        {"cycle": cycle_id, "continuations": len(continuations), "launches": launches},
        failures,
    )


def no_partial_promotion_verdict(
    accepted_before: str, accepted_after: str, rows: Sequence[Row], exercised: bool
) -> Verdict:
    """The accepted identity changes only by a ``promote`` row (§12a), and at most one. A kill
    that landed after the promotion committed did not interrupt it: not exercised, so no
    pass."""
    promotes = [r for r in _applied(rows) if r.operation == "promote"]
    failures = []
    if not exercised:
        failures.append("the promotion committed before the kill: the window was not hit")
    if accepted_after != accepted_before and not promotes:
        failures.append("the accepted identity changed with no promote row")
    if len(promotes) > 1:
        failures.append(f"{len(promotes)} promote rows for one evaluation")
    return Verdict(
        "kill-before-promotion",
        not failures,
        {
            "accepted_before": accepted_before,
            "accepted_after": accepted_after,
            "promotes": len(promotes),
            "exercised": exercised,
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


def _now() -> str:
    return f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}"


def wait_for(predicate: Callable[[], bool], what: str, timeout_s: int = 4 * 3600) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        if time.monotonic() > deadline:
            raise SystemExit(f"timed out waiting for {what}")
        time.sleep(POLL_S)
    print(f"[{_now()}] {what}", flush=True)


def _healthy() -> None:
    wait_for(
        lambda: (
            subprocess.run(
                ["curl", "-sf", "-o", "/dev/null", "http://localhost:8001/health"]
            ).returncode
            == 0
        ),
        "runtime-api healthy",
        timeout_s=300,
    )
    time.sleep(2 * POLL_S)  # the startup drain, re-hearing and re-attach run once it is up


def restart_runtime() -> str:
    """A graceful restart (SIGTERM, then the stop timeout). Returns when it went down."""
    since = _now()
    subprocess.run(["docker", "restart", RUNTIME], check=True, capture_output=True)
    _healthy()
    return since


def kill_runtime() -> str:
    """A crash: SIGKILL, no shutdown path, then a start. Returns when it was killed."""
    since = _now()
    subprocess.run(["docker", "kill", RUNTIME], check=True, capture_output=True)
    subprocess.run(["docker", "start", RUNTIME], check=True, capture_output=True)
    _healthy()
    return since


def _taken_up(since: str, runs: Sequence[str], timeout_s: int = 300) -> list[str]:
    """The runs runtime-api executed again after ``since`` (its ``Executing run`` line)."""
    deadline = time.monotonic() + timeout_s
    while True:
        log = subprocess.run(
            ["docker", "logs", "--since", since, RUNTIME], capture_output=True, text=True
        )
        text = log.stdout + log.stderr
        taken = [r for r in runs if f"Executing run {r} " in text]
        if len(taken) == len(runs) or time.monotonic() > deadline:
            return taken
        time.sleep(POLL_S)


def squadops(*args: str) -> subprocess.CompletedProcess:
    """A CLI call, logged in first, by the driver's rule: the token lasts minutes and a
    diagnostic waits hours for its moment. On an expired session a ruling, a pause or an abort
    fails, and the next wait (the pause landing, the campaign completing) can never pass."""
    login(str(SQUADOPS))
    return subprocess.run([str(SQUADOPS), *args], capture_output=True, text=True)


def _record(campaign_id: str, verdict: Verdict) -> Path:
    verdict.facts["runtime_image"] = subprocess.run(
        ["docker", "inspect", "-f", "{{.Image}}", RUNTIME], capture_output=True, text=True
    ).stdout.strip()
    folder = REPO / "var" / "campaigns" / campaign_id / "diagnostics"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{verdict.diagnostic}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(asdict(verdict), indent=2, default=str) + "\n")
    print(
        f"{verdict.diagnostic}: {'PASS' if verdict.passed else 'FAIL'} {verdict.failures} -> {path}",
        flush=True,
    )
    return path


# ---------------------------------------------------------------------------------------------
# The diagnostics
# ---------------------------------------------------------------------------------------------


def _restarted(campaign_id: str, name: str, inject: Callable[[], str]) -> Verdict:
    """Inject, then read: the log kept, the campaign resumed, every run in flight taken up, and
    nothing decided twice by the re-hearing."""
    in_flight = _running(campaign_id)
    before = control_log(campaign_id)
    since = inject()
    verdict = restart_kept_the_log(
        name, before, control_log(campaign_id), campaign_state(campaign_id)[0]
    )
    taken = _taken_up(since, in_flight) if in_flight else []
    verdict.facts.update({"injected_at": since, "in_flight": in_flight, "taken_up": taken})
    return verdict.fail(
        [
            *reattach_verdict(in_flight, taken),
            *decided_once(control_log(campaign_id), cycles_per_launch(campaign_id)),
        ]
    )


def restart_at(campaign_id: str, state: str) -> Verdict:
    def there() -> bool:
        return campaign_state(campaign_id)[0] == state and (
            state not in _RUN_IN_FLIGHT or bool(_running(campaign_id))
        )

    wait_for(
        there,
        f"the campaign is {state}" + (" with a run in flight" if state in _RUN_IN_FLIGHT else ""),
    )
    return _restarted(campaign_id, f"restart-at-{state}", restart_runtime)


def restart_paused(campaign_id: str) -> Verdict:
    reason = "#1803 diagnostic: a restart while paused"
    squadops("campaigns", "pause", campaign_id, "--reason", reason)
    wait_for(lambda: campaign_state(campaign_id)[0] == "paused", "the campaign paused", 300)
    verdict = _restarted(campaign_id, "restart-paused", restart_runtime)
    resumed = squadops("campaigns", "resume", campaign_id, "--reason", reason)
    verdict.facts["state_after_resume"] = campaign_state(campaign_id)[0]
    return verdict.fail(
        [f"the resume did not apply: {resumed.stderr.strip()[-200:]}"]
        if resumed.returncode or verdict.facts["state_after_resume"] == "paused"
        else []
    )


def _change_request(cycle_id: str, run_id: str, folder: Path) -> Path:
    listed = squadops(
        "--json", "artifacts", "list", "--project", PROJECT, "--cycle", cycle_id, "--run", run_id
    )
    [art] = [
        a["artifact_id"]
        for a in json.loads(listed.stdout)
        if a["filename"] == "change_request.yaml"
    ]
    path = folder / "change_request.yaml"
    squadops("artifacts", "download", art, "--out", str(path))
    return path


def repeated_ruling(campaign_id: str) -> Verdict:
    wait_for(
        lambda: campaign_state(campaign_id)[0] == "awaiting_ruling", "the increment gate is open"
    )
    cycle_id, run_id = [
        (c, r) for c, r, w, st in runs_of(campaign_id) if w == "proposal" and st == "completed"
    ][-1]
    key = f"diag-repeat-{run_id}"
    notes = "#1803 diagnostic: a ruling, repeated with its key, then the key reused for a reject"
    with tempfile.TemporaryDirectory() as tmp:
        change_request = _change_request(cycle_id, run_id, Path(tmp))
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
            str(change_request),
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
    wait_for(
        lambda: any(c == cycle_id and w == "framing" for c, _r, w, _s in runs_of(campaign_id)),
        "framing started after the ruling",
        timeout_s=600,
    )
    return verdict


def kill_before_promotion(campaign_id: str) -> Verdict:
    wait_for(
        lambda: any(
            w == "implementation" and st == "running" for _c, _r, w, st in runs_of(campaign_id)
        ),
        "an increment's implementation run in flight",
    )
    [(cycle_id, run_id)] = [
        (c, r) for c, r, w, st in runs_of(campaign_id) if w == "implementation" and st == "running"
    ][-1:]
    accepted_before = campaign_state(campaign_id)[1]
    seq_before = len(control_log(campaign_id))
    # The window is the completion hook's: the run's last line, then the promotion. A poll misses
    # it, so the log is followed and the kill sent on the line.
    follow = subprocess.Popen(
        ["docker", "logs", "-f", "--since", _now(), RUNTIME],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    completed, checked = False, time.monotonic()
    for line in follow.stdout:
        if f"Run {run_id} completed successfully" in line:
            completed = True
            break
        if time.monotonic() - checked > POLL_S:  # a run that ends otherwise never logs the line
            checked = time.monotonic()
            if run_id not in _running(campaign_id):
                break
    killed_at = kill_runtime() if completed else _now()
    follow.kill()
    at_kill = control_log(campaign_id)[seq_before:]
    exercised = completed and not any(
        r.target == cycle_id and r.operation in ("promote", "decide") for r in _applied(at_kill)
    )
    wait_for(
        lambda: bool(_continuations(control_log(campaign_id), cycle_id)),
        "the cycle decided after the kill",
        timeout_s=1800,
    )
    rows = control_log(campaign_id)
    verdict = no_partial_promotion_verdict(
        accepted_before, campaign_state(campaign_id)[1], rows[seq_before:], exercised
    )
    verdict.facts.update({"run": run_id, "killed_at": killed_at, "completed": completed})
    return verdict.fail(decided_once(rows, cycles_per_launch(campaign_id)))


def duplicate_completion(campaign_id: str) -> Verdict:
    latest: list[Row] = []

    def decided() -> bool:
        decides = [r for r in _applied(control_log(campaign_id)) if r.operation == "decide"]
        latest[:] = decides[-1:] if decides and decides[-1].next_state != "evaluating" else []
        return bool(latest)

    wait_for(decided, "a cycle's continuation decision committed")
    cycle_id = latest[0].target
    verdict = _restarted(campaign_id, "duplicate-completion", restart_runtime)
    # The startup drain launches what the decision intended; give it its window.
    launches = {
        r.launch_id
        for r in _applied(control_log(campaign_id))
        if r.target == cycle_id and r.launch_id
    }
    deadline = time.monotonic() + 120
    while not launches <= set(cycles_per_launch(campaign_id)) and time.monotonic() < deadline:
        time.sleep(POLL_S)
    targeted = duplicate_completion_verdict(
        control_log(campaign_id), cycle_id, cycles_per_launch(campaign_id)
    )
    verdict.facts.update(targeted.facts)
    return verdict.fail(targeted.failures)


def abort_in_flight(campaign_id: str) -> Verdict:
    wait_for(lambda: bool(_running(campaign_id)), "a run of the campaign in flight")
    squadops("campaigns", "abort", campaign_id, "--reason", "#1803 diagnostic: an abort mid-cycle")
    wait_for(lambda: campaign_state(campaign_id)[0] == "completed", "the campaign completed", 600)
    cancelled = sum(1 for *_x, st in runs_of(campaign_id) if st == "cancelled")
    return abort_verdict(control_log(campaign_id), campaign_state(campaign_id)[0], cancelled)


DIAGNOSTICS: dict[str, Callable[[str], Verdict]] = {
    "restart-paused": restart_paused,
    "repeated-ruling": repeated_ruling,
    "kill-before-promotion": kill_before_promotion,
    "duplicate-completion": duplicate_completion,
    "abort-in-flight": abort_in_flight,
}


def _diagnostic(spec: str) -> Callable[[str], Verdict]:
    if spec.startswith("restart-at:"):
        state = spec.removeprefix("restart-at:")
        if state not in {s.value for s in CampaignState} - {"draft", "completed"}:
            raise argparse.ArgumentTypeError(f"not a state a campaign restarts in: {state}")
        return lambda campaign_id: restart_at(campaign_id, state)
    if spec not in DIAGNOSTICS:
        raise argparse.ArgumentTypeError(f"not a diagnostic: {spec}")
    return DIAGNOSTICS[spec]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("campaign_id", type=_id)
    parser.add_argument(
        "diagnostics",
        nargs="+",
        help=f"in order: restart-at:<state>, {', '.join(DIAGNOSTICS)}",
    )
    args = parser.parse_args(argv)
    try:  # every spec is read before the first injection: a typo never strands a campaign
        runs = [_diagnostic(spec) for spec in args.diagnostics]
    except argparse.ArgumentTypeError as e:
        parser.error(str(e))
    failed = 0
    for run in runs:
        verdict = run(args.campaign_id)
        _record(args.campaign_id, verdict)
        failed += not verdict.passed
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
