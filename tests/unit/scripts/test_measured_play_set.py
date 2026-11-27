"""``scripts/dev/measured_play_set.py``: a measured set played through the runtime, and two read.

What bugs would these catch?
- A play's claim-to-completion read from the tool's own polling, not the runtime's record, so
  the 20% target is read on a time that includes the poll's lag.
- A set that stopped early, or whose plays didn't all complete, read as a matched pair.
- A cut read from two sets on different qualifications, scenarios or trees.
- A play the tool queued left running after it gives up or is stopped.
- An unread host reading taken as a quiet Mac.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.remote_execution.models import (
    AssertionOutcome,
    AssertionRecord,
    EvidenceItem,
    OperationStatus,
    RemoteOperationResult,
)
from squadops.remote_execution.registry import WorkerRegistry
from squadops.remote_execution.workers import OperationState
from tests.unit.remote_execution.registry_contract import PLAY, Clock, registration
from tests.unit.remote_execution.scenario_fixture import door_opens

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "measured_play_set.py"
_spec = importlib.util.spec_from_file_location("measured_play_set", _SCRIPT)
measured = importlib.util.module_from_spec(_spec)
sys.modules["measured_play_set"] = measured
_spec.loader.exec_module(measured)

OWNER = {"cycle_id": "measured-set:test:run1", "requester": "measured_play_set"}


def _requests(plays: int):
    return measured.set_requests(
        "test",
        "run1",
        plays,
        source_files={"src/server/init.luau": "return {}\n"},
        scenario=door_opens(),
        provider=PLAY.provider,
        operation=PLAY.operation,
    )


def _result(dispatch_id: str, stages: dict | None, *, proved: str = "edcbf9c10a7257c3"):
    evidence = ()
    if stages is not None:
        evidence = (
            EvidenceItem(
                "stages.json",
                json.dumps({"stages": stages, "waits": [0.5], "transactions": 1}),
                "application/json",
            ),
        )
    return RemoteOperationResult(
        status=OperationStatus.COMPLETED,
        records=(AssertionRecord("door_opens", AssertionOutcome.PASSED, "open", "open", "client"),),
        evidence=evidence,
        provider_version="fixture-editor@1",
        ran_with={"qualified_by": proved, "played.studio_version": "0.1"},
        dispatch_id=dispatch_id,
    )


class _Worker:
    """A worker driven by the set's own sleeps: each time the tool waits, it does its next
    thing on the registry's clock. ``plays`` is, for each play, how long it queues before its
    claim, how long it runs, and the stages it reports (``None`` for a play that never ends)."""

    def __init__(self, registry: WorkerRegistry, clock: Clock, plays: list[tuple]):
        self.registry, self.clock, self.plays = registry, clock, list(plays)
        self.session = None
        self.claim = None

    async def sleep(self, seconds: float) -> None:
        if self.session is None:
            self.session = await self.registry.register(registration("macbook", PLAY))
        if self.claim is None:
            wait, _, _ = self.plays[0]
            self.clock.advance(wait)
            self.claim = await self.registry.claim(self.session.session_id)
            return
        _, ran, stages = self.plays[0]
        if ran is None:
            await self._run_for(seconds)
            return
        await self._run_for(ran)
        await self.registry.submit_result(
            self.claim.fence, _result(self.claim.request.dispatch_id, stages)
        )
        self.plays.pop(0)
        self.claim = None

    async def _run_for(self, seconds: float) -> None:
        """The play running: the clock moves, and the worker renews its lease as a real one
        does, every 15 s, so a play longer than the lease isn't read as abandoned."""
        left = seconds
        while left > 0:
            step = min(15.0, left)
            self.clock.advance(step)
            left -= step
            await self.registry.heartbeat(self.session.session_id, "online", self.claim.fence)


async def _world(plays: list[tuple]):
    clock = Clock()
    store = MemoryWorkerRegistryStore()
    registry = WorkerRegistry(store, clock=clock)
    worker = _Worker(registry, clock, plays)
    # A worker is registered before the first play is queued, as the window's opening checks ask.
    worker.session = await registry.register(registration("macbook", PLAY))
    return registry, store, worker


