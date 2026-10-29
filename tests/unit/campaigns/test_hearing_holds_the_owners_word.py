"""An owner's pause or abort holds across a campaign cycle's hearing (#2789; SIP-0109 §10, §17,
§24cq).

Entered where the live campaign enters: ``CampaignProgress.cycle_ended``, the completion boundary's
call, and ``rehear_ended``, the startup's and the sweep's. The progress and the evaluator are built
as the runtime root builds them (``main.py``). The world is the shared fixture's Tally, in a real
managed clone: its campaign started by its calibration record, an increment launched by the owner's
word and delivered for real (verified and captured). Its ending is evaluated against a pinned suite
by a runner that applies the owner's operation while it reads the increment's tree, as an owner
acting during a minutes-long evaluation would.

What bugs would these catch?
- the promotion written from the campaign read before the evaluation, which moves a paused campaign
  out of ``paused`` and lets the decision launch over the owner's brake;
- an abort's refusal raised out of the hearing;
- a moved campaign never decided once it is resumed, or its evaluation taken twice;
- a decision written over a pause applied after the promotion;
- a paused campaign's ending decided while it is paused.
"""

from __future__ import annotations

import logging

import pytest

from squadops.campaigns.calibration_record import recorded_calibration
from squadops.campaigns.models import (
    CampaignOutcome,
    CampaignState,
    ControlOperation,
    ControlOutcome,
    RefusalReason,
)
from squadops.cycles.cycle_end import CycleStopReason, RecordedEnd
from tests.unit.campaigns.test_campaign_branch import CID, _added, _World
from tests.unit.scenarios.test_campaign_baseline_reading import (
    _AbortsAsItPromotes,
    _evaluator,
    _owners,
    _progress,
    _rows,
    _Runner,
    _store,
)
from tests.unit.scenarios.test_campaign_cycles_declared_start import _without_secret

INCREMENT = "cyc_inc000000001"
PAUSE = _owners(ControlOperation.PAUSE, CampaignState.PAUSED, "pause-inc")
ABORT = _owners(
    ControlOperation.ABORT, CampaignState.COMPLETED, "abort-inc", outcome=CampaignOutcome.ABORTED
)


class _ActsOnTheIncrement(_Runner):
    """The owner's operation, applied while the increment's tree is read: the runner's second
    call, the first being the calibration record's baseline reading."""

    def __init__(self, world, transition=None) -> None:
        super().__init__(world)
        self.transition = transition

    async def evaluate_tree(self, **kw):
        if self.calls and self.transition is not None:
            await self.world.campaigns.transition(CID, self.transition)
        return await super().evaluate_tree(**kw)


async def _delivered(tmp_path, *, runner_acts=None, campaigns=None):
    """Tally's campaign started by its record, and its first increment delivered for real, its
    ending recorded as the completion boundary records it. Returns the world, the store, the
    runner, the cycle and its run, and the progress that hears it."""
    world = _World(tmp_path)
    world.projects.configuration = _without_secret(world.projects.configuration)
    store = await _store()
    runner = _ActsOnTheIncrement(world, runner_acts)
    world.progress = _progress(world, _evaluator(world, store, runner), store)
    await world.started()
    cycle, run, _captured = await world.delivered(INCREMENT, _added("total"))
    await world.cycles.record_cycle_end(
        RecordedEnd(cycle.cycle_id, run.run_id, CycleStopReason.SEQUENCE_COMPLETED)
    )
    progress = (
        _progress(
            world, _evaluator(world, store, runner), store, campaigns=campaigns(world.campaigns)
        )
        if campaigns
        else world.progress
    )
    return world, store, runner, cycle, run, progress


async def _increment_rows(world) -> tuple[list, list]:
    log = await world.campaigns.control_log(CID)
    promotions = [e for e in _rows(log, ControlOperation.PROMOTE) if e.target == INCREMENT]
    decisions = [e for e in _rows(log, ControlOperation.DECIDE) if e.target == INCREMENT]
    return promotions, decisions


def _decided(decisions) -> list:
    """The decision rows proper: not the move to evaluating, which is a DECIDE row too."""
    return [e for e in decisions if "row" in e.binding]


async def test_a_pause_during_the_evaluation_holds_and_the_resumed_campaign_is_decided_once(
    tmp_path,
):
    """#2789, as found. Bugs caught: the promotion written from the campaign as it was before the
    evaluation (``paused → building``) and the decision launching over the owner's brake; the
    re-hearing deciding it while it is still paused; or, once resumed, never deciding it, or
    evaluating the increment a second time."""
    world, store, runner, cycle, run, progress = await _delivered(tmp_path, runner_acts=PAUSE)

    assert await progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED) is None
    promotions, decisions = await _increment_rows(world)
    assert (promotions, decisions) == ([], [])
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.PAUSED
    assert await progress.rehear_ended([INCREMENT]) == []

    await world.campaigns.transition(
        CID, _owners(ControlOperation.RESUME, CampaignState.BUILDING, "resume-inc")
    )
    assert await progress.rehear_ended([INCREMENT]) == [INCREMENT]

    promotions, decisions = await _increment_rows(world)
    assert len(promotions) == 1 and len(_decided(decisions)) == 1
    assert len(await store.evaluations_for_cycle(INCREMENT)) == 1
    assert len(runner.calls) == 2  # the baseline's, and the increment's once
    assert await progress.rehear_ended([INCREMENT]) == []


