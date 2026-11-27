"""``scripts/dev/play_isolation_sequence.py``: one play's state never reaches another.

What bugs would these catch?
- A reader that can't see a mark, so "absent" after a marked play proves nothing.
- A leak after a completed, a failed or an interrupted play read as isolated.
- The marks put where the product's own headless loader meets them, or above ``--!strict``.
- A scenario the reader's vocabulary refuses, found only when the sequence is played.
- A pair said to compete that was never queued together.
"""

from __future__ import annotations

import copy
import dataclasses
import importlib.util
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio.vocabulary import VOCABULARY
from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.remote_execution.models import (
    AssertionOutcome,
    AssertionRecord,
    OperationStatus,
    RemoteOperationResult,
)
from squadops.remote_execution.registry import WorkerRegistry
from squadops.remote_execution.scenario import frozen_scenario, staged_revision
from squadops.remote_execution.workers import ServedOperation, WorkerRegistration
from tests.unit.remote_execution.registry_contract import Clock

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "play_isolation_sequence.py"
_spec = importlib.util.spec_from_file_location("play_isolation_sequence", _SCRIPT)
isolation = importlib.util.module_from_spec(_spec)
sys.modules["play_isolation_sequence"] = isolation
_spec.loader.exec_module(isolation)

PLAY = ServedOperation("roblox-studio", "play_scenario")
OWNER = {"cycle_id": "isolation-sequence:test", "requester": "play_isolation_sequence"}
SERVER, CLIENT = "src/Server/Boot.server.luau", "src/Client/Boot.local.luau"
BASELINE = {
    SERVER: "--!strict\n-- starts the round\nlocal Rounds = require(script.Parent.Rounds)\n",
    CLIENT: "-- shows the lobby\nlocal Lobby = require(script.Parent.Lobby)\n",
    "src/Server/Rounds.luau": "return {}\n",
    "README.md": "a game\n",
}
BASELINE_SCENARIO = {
    "schema": "squadops.scenario/1",
    "scenario_id": "lobby-shown",
    "reader": "roblox-studio/1",
    "setup": [],
    "steps": [],
    "assertions": [
        {
            "id": "lobby-shown",
            "observe": {
                "kind": "gui_state", "path": "@player.PlayerGui.Lobby", "state": "visible",
                "context": "client",
            },
            "expect": {"op": "equals", "value": True},
        }
    ],
    "named_assertion": "lobby-shown",
}  # fmt: skip


# ------------------------------------------------------------------------------------ the trees


def test_the_marked_tree_marks_before_it_reads_and_keeps_the_scripts_own_first_lines():
    """Bugs caught: the reader ahead of the marks, so a marked play reads its own marks as
    absent; a block above ``--!strict``; a block the headless loader would run."""
    marked = isolation.marked_tree(BASELINE)

    server = marked[SERVER].split("\n")
    assert server[:2] == ["--!strict", "-- starts the round"]
    assert server[2].startswith(
        'if typeof(game) == "Instance" then -- __squadops_isolation_probe__'
    )
    assert marked[SERVER].index("marks (server)") < marked[SERVER].index("reader (server)")
    assert marked[CLIENT].index("marks (client)") < marked[CLIENT].index("reader (client)")
    assert marked[SERVER].endswith("local Rounds = require(script.Parent.Rounds)\n")
    assert marked[isolation.RESIDUE_MODULE].startswith("-- __squadops_isolation_probe__")


def test_the_reading_tree_reads_and_marks_nothing():
    """Bug caught: a mark in the tree that is meant to find none, which would read as a leak
    from the play before it."""
    reading = isolation.reading_tree(BASELINE)

    assert "reader (server)" in reading[SERVER] and "reader (client)" in reading[CLIENT]
    # It names each mark only to look for it: it sets no attribute but its own reports, makes
    # no instance, and writes no global.
    both = reading[SERVER] + reading[CLIENT]
    assert "marks (" not in both
    assert 'SetAttribute("squadops_mark' not in both and "Instance.new" not in both
    assert "squadops_mark_global =" not in both and ".mark =" not in both
    assert isolation.RESIDUE_MODULE not in reading
    assert isolation.PROBE_MODULE in reading
    assert reading["README.md"] == BASELINE["README.md"]