async def test_a_plays_times_are_the_runtimes_own_record_of_it():
    """Entered at ``run_set``, the call ``play`` makes, over the real registry. Bug caught: the
    times taken from the tool's polling. The poll here is 1 s and the worker takes 3 s to
    claim and 97.5 s to play: the record must say exactly that."""
    registry, store, worker = await _world(
        [(3.0, 97.5, {"sync_s": 14.0, "place_state_s": 22.5, "scenario_s": 2.0})]
    )

    plays, stopped = await measured.run_set(
        registry, store, _requests(1), OWNER,
        play_timeout_seconds=600, sleep=worker.sleep, said=lambda line: None,
    )  # fmt: skip

    [play] = plays
    assert stopped == ""
    assert (play["status"], play["outcomes"]) == ("completed", [["door_opens", "passed"]])
    assert (play["queue_wait_s"], play["claim_to_completion_s"]) == (3.0, 97.5)
    assert (play["stages_total_s"], play["outside_stages_s"]) == (38.5, 59.0)
    assert (play["waits"], play["transactions"]) == ([0.5], 1)
    assert (play["served_by"], play["qualified_by"]) == ("macbook", "edcbf9c10a7257c3")
    assert play["played"] == {"studio_version": "0.1"}


async def test_a_play_with_no_result_stops_the_set_and_is_asked_to_stop():
    """Bugs caught: the set going on past a play that never ended, so its record holds a hole;
    and the unfinished play left claimed after the tool returns."""
    registry, store, worker = await _world([(1.0, 50.0, {"sync_s": 1.0}), (1.0, None, None)])

    plays, stopped = await measured.run_set(
        registry, store, _requests(3), OWNER,
        play_timeout_seconds=30, sleep=worker.sleep, said=lambda line: None,
    )  # fmt: skip

    assert [p["status"] for p in plays] == ["completed", "no_result"]
    assert stopped == "play 2 had no result within 30 s"
    assert plays[1]["claim_to_completion_s"] is None
    held = await registry.operation(plays[1]["operation_id"])
    assert (held.state, held.cancel_requested) == (OperationState.CLAIMED, True)


async def test_a_set_with_no_worker_queues_nothing():
    """Bug caught: a set queued for a worker that isn't there, so its first play's queue wait
    is however long the worker took to come back."""
    registry = WorkerRegistry(MemoryWorkerRegistryStore(), clock=Clock())

    plays, stopped = await measured.run_set(
        registry, None, _requests(2), OWNER, play_timeout_seconds=30, said=lambda line: None
    )

    assert plays == []
    assert stopped.startswith("play 1 wasn't queued: NoWorker(")


async def test_a_stopped_tool_asks_every_play_it_queued_to_stop():
    """Bug caught: an interrupted set leaving a play queued for the worker to run for nobody."""
    registry, store, worker = await _world([(1.0, None, None)])

    async def interrupted(seconds: float) -> None:
        await worker.sleep(seconds)
        if worker.claim is not None:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        await measured.run_set(
            registry, store, _requests(2), OWNER,
            play_timeout_seconds=600, sleep=interrupted, said=lambda line: None,
        )  # fmt: skip

    operation = await registry.operation(worker.claim.fence.operation_id)
    assert (operation.state, operation.cancel_requested) == (OperationState.CLAIMED, True)


def test_each_run_of_a_label_is_its_own_sends():
    """Bug caught: a second run of one label reading the first run's results, since the
    registry answers a send it has seen with the operation it queued then."""
    first = measured.set_requests(
        "2.9-before", "aaaa", 2, source_files={"a": "1"}, scenario=door_opens(),
        provider="p", operation="o",
    )  # fmt: skip
    again = measured.set_requests(
        "2.9-before", "bbbb", 2, source_files={"a": "1"}, scenario=door_opens(),
        provider="p", operation="o",
    )  # fmt: skip

    sends = [(r.task_id, r.dispatch_id) for r in (*first, *again)]
    assert len(set(sends)) == 4
    assert sends[0] == (
        "measured-set:2.9-before:aaaa:play-01",
        "measured-set:2.9-before:aaaa:play-01:send-1",
    )
    assert {r.source_revision for r in (*first, *again)} == {first[0].source_revision}


def test_only_text_files_are_staged_and_the_rest_are_named():
    staged, left = measured.staged_text(
        {"src/a.luau": b"return 1\n", "assets/icon.png": b"\x89\xff"}
    )

    assert (staged, left) == ({"src/a.luau": "return 1\n"}, ["assets/icon.png"])


# ---------------------------------------------------------------------------------- the readout