async def test_an_abort_during_the_evaluation_holds_and_the_hearing_never_raises(tmp_path):
    """#2789's abort. Bugs caught: the promotion's refusal raised out of the completion boundary,
    so the ending is logged as the campaign's failure; or a promotion or decision written for an
    aborted campaign, by this hearing or a re-hearing."""
    world, _store_, _runner, cycle, run, progress = await _delivered(tmp_path, runner_acts=ABORT)

    assert await progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED) is None
    assert await _increment_rows(world) == ([], [])
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.COMPLETED
    assert await progress.rehear_ended([INCREMENT]) == []


async def test_a_promotion_refused_in_the_last_instant_is_logged_never_raised(tmp_path, caplog):
    """#2789's remainder: no read closes the window to the write itself. Bug caught: the refusal
    raised out of the hearing, which the completion boundary logs as the campaign's failure."""
    world, _store_, _runner, cycle, run, progress = await _delivered(
        tmp_path, campaigns=_AbortsAsItPromotes
    )

    with caplog.at_level("ERROR", logger="squadops.campaigns.progress"):
        assert await progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED) is None

    errors = [
        r
        for r in caplog.records
        if r.name == "squadops.campaigns.progress" and r.levelno >= logging.ERROR
    ]
    assert [r.getMessage() for r in errors] == ["campaign_cycle_promotion_refused"]
    _promotions, decisions = await _increment_rows(world)
    assert _decided(decisions) == []
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.COMPLETED


async def test_a_pause_after_the_promotion_holds_the_decision_and_the_resume_decides_it(tmp_path):
    """#2789: the campaign is read again before the decision too, after the promotion and the
    reads that build the decision. Bugs caught: the decision written from the state the promotion
    left, over a pause applied since; or the resumed campaign, back in ``evaluating``, never
    decided, or promoted twice."""
    world, store, _runner, cycle, run, progress = await _delivered(tmp_path)
    building = progress._launch_for

    async def pause_then_build(*args, **kwargs):
        await world.campaigns.transition(CID, PAUSE)
        return await building(*args, **kwargs)

    progress._launch_for = pause_then_build

    assert await progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED) is None
    promotions, decisions = await _increment_rows(world)
    assert (len(promotions), _decided(decisions)) == (1, [])
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.PAUSED

    progress._launch_for = building
    await world.campaigns.transition(
        CID, _owners(ControlOperation.RESUME, CampaignState.EVALUATING, "resume-eval")
    )
    assert await progress.rehear_ended([INCREMENT]) == [INCREMENT]
    promotions, decisions = await _increment_rows(world)
    assert (len(promotions), len(_decided(decisions))) == (1, 1)
    assert len(await store.evaluations_for_cycle(INCREMENT)) == 1


async def test_a_campaign_paused_before_its_cycle_ends_is_decided_once_it_is_resumed(tmp_path):
    """§17: a paused campaign holds its pending action until its resume. **This changes the
    hearing's behaviour (#2789):** before it, a campaign already paused when its cycle's ending was
    heard was promoted and decided at once, and the decision moved it out of ``paused``. A limit's
    pause records its action as held (``held_action``); an owner's pause made before the ending
    had no such record, so the decision launched over it. Now the ending waits, unheard, and is
    decided once the campaign is resumed. Bugs caught: a decision, a promotion or an evaluation
    while paused; or the resumed campaign never decided."""
    world, store, runner, cycle, run, progress = await _delivered(tmp_path)
    await world.campaigns.transition(CID, PAUSE)

    assert await progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED) is None
    assert await _increment_rows(world) == ([], [])
    assert (len(runner.calls), await store.evaluations_for_cycle(INCREMENT)) == (1, [])

    await world.campaigns.transition(
        CID, _owners(ControlOperation.RESUME, CampaignState.BUILDING, "resume-pre")
    )
    assert await progress.rehear_ended([INCREMENT]) == [INCREMENT]
    promotions, decisions = await _increment_rows(world)
    assert (len(promotions), len(_decided(decisions))) == (1, 1)
    assert len(await store.evaluations_for_cycle(INCREMENT)) == 1


async def test_a_campaign_left_alone_is_heard_as_before(tmp_path):
    """The control: nothing moved, so the hearing promotes and decides at once, its evaluation
    taken once. Bug caught: a re-read that reads every hearing as moved, so no ending is ever
    decided."""
    world, store, runner, cycle, run, progress = await _delivered(tmp_path)

    decision = await progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)

    assert decision is not None and decision.cycle_id == INCREMENT
    promotions, decisions = await _increment_rows(world)
    assert (len(promotions), len(_decided(decisions))) == (1, 1)
    assert (len(runner.calls), len(await store.evaluations_for_cycle(INCREMENT))) == (2, 1)
    record = recorded_calibration(await world.campaigns.control_log(CID))
    assert promotions[0].binding["parent_commit"] == record.commit