def test_the_three_trees_stage_as_three_revisions_and_the_baseline_is_untouched():
    before = copy.deepcopy(BASELINE)
    trees = [BASELINE, isolation.marked_tree(BASELINE), isolation.reading_tree(BASELINE)]

    assert BASELINE == before
    assert len({staged_revision(dict(tree)) for tree in trees}) == 3


@pytest.mark.parametrize(
    ("tree", "why"),
    [
        ({SERVER: "x\n"}, "holds no .local.luau script under src/Client/"),
        ({CLIENT: "x\n"}, "holds no .server.luau script under src/Server/"),
        (
            {**BASELINE, "src/Shared/SquadopsProbe.luau": "return 1\n"},
            "already holds src/Shared/SquadopsProbe.luau",
        ),
    ],
    ids=["no client script", "no server script", "the probe's path is taken"],
)
def test_a_tree_the_sequence_cant_mark_is_refused_by_name(tree, why):
    with pytest.raises(ValueError, match=why):
        isolation.marked_tree(tree)


# -------------------------------------------------------------------------------- the scenarios


@pytest.mark.parametrize("expected", ["present", "absent"])
def test_the_marks_scenario_is_one_the_readers_vocabulary_accepts(expected):
    """Bug caught: a scenario the roblox-studio reader refuses, found only at the first play."""
    scenario = frozen_scenario(isolation.marks_scenario("isolation-x", expected), VOCABULARY)
    document = isolation.marks_scenario("isolation-x", expected)

    assert scenario.digest.startswith("sha256:")
    assert [a["id"] for a in document["assertions"]] == [
        f"attribute-{expected}",
        f"value-{expected}",
        f"global-{expected}",
        f"module-{expected}",
        f"residue-{expected}",
        f"gui-{expected}",
        f"client-global-{expected}",
    ]
    assert [(s["observe"]["context"], s["expect"]["value"]) for s in document["setup"]] == [
        ("server", "server"),
        ("client", "client"),
    ]
    assert {a["observe"]["context"] for a in document["assertions"][5:]} == {"client"}


def test_the_unmet_setup_waits_on_something_no_tree_sets():
    document = isolation.unmet_setup_scenario()

    frozen_scenario(document, VOCABULARY)
    [setup] = document["setup"]
    assert (setup["observe"]["name"], setup["deadline_s"]) == ("squadops_seen_never_set", 5)
    assert "never_set" not in isolation.SERVER_READER_BLOCK + isolation.CLIENT_READER_BLOCK


# --------------------------------------------------------------------------------- the sequence


class _Worker:
    """A worker driven by the sequence's own sleeps, on the registry's clock. It plays each
    claim for three seconds, renewing its lease, and answers by what the request's tree and
    scenario are. A play that is asked to stop answers ``interrupted``."""

    def __init__(self, registry, clock, *, leaks_after: str = "", blind: bool = False):
        self.registry, self.clock = registry, clock
        self.leaks_after, self.blind = leaks_after, blind
        self.session = None
        self.claim = None
        self.ran = 0.0
        self.last_ended = ""

    async def sleep(self, seconds: float) -> None:
        self.clock.advance(seconds)
        if self.claim is None:
            self.claim = await self.registry.claim(self.session.session_id)
            self.ran = 0.0
            return
        told = await self.registry.heartbeat(self.session.session_id, "online", self.claim.fence)
        request = self.claim.request
        if told.cancel_requested:
            await self._submit(OperationStatus.INTERRUPTED, (), "cancelled")
            self.last_ended = "interrupted"
            return
        self.ran += seconds
        if self.ran < (60.0 if "marked-cancelled" in request.task_id else 3.0):
            return
        marked = isolation.RESIDUE_MODULE in request.source_files
        scenario = request.scenario.scenario_id
        if scenario == "isolation-setup-unmet":
            outcomes, ended = _records(request, AssertionOutcome.SETUP_FAILED), "setup_failed"
        elif scenario == "isolation-marks-present":
            seen = marked and not self.blind
            outcomes = _records(
                request, AssertionOutcome.PASSED if seen else AssertionOutcome.FAILED
            )
            ended = "completed"
        elif scenario == "isolation-nothing-left":
            leaked = self.leaks_after == self.last_ended
            outcomes = _records(request, AssertionOutcome.PASSED, failing_first=leaked)
            ended = self.last_ended
        else:
            outcomes, ended = _records(request, AssertionOutcome.PASSED), self.last_ended
        await self._submit(OperationStatus.COMPLETED, outcomes, "")
        self.last_ended = ended

    async def _submit(self, status, records, reason) -> None:
        request = self.claim.request
        await self.registry.submit_result(
            self.claim.fence,
            RemoteOperationResult(
                status=status,
                records=records,
                reason=reason,
                provider_version="roblox-studio@2",
                ran_with={"source_revision": request.source_revision, "place_baseline": "pin0000"},
                dispatch_id=request.dispatch_id,
            ),
        )
        self.claim = None