def _play(index: int, seconds: float | None, *, status="completed", proved="edcbf9c1", **more):
    return {
        "index": index,
        "operation_id": f"op_{index}",
        "status": status,
        "reason": "",
        "outcomes": [["shown", "passed"]],
        "queued_at": f"2026-11-27T10:{index:02d}:00.000+00:00",
        "claimed_at": f"2026-11-27T10:{index:02d}:01.000+00:00",
        "settled_at": f"2026-11-27T10:{index:02d}:59.000+00:00",
        "queue_wait_s": 1.0,
        "claim_to_completion_s": seconds,
        "stages": {"sync_s": 14.0, "place_state_s": seconds / 4 if seconds else 0.0},
        "waits": [0.4],
        "transactions": 1,
        "stages_total_s": 30.0,
        "outside_stages_s": 2.0,
        "source_revision": "rev_baseline",
        "served_by": "macbook",
        "qualified_by": proved,
        "played": {},
        **more,
    }


def _set(label: str, seconds: list[float], **play_fields):
    plays = [_play(i, s, **play_fields) for i, s in enumerate(seconds, start=1)]
    return measured.set_document(
        label, project="prj", commit="c0ffee", scenario_name="scenario.json",
        scenario_digest="sha256:aa", asked=len(seconds), plays=plays,
    )  # fmt: skip


@pytest.mark.parametrize(
    ("values", "fraction", "expected"),
    [
        (list(range(1, 21)), 0.95, 19),
        (list(range(1, 11)), 0.95, 10),
        ([7.0], 0.95, 7.0),
        ([3, 1, 2], 0.5, 2),
    ],
    ids=["the 19th of 20", "under 20 it is the maximum", "one value", "unsorted"],
)
def test_the_p95_is_the_nearest_rank(values, fraction, expected):
    assert measured.nearest_rank(values, fraction) == expected


def test_no_values_have_no_rank():
    with pytest.raises(ValueError, match="no values"):
        measured.nearest_rank([], 0.95)


def test_the_summary_counts_what_didnt_complete_beside_what_did():
    """Bug caught: a median over fewer plays than were asked, with nothing saying so."""
    plays = [
        _play(1, 100.0),
        _play(2, 96.0),
        _play(3, None, status="interrupted"),
        _play(4, 98.0, transactions=2),
        _play(5, None, status="no_result"),
    ]

    read = measured.summary(plays)

    assert read["by_status"] == {"completed": 3, "interrupted": 1, "no_result": 1}
    assert read["claim_to_completion_s"] == {
        "median": 98.0, "p95": 100.0, "min": 96.0, "max": 100.0, "read_on": 3,
    }  # fmt: skip
    assert read["stage_median_s"] == {"place_state_s": 24.5, "sync_s": 14.0}
    assert (read["begun_again"], read["without_stages"]) == (1, 0)
    # Three completed plays between 10:01:00 queued and 10:05:59 settled, the whole set's span.
    assert read["plays_per_hour"] == 36.12


def test_two_matched_sets_read_their_cut_against_the_target():
    before, after = _set("before", [100.0] * 20), _set("after", [78.0] * 20)

    read = measured.compare(before, after)

    assert (read["matched"], read["unmatched_because"]) == (True, [])
    assert (read["median_before_s"], read["median_after_s"]) == (100.0, 78.0)
    assert (read["median_cut"], read["target_met"], read["outcomes_unchanged"]) == (
        0.22,
        True,
        True,
    )
    assert read["stage_median_after_s"]["place_state_s"] == 19.5


def test_a_cut_just_under_the_target_is_a_miss():
    read = measured.compare(_set("before", [100.0] * 20), _set("after", [80.5] * 20))

    assert (read["median_cut"], read["target_met"]) == (0.195, False)


@pytest.mark.parametrize(
    ("change", "because"),
    [
        (lambda d: d["scenario"].update(digest="sha256:bb"), "scenario differ"),
        (lambda d: d.update(commit="deadbeef"), "commit differ"),
        (lambda d: d.update(stopped="play 7 had no result within 600 s"), "stopped early"),
        (
            lambda d: d["summary"].update(qualified_by=["0000aaaa"]),
            "the sets ran on different qualifications",
        ),
        (
            lambda d: d["summary"].update(qualified_by=["edcbf9c1", "0000aaaa"]),
            "as its qualification, not one",
        ),
        (
            lambda d: d["summary"].update(by_status={"completed": 19, "interrupted": 1}),
            "plays that didn't complete",
        ),
    ],
    ids=["scenario", "commit", "stopped", "requalified between", "two in one set", "incomplete"],
)
def test_a_pair_that_isnt_matched_says_why(change, because):
    """Bug caught: a cut reported for two sets that differ in more than the change measured."""
    before, after = _set("before", [100.0] * 20), _set("after", [70.0] * 20)
    change(after)

    read = measured.compare(before, after)

    assert read["matched"] is False
    assert any(because in why for why in read["unmatched_because"]), read["unmatched_because"]