class _StopsAtTheDecision:
    """The campaign registry of a process that stops after the promotion and the move to
    evaluating, before the decision commits."""

    def __init__(self, inner) -> None:
        self._inner, self.stopped = inner, False

    async def transition(self, campaign_id, transition):
        if (
            transition.operation is ControlOperation.DECIDE
            and "row" in transition.binding
            and not self.stopped
        ):
            self.stopped = True
            raise RuntimeError("the process stopped")
        return await self._inner.transition(campaign_id, transition)

    def __getattr__(self, name):
        return getattr(self._inner, name)


async def test_a_restart_after_the_move_to_evaluating_decides_the_ending_once(tmp_path):
    """§12a, which #2789's re-reads lean on: a re-hearing takes an applied promotion as written.
    Bug caught (latent before #2789): the restarted hearing replaying the promotion with the
    campaign's new state (``evaluating``) under the old key, which the registry refuses as a
    conflict, so the ending is never decided."""
    world, store, runner, cycle, run, stopping = await _delivered(
        tmp_path, campaigns=_StopsAtTheDecision
    )
    with pytest.raises(RuntimeError, match="the process stopped"):
        await stopping.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.EVALUATING

    restarted = _progress(world, _evaluator(world, store, runner), store)
    assert await restarted.rehear_ended([INCREMENT]) == [INCREMENT]

    promotions, decisions = await _increment_rows(world)
    assert (len(promotions), len(_decided(decisions))) == (1, 1)
    assert len(await store.evaluations_for_cycle(INCREMENT)) == 1


def _stale(log, operation, key_prefix: str) -> list:
    """The rows of ``operation`` the registry refused as stale, for the increment."""
    return [
        e.refusal
        for e in log
        if e.operation is operation
        and e.outcome is ControlOutcome.REFUSED
        and e.idempotency_key.startswith(key_prefix)
    ]


async def test_a_pause_while_the_bundles_are_frozen_refuses_the_promotion_and_the_resume_decides(
    tmp_path,
):
    """The review of #2792 (P2): the promotion's own I/O comes after the hearing's re-read. Bug
    caught: a pause applied while the increment's frozen bundles are stored, overwritten by the
    promotion (``paused → building``), and the decision launching over it. The promotion carries
    the state the hearing read, so the registry refuses it as stale; the resumed campaign is
    promoted and decided once."""
    world, store, _runner, cycle, run, progress = await _delivered(tmp_path)
    freeze = progress._freeze_bundles

    async def pause_then_freeze(*args, **kwargs):
        await world.campaigns.transition(CID, PAUSE)
        return await freeze(*args, **kwargs)

    progress._freeze_bundles = pause_then_freeze
    assert await progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED) is None

    log = await world.campaigns.control_log(CID)
    assert _stale(log, ControlOperation.PROMOTE, f"promote:{INCREMENT}:") == [
        RefusalReason.STALE_STATE
    ]
    assert await _increment_rows(world) == ([], [])
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.PAUSED

    progress._freeze_bundles = freeze
    await world.campaigns.transition(
        CID, _owners(ControlOperation.RESUME, CampaignState.BUILDING, "resume-freeze")
    )
    assert await progress.rehear_ended([INCREMENT]) == [INCREMENT]
    promotions, decisions = await _increment_rows(world)
    assert (len(promotions), len(_decided(decisions))) == (1, 1)
    assert len(await store.evaluations_for_cycle(INCREMENT)) == 1


async def test_a_pause_while_the_branch_follows_refuses_the_move_to_evaluating_and_the_resume_decides(
    tmp_path,
):
    """P2: a pause applied while the campaign branch's ref follows the promotion's row. Bug caught:
    the move to ``evaluating`` written over it (``paused → evaluating``), and the decision after. The
    move carries the state the promotion left, so it is refused as stale; the resumed campaign is
    decided once, its promotion taken as written."""
    world, store, _runner, cycle, run, progress = await _delivered(tmp_path)
    branch = progress._campaign_branch
    follow = branch.follow

    async def pause_then_follow(*args, **kwargs):
        await world.campaigns.transition(CID, PAUSE)
        return await follow(*args, **kwargs)

    branch.follow = pause_then_follow
    assert await progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED) is None

    log = await world.campaigns.control_log(CID)
    assert _stale(log, ControlOperation.DECIDE, f"evaluate:{INCREMENT}") == [
        RefusalReason.STALE_STATE
    ]
    promotions, decisions = await _increment_rows(world)
    assert (len(promotions), _decided(decisions)) == (1, [])
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.PAUSED

    branch.follow = follow
    await world.campaigns.transition(
        CID, _owners(ControlOperation.RESUME, CampaignState.BUILDING, "resume-follow")
    )
    assert await progress.rehear_ended([INCREMENT]) == [INCREMENT]
    promotions, decisions = await _increment_rows(world)
    assert (len(promotions), len(_decided(decisions))) == (1, 1)
    assert len(await store.evaluations_for_cycle(INCREMENT)) == 1