def _records(request, outcome, *, failing_first: bool = False):
    ids = request.scenario.assertions
    return tuple(
        AssertionRecord(
            assertion_id,
            AssertionOutcome.FAILED if failing_first and i == 0 else outcome,
            context="server",
        )
        for i, assertion_id in enumerate(ids)
    )


class _Ticking(Clock):
    """A clock no two readings of which are the same instant, as a real one's aren't: the
    registry gives the older of two queued operations first, and two queued at one frozen
    instant have no older one."""

    def __call__(self):
        self.now += timedelta(microseconds=1)
        return self.now


async def _played(**worker):
    clock = _Ticking()
    store = MemoryWorkerRegistryStore()
    registry = WorkerRegistry(store, clock=clock)
    stand_in = _Worker(registry, clock, **worker)
    stand_in.session = await registry.register(
        WorkerRegistration(
            worker_id="macbook",
            platform="macos-arm64",
            tool_versions={"roblox-studio": "0.1"},
            operations=(PLAY,),
        )  # fmt: skip
    )
    steps = tuple(
        dataclasses.replace(step, cancel_after_s=2.0) if step.cancel_after_s else step
        for step in isolation.SEQUENCE
    )
    scenarios = {
        "baseline": frozen_scenario(BASELINE_SCENARIO, VOCABULARY),
        "present": frozen_scenario(
            isolation.marks_scenario("isolation-marks-present", "present"), VOCABULARY
        ),
        "absent": frozen_scenario(
            isolation.marks_scenario("isolation-nothing-left", "absent"), VOCABULARY
        ),
        "unmet": frozen_scenario(isolation.unmet_setup_scenario(), VOCABULARY),
    }
    trees = {
        "baseline": BASELINE,
        "marked": isolation.marked_tree(BASELINE),
        "reading": isolation.reading_tree(BASELINE),
    }
    requests = isolation.sequence_requests(
        "run1", trees=trees, scenarios=scenarios, provider=PLAY.provider,
        operation=PLAY.operation, steps=steps,
    )  # fmt: skip
    plays, stopped = await isolation.run_sequence(
        registry, store, steps, requests, OWNER,
        play_timeout_seconds=300, sleep=stand_in.sleep, said=lambda line: None,
    )  # fmt: skip
    return {"stopped": stopped, "plays": plays}


async def test_the_whole_sequence_over_the_real_registry_reads_isolated():
    """Entered at ``run_sequence``, the call ``play`` makes, over the real ``WorkerRegistry``.
    Bugs caught: a step played out of turn, the cancel never sent, or the pair queued one
    after the other and still read as competing."""
    document = await _played()

    assert document["stopped"] == ""
    assert [(p["step"], p["status"]) for p in document["plays"]] == [
        ("baseline-first", "completed"),
        ("marked", "completed"),
        ("after-a-completed-play", "completed"),
        ("marked-setup-fails", "completed"),
        ("after-a-failed-play", "completed"),
        ("marked-cancelled", "interrupted"),
        ("after-an-interrupted-play", "completed"),
        ("baseline-again", "completed"),
        ("competing-marked", "completed"),
        ("competing-reading", "completed"),
    ]
    first, second = document["plays"][8], document["plays"][9]
    assert second["queued_at"] < first["settled_at"] <= second["claimed_at"]
    reading = isolation.read_sequence(document)
    assert reading["isolated"] is True
    assert [name for name, t in reading["tests"].items() if t["holds"] is not True] == []
    assert len(reading["tests"]) == 10