def test_a_play_whose_outcome_changed_is_named():
    """Bug caught: a faster play that stopped asserting what it asserted before."""
    before, after = _set("before", [100.0] * 3), _set("after", [70.0] * 3)
    after["plays"][1]["outcomes"] = [["shown", "failed"]]

    read = measured.compare(before, after)

    assert (read["outcomes_unchanged"], read["plays_whose_outcomes_differ"]) == (False, [2])


# -------------------------------------------------------------------------------- the host's bar

QUIET = {
    "load_average": [1.17, 2.07, 2.68],
    "memory_free_percent": 80,
    "models_loaded": [],
    "docker": {"answers": True, "containers_running": 0},
    "processes": {"other": {"count": 557, "cpu_percent": 65.5, "rss_mb": 12100.0}},
}


def test_a_settled_mac_meets_the_start_bar():
    assert measured.host_bar(QUIET, "start") == []


@pytest.mark.parametrize(
    ("change", "miss"),
    [
        ({"load_average": [2.0, 2.1, 2.2]}, "the 1-minute load is 2.0, not under 2.0"),
        ({"load_average": [1.0, 2.9, 3.4]}, "the 15-minute load is 3.4, not under 3.0"),
        ({"memory_free_percent": 69}, "free memory is 69%, under 70%"),
        ({"models_loaded": ["some-model:7b"]}, "1 models are loaded"),
        ({"docker": {"answers": True, "containers_running": 21}}, "21 containers are running"),
        (
            {"processes": {"other": {"count": 9, "cpu_percent": 157.5}}},
            "other processes use 157.5% CPU, not under 100%",
        ),
        ({"load_average": {"unread": "OSError: no sysctl"}}, "the load average wasn't read"),
        ({"memory_free_percent": {"unread": "x"}}, "the free memory wasn't read"),
        ({"models_loaded": {"unread": "x"}}, "the loaded models weren't read"),
        ({"processes": {"unread": "x"}}, "the other processes weren't read"),
    ],
)
def test_a_reading_that_misses_the_start_bar_says_how(change, miss):
    """Bug caught: an unread reading, or one at the bar's edge, taken as a quiet Mac."""
    misses = measured.host_bar({**QUIET, **change}, "start")

    assert len(misses) == 1 and misses[0].startswith(miss), misses


def test_docker_saying_it_isnt_running_is_no_container_and_a_docker_that_hung_is_a_miss():
    """Bug caught: a hung daemon, which can still have containers at work, read as none. The
    reading script answers a hang as ``answers: false`` too, with why it didn't answer."""
    stopped = {**QUIET, "docker": {"answers": False, "why": "OSError: docker exited 1: daemon"}}
    hung = {
        **QUIET,
        "docker": {"answers": False, "why": "TimeoutExpired: Command '['docker', 'ps'..."},
    }
    unread = {key: value for key, value in QUIET.items() if key != "docker"}
    told = ["docker didn't answer in time, so its containers weren't read"]

    assert measured.host_bar(stopped, "start") == []
    assert (measured.host_bar(hung, "start"), measured.host_bar(hung, "end")) == (told, told)
    assert measured.host_bar(unread, "start") == ["docker wasn't read"]


def test_the_end_bar_holds_only_what_the_set_cant_have_caused():
    """A set of plays raises the load and Studio's memory by itself. A container or a model
    at its end is something else at work."""
    busy = {**QUIET, "load_average": [4.2, 3.8, 3.1], "memory_free_percent": 55}

    assert measured.host_bar(busy, "end") == []
    assert measured.host_bar({**busy, "models_loaded": ["m"]}, "end") == ["1 models are loaded"]


def test_the_command_exits_nonzero_for_an_unmatched_pair(tmp_path, capsys):
    before, after = _set("before", [100.0] * 2), _set("after", [70.0] * 2)
    after["commit"] = "deadbeef"
    (tmp_path / "b.json").write_text(json.dumps(before))
    (tmp_path / "a.json").write_text(json.dumps(after))

    code = measured.main(["compare", str(tmp_path / "b.json"), str(tmp_path / "a.json")])

    assert code == 1
    assert json.loads(capsys.readouterr().out)["matched"] is False
