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
| ``restart-queued-successor`` | the increment gate is open | a foreign model loaded, the ruling, a restart while the successor waits queued for the box, then the model unloaded | the successor is started once after the restart and the cycle goes on by its own rules (#2042) |

``restart-at:at_proposal`` also waits for the proposal task's dispatch before it restarts, and passes
only when the re-attach asks for it under the same id and the proposer answers that copy from its
stored reply, rather than running it again (#1934, SIP-0109 §24ao).

**Every record also reads #2007:** no flow run of an ended run is still open in Prefect, and a run
in flight holds at most one. The tracker's own query reads it, and a Prefect that cannot be read fails
the record rather than reading as none open.

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

3. **2.1 rebuild 1** (2.1.0 plan §4 step 3): a campaign of one increment,
   ``restart-at:at_proposal restart-queued-successor duplicate-completion``
   (``examples/03_group_run/campaigns/2-1-0-rebuild1-diag.yaml``). The increment's cycle ends by
   its own rules, and the last record reads #2007 over every run the restarts touched.

The rulings this script makes are the diagnostic's, recorded with its reason. The supervision
policy of a counted set does not apply to a diagnostic campaign.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checkouts import main_checkout  # noqa: E402
from verification_set_driver import login  # noqa: E402

from squadops.campaigns.models import CampaignState  # noqa: E402
from squadops.cycles.naming import flow_run_name  # noqa: E402

REPO = main_checkout(Path(__file__).resolve().parents[2])
SQUADOPS = REPO / ".venv" / "bin" / "squadops"
PROJECT = "group_run"
RUNTIME = "squadops-runtime-api"
PROPOSER = "squadops-nat"
PROPOSAL_TASK = "strategy.propose_increment"
PREFECT_API = "http://localhost:4200/api"
OLLAMA = "http://localhost:11434"
#: A model no deploy record declares: while it is resident the box is not quiet, so a run start
#: waits, still queued (``RunAdmission.await_box``). The 2.0 blocked legs used it (operator notes,
#: ``cmp_678167dcd86a``).
FOREIGN_MODEL = "llama3.1:8b"
_TERMINAL = frozenset({"completed", "failed", "cancelled"})
_DISPATCHED = re.compile(r"Dispatched task (\S+) \((\S+)\) to ")
_REPLAYED = re.compile(r"task_reply_replayed: task=(\S+)")
POLL_S = 15
T = TypeVar("T")
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


def _started_at(run_id: str) -> str:
    [[at]] = _psql(
        "select to_char(started_at at time zone 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') "
        f"from cycle_runs where run_id = '{_id(run_id)}'"
    )
    return at


def _logs(container: str, since: str) -> str:
    out = subprocess.run(
        ["docker", "logs", "--since", since, container], capture_output=True, text=True
    )
    return out.stdout + out.stderr


def dispatched(log: str, task_type: str) -> list[str]:
    """The ids the runtime dispatched ``task_type`` under, in order (its ``Dispatched task`` line)."""
    return [m[1] for m in _DISPATCHED.finditer(log) if m[2] == task_type]


def replayed(log: str) -> list[str]:
    """The task ids an agent answered from its stored reply (``task_reply_replayed``, #1929)."""
    return [m[1] for m in _REPLAYED.finditer(log)]


def open_flow_runs(runs: Sequence[tuple[str, str, str, str]]) -> dict[str, list[str]] | None:
    """Each run's flow runs Prefect still holds open, by the run's flow-run name: the tracker's
    own query, so this reads what the executor's cleanup reads (#2007). ``None`` when Prefect
    cannot be read: the tracker answers ``[]`` on a transport failure, which would read as none."""
    from adapters.cycles.prefect_workflow_tracker import PrefectWorkflowTracker

    up = subprocess.run(["curl", "-sf", "-o", "/dev/null", f"{PREFECT_API}/health"])
    if up.returncode != 0:
        return None

    async def read() -> dict[str, list[str]]:
        tracker = PrefectWorkflowTracker(PREFECT_API)
        return {
            r: await tracker.find_active_flow_run_ids([flow_run_name(PROJECT, c, r)])
            for c, r, _w, _s in runs
        }

    return asyncio.run(read())


def _queued_successor(campaign_id: str, cycle_id: str) -> str | None:
    """The run #2042's window holds: the cycle's latest run queued, after only completed runs."""
    runs = [(r, st) for c, r, _w, st in runs_of(campaign_id) if c == cycle_id and st != "cancelled"]
    if len(runs) > 1 and runs[-1][1] == "queued" and all(st == "completed" for _r, st in runs[:-1]):
        return runs[-1][0]
    return None


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


def flow_runs_left_open(
    runs: Sequence[tuple[str, str, str, str]], open_by_run: Mapping[str, Sequence[str]] | None
) -> list[str]:
    """#2007: no flow run of an ended run stays open, and a run in flight holds at most one (the
    restart's re-attach opens its own, and ends the dead process's)."""
    if open_by_run is None:
        return ["Prefect could not be read, so the open flow runs are unread"]
    out = []
    for _c, run_id, _w, status in runs:
        held = list(open_by_run.get(run_id, ()))
        if status in _TERMINAL and held:
            out.append(f"{run_id} is {status} and {len(held)} flow run(s) of it are open: {held}")
        elif len(held) > 1:
            out.append(f"{run_id} is {status} and {len(held)} flow runs of it are open: {held}")
    return out


def proposal_answered_once(
    before: Sequence[str], after: Sequence[str], answered_from_store: Sequence[str]
) -> list[str]:
    """#1934: the re-attach asks for the in-flight proposal task under the id it was dispatched
    with, and the proposer answers that copy from its stored reply instead of running it again.
    Rebuild 18's shape was a second id (``68de55e6f36b`` then ``532815c18eb5``), run in full."""
    if not before:
        return ["no proposal task was dispatched before the restart, so the window was missed"]
    if not after:
        return ["the re-attach dispatched no proposal task"]
    out = [
        f"re-dispatched as {t}, an id the proposer was never sent" for t in after if t not in before
    ]
    out += [
        f"{t}: the proposer did not answer the copy from its stored reply"
        for t in after
        if t in before and t not in answered_from_store
    ]
    return out


def queued_successor_verdict(
    successor: str | None, queued_after_restart: bool, starts: int, live_runs_at_position: int
) -> list[str]:
    """#2042: a successor left queued by a restart is started once, by the startup re-attach."""
    if successor is None:
        return ["no successor was queued when the runtime went down, so the window was missed"]
    out = []
    if not queued_after_restart:
        out.append(
            f"{successor} was not still queued after the restart, so the restart did not hold it"
        )
    if starts == 0:
        out.append(f"{successor} was never started after the restart: the cycle is stranded")
    elif starts > 1:
        out.append(f"{successor} was started {starts} times after the restart")
    if live_runs_at_position != 1:
        out.append(f"{live_runs_at_position} runs hold the successor's position")
    return out


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


def kill_runtime(read_at_kill: Callable[[], T]) -> tuple[str, T]:
    """A crash: SIGKILL, no shutdown path, then a start. ``read_at_kill`` reads the records
    while the process is down, before the start: what the dead process committed, and nothing
    the restarted one did. Read after the start, it saw the re-attach's own promotion, and the
    first live run recorded a hit window as missed (2026-10-03, ``cmp_e39d5b9c24c6``).
    Returns when it was killed, and that read."""
    since = _now()
    subprocess.run(["docker", "kill", RUNTIME], check=True, capture_output=True)
    at_kill = read_at_kill()
    subprocess.run(["docker", "start", RUNTIME], check=True, capture_output=True)
    _healthy()
    return since, at_kill


def _taken_up(since: str, runs: Sequence[str], timeout_s: int = 300) -> list[str]:
    """The runs runtime-api executed again after ``since`` (its ``Executing run`` line)."""
    deadline = time.monotonic() + timeout_s
    while True:
        text = _logs(RUNTIME, since)
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
    runs = runs_of(campaign_id)
    left_open = flow_runs_left_open(runs, open_flow_runs(runs))
    verdict.facts["flow_runs_left_open"] = left_open
    verdict.fail(left_open)
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


def _proposal_in_flight(campaign_id: str) -> str | None:
    running = [r for _c, r, w, st in runs_of(campaign_id) if w == "proposal" and st == "running"]
    return running[-1] if running else None


def restart_at(campaign_id: str, state: str) -> Verdict:
    def there() -> bool:
        if campaign_state(campaign_id)[0] != state:
            return False
        if state == "at_proposal":  # #1934's window: the proposal task is with the proposer
            run = _proposal_in_flight(campaign_id)
            return run is not None and bool(
                dispatched(_logs(RUNTIME, _started_at(run)), PROPOSAL_TASK)
            )
        return state not in _RUN_IN_FLIGHT or bool(_running(campaign_id))

    wait_for(
        there,
        f"the campaign is {state}"
        + (" with its proposal task dispatched" if state == "at_proposal" else "")
        + (" with a run in flight" if state in _RUN_IN_FLIGHT - {"at_proposal"} else ""),
    )
    if state != "at_proposal":
        return _restarted(campaign_id, f"restart-at-{state}", restart_runtime)
    run = _proposal_in_flight(campaign_id)
    before = dispatched(_logs(RUNTIME, _started_at(run)), PROPOSAL_TASK)
    verdict = _restarted(campaign_id, "restart-at-at_proposal", restart_runtime)
    since = verdict.facts["injected_at"]
    # The copy is answered once the original finishes, so it is read when the run has ended.
    wait_for(
        lambda: dict((r, st) for _c, r, _w, st in runs_of(campaign_id)).get(run) != "running",
        "the proposal run ended",
        timeout_s=3600,
    )
    after = dispatched(_logs(RUNTIME, since), PROPOSAL_TASK)
    from_store = replayed(_logs(PROPOSER, since))
    verdict.facts.update(
        {
            "proposal_dispatched_before": before,
            "proposal_dispatched_after": after,
            "proposal_answered_from_store": from_store,
        }
    )
    return verdict.fail(proposal_answered_once(before, after, from_store))


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


def _at_the_ruling(campaign_id: str) -> tuple[str, str]:
    """Wait for the increment gate, and return the proposal run it rules on: (cycle, run)."""
    wait_for(
        lambda: campaign_state(campaign_id)[0] == "awaiting_ruling", "the increment gate is open"
    )
    return [
        (c, r) for c, r, w, st in runs_of(campaign_id) if w == "proposal" and st == "completed"
    ][-1]


def _rule(
    cycle_id: str, run_id: str, notes: str, key: str, decisions: Sequence[str]
) -> list[subprocess.CompletedProcess]:
    """The increment ruling, once per decision flag in ``decisions``, under one key."""
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
        return [squadops(*base, flag) for flag in decisions]


def repeated_ruling(campaign_id: str) -> Verdict:
    cycle_id, run_id = _at_the_ruling(campaign_id)
    key = f"diag-repeat-{run_id}"
    notes = "#1803 diagnostic: a ruling, repeated with its key, then the key reused for a reject"
    first, again, conflict = _rule(
        cycle_id, run_id, notes, key, ("--approve", "--approve", "--reject")
    )
    verdict = repeated_ruling_verdict(control_log(campaign_id), key)
    verdict.facts["cli"] = [first.returncode, again.returncode, conflict.returncode]
    wait_for(
        lambda: any(c == cycle_id and w == "framing" for c, _r, w, _s in runs_of(campaign_id)),
        "framing started after the ruling",
        timeout_s=600,
    )
    return verdict


def _available_gb() -> int:
    with open("/proc/meminfo") as f:
        kb = next(int(line.split()[1]) for line in f if line.startswith("MemAvailable:"))
    return kb // (1024 * 1024)


def _ollama_keep(model: str, keep_alive: str | int) -> None:
    payload = json.dumps({"model": model, "keep_alive": keep_alive})
    subprocess.run(
        ["curl", "-sf", f"{OLLAMA}/api/generate", "-d", payload],
        check=True,
        capture_output=True,
        timeout=600,
    )


@contextmanager
def box_held_by(model: str) -> Iterator[dict]:
    """The box is not quiet while ``model`` is resident. Unloaded on the way out, whatever
    happened: a foreign model left resident refuses every launch after this diagnostic."""
    facts = {"model": model, "available_gb_before": _available_gb()}
    _ollama_keep(model, "2h")
    try:
        facts["available_gb_loaded"] = _available_gb()
        yield facts
    finally:
        _ollama_keep(model, 0)
        facts["available_gb_after_unload"] = _available_gb()


def restart_queued_successor(campaign_id: str) -> Verdict:
    """#2042: the ruling's successor run is created queued and waits for the box, which a foreign
    model holds; the runtime restarts in that window; then the box is freed. The startup
    re-attach must start the successor, once."""
    cycle_id, run_id = _at_the_ruling(campaign_id)
    before = control_log(campaign_id)
    notes = "#2042 diagnostic: a restart while the ruling's successor waits, queued, for the box"
    with box_held_by(FOREIGN_MODEL) as held:
        _rule(cycle_id, run_id, notes, f"diag-successor-{run_id}", ("--approve",))
        wait_for(
            lambda: (
                (s := _queued_successor(campaign_id, cycle_id)) is not None
                and f"run_start_waiting_for_box run={s}" in _logs(RUNTIME, _started_at(run_id))
            ),
            "the successor is queued, waiting for the box",
            timeout_s=900,
        )
        successor = _queued_successor(campaign_id, cycle_id)
        since = restart_runtime()
        queued_after = _queued_successor(campaign_id, cycle_id) == successor
    taken = _taken_up(since, [successor], timeout_s=900)
    starts = _logs(RUNTIME, since).count(f"Executing run {successor} ")
    position = [
        r
        for c, r, w, st in runs_of(campaign_id)
        if c == cycle_id and st != "cancelled" and r != run_id and w == _workload_of(successor)
    ]
    verdict = restart_kept_the_log(
        "restart-queued-successor",
        before,
        control_log(campaign_id),
        campaign_state(campaign_id)[0],
    )
    verdict.facts.update(
        {
            "box": held,
            "injected_at": since,
            "successor": successor,
            "queued_after_restart": queued_after,
            "taken_up": taken,
            "starts_after_restart": starts,
        }
    )
    return verdict.fail(
        [
            *queued_successor_verdict(successor, queued_after, starts, len(position)),
            *decided_once(control_log(campaign_id), cycles_per_launch(campaign_id)),
        ]
    )


def _workload_of(run_id: str) -> str:
    [[workload]] = _psql(
        f"select coalesce(workload_type,'') from cycle_runs where run_id = '{_id(run_id)}'"
    )
    return workload


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

    def committed() -> list[Row]:
        return control_log(campaign_id)[seq_before:]

    killed_at, at_kill = kill_runtime(committed) if completed else (_now(), committed())
    follow.kill()
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
    "restart-queued-successor": restart_queued_successor,
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