@pytest.mark.parametrize(
    ("leaks_after", "test"),
    [
        ("completed", "nothing is left after a completed play"),
        ("setup_failed", "nothing is left after a failed play"),
        ("interrupted", "nothing is left after an interrupted play"),
    ],
)
async def test_a_mark_left_behind_is_a_leak_named_by_where_it_was_found(leaks_after, test):
    """Bug caught: a leak after one kind of ending read as isolated because the others held."""
    reading = isolation.read_sequence(await _played(leaks_after=leaks_after))

    assert reading["isolated"] is False
    assert reading["tests"][test]["holds"] is False
    assert "not read as absent: ['attribute-absent']" in reading["tests"][test]["why"][0]


async def test_a_reader_that_cant_see_a_mark_fails_the_sequence_though_nothing_reads_left():
    """Bug caught: 'absent' everywhere taken as isolation when the reader sees nothing at all."""
    reading = isolation.read_sequence(await _played(blind=True))

    assert reading["isolated"] is False
    assert reading["tests"]["the marks are made, and the reader sees them"]["holds"] is False
    assert reading["tests"]["nothing is left after a completed play"]["holds"] is True


async def test_a_sequence_that_stopped_early_isnt_isolated_and_its_unplayed_tests_arent_read():
    document = await _played()
    cut = {
        "stopped": "step marked-cancelled had no result within 300 s",
        "plays": document["plays"][:5],
    }

    reading = isolation.read_sequence(cut)

    assert reading["isolated"] is False
    assert reading["tests"]["nothing is left after a failed play"]["holds"] is True
    assert reading["tests"]["nothing is left after an interrupted play"] == {
        "holds": None,
        "why": ["not read: no play of after-an-interrupted-play"],
    }


@pytest.mark.parametrize(
    ("change", "test", "why"),
    [
        (
            lambda plays: plays[7].update(place_baseline="drifted0"),
            "every completed play read one place baseline",
            "read ['drifted0', 'pin0000']",
        ),
        (
            lambda plays: plays[2].update(ran_source_revision="rev_of_the_marked_tree"),
            "every play ran the revision asked, and each tree is its own",
            "ran a revision other than the one asked: ['after-a-completed-play']",
        ),
        (
            lambda plays: plays[9].update(queued_at=plays[8]["settled_at"]),
            "two plays queued together run one after the other, each on its own tree",
            "the second wasn't queued until the first had settled, so nothing competed",
        ),
        (
            lambda plays: plays[9].update(claimed_at=plays[8]["queued_at"]),
            "two plays queued together run one after the other, each on its own tree",
            "the reading play was claimed first, so it had no marked play before it",
        ),
        (
            lambda plays: plays[8].update(settled_at=plays[9]["settled_at"]),
            "two plays queued together run one after the other, each on its own tree",
            "the second was claimed before the first settled",
        ),
        (
            lambda plays: plays[7].update(outcomes=[["lobby-shown", "failed"]]),
            "the baseline reads the same before and after the candidates",
            "the two baseline plays' outcomes differ",
        ),
    ],
    ids=[
        "a drifted place",
        "another tree's revision",
        "never competed",
        "the reading play went first",
        "ran together",
        "baseline moved",
    ],
)
async def test_each_way_the_record_can_fail_a_test_is_said(change, test, why):
    document = await _played()
    change(document["plays"])

    reading = isolation.read_sequence(document)

    assert reading["isolated"] is False
    assert reading["tests"][test] == {"holds": False, "why": [why]}
