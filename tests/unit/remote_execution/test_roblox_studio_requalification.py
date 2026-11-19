"""Re-qualifying the worker after a Studio update (SIP-0117 R5.21; #3048).

Entered at ``requalify`` and at ``RobloxStudioRunner.run`` with the worker's pins read from its
qualification records, as ``worker.create_runner`` builds it, over the stand-in ``StudioMCP``.
Every record here is written by a re-qualification run, as on the worker, but one:
``RECORD_FROM_2_8`` is a record the 2.8 worker wrote, before a record named Studio's channel
(#3206). The live runs on the real Studio are in the PR (``scripts/dev/studio_requalify.py``).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio import worker as studio_worker
from adapters.remote_execution.game_dev_roblox_studio.qualification import (
    SCHEMA_WITHOUT_CHANNEL,
    Qualifications,
    requalify,
)
from adapters.remote_execution.game_dev_roblox_studio.runner import (
    OPERATION,
    PROVIDER,
    ProvedOn,
    RobloxStudioRunner,
    StudioBusy,
)
from adapters.remote_execution.game_dev_roblox_studio.session import StudioMcpSession
from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.remote_execution.models import OperationStatus
from squadops.remote_execution.registry import WorkerRegistry
from squadops.remote_execution.serving import Worker
from squadops.remote_execution.workers import OperationState, ServedOperation
from tests.unit.remote_execution.registry_contract import Clock, queue
from tests.unit.remote_execution.test_roblox_studio_play_scenario import (
    DECLARATION,
    STANDIN,
    _files,
    _Mac,
    _played,
    _request,
    _scenario,
)
from tests.unit.remote_execution.test_roblox_studio_read_side import _tools
from tests.unit.remote_execution.worker_harness import RegistryWorkerApi, Serving, sleeping_on

#: The MacBook worker's pin through the 2.8 demonstration, byte for byte as the 2.8 worker
#: wrote it on 2026-11-18. It names no channel: the Studio it ran on had moved from
#: ``production`` to another channel that day, at this version (#3206).
RECORD_FROM_2_8 = (
    '{"schema": "squadops.studio-qualification/1", "provider": "roblox-studio", '
    '"provider_version": "2", "recorded_at": "2026-11-18T19:15:13.213301Z", "passed": true, '
    '"failing": "", "studio_version": "0.748.0.7481526", "studio_tools": '
    '"38:1ba499d8d3267332057ed364459a6f845a3cffdf1481094d2f64be01ab4b36a9", "tool_names": '
    '["auto_setup_avatar", "character_navigation", "create_skill", "edit_skill", '
    '"execute_luau", "generate_animation", "generate_avatar", "generate_material", '
    '"generate_mesh", "generate_procedural_model", "generate_scene", "generate_texture", '
    '"get_console_output", "get_studio_state", "http_get", "insert_asset", "inspect_instance", '
    '"list_roblox_studios", "list_skills", "multi_edit", "open_cloud_invoke", "save_place", '
    '"screen_capture", "script_grep", "script_read", "script_search", "search_asset", '
    '"search_game_tree", "segment_mesh", "skill", "start_stop_play", "store_image", '
    '"subagent", "submit_feedback", "upload_image", "user_keyboard_input", "user_mouse_input", '
    '"wait_job_finished"], "replaces": '
    '"d8d6d83bdbea1ac740a729e5d2651399afc1919ab3b29020e63ffcb7a4ab71b1", "tools_added": [], '
    '"tools_removed": [], "scenario_digest": '
    '"sha256:4c660da51d2b6aa81a1fe8e5a9f0d42504a45540e293bbab5087eb364688bf93", '
    '"source_revision": "65dd3c6d8b9ce286b0e4a5873b3eb9d2271d64f0725f5b1ccb46ad279c994b52", '
    '"steps": [{"name": "play 1", "status": "completed", "reason": "", "records": '
    '["hud-screen-visible: passed", "hud-enabled: passed"]}, {"name": "reset", "status": '
    '"reset", "reason": "", "records": []}, {"name": "play 2", "status": "completed", '
    '"reason": "", "records": ["hud-screen-visible: passed", "hud-enabled: passed"]}], '
    '"digest": "46fa73a685047cb6ad3c9c7fa3c6ce59e521bde04d149d6dc661c596332a7cff"}'
)
_NO_LOG = "Studio (pid 4242) holds 0 startup logs open (none)"

#: The qualification scenario: the click's two effects, each of which passes on the stand-in.
PASSING = _scenario(assertions=DECLARATION["assertions"][:2])


class _Studio:
    """The Mac's Studio as a test moves it: its version, and the world its StudioMCP reads."""

    def __init__(self, tmp_path: Path, version: str = "0.747.0") -> None:
        self.version = version
        self.world = _played(tmp_path)
        self.mac = _Mac(world=self.world)
        self.files = _files(tmp_path)

    def update(self, version: str, **tools) -> None:
        """Studio updated itself: a new version, and its tool list changed."""
        self.version = version
        doc = json.loads(self.world.read_text())
        doc["tools"] = _tools(**tools)
        self.world.write_text(json.dumps(doc))

    def moves_to(self, channel: str | OSError) -> None:
        """Roblox's updater moved the install to another release channel, at the same version
        and tool list (#3206). An ``OSError`` is a Studio whose channel can't be read."""
        self.mac.studio_channel = channel

    def runner(self, pins: ProvedOn | Qualifications) -> RobloxStudioRunner:
        return RobloxStudioRunner(
            Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"),
            session_factory=lambda **kw: StudioMcpSession(
                [sys.executable, str(STANDIN), str(self.world)], **kw
            ),
            studio_version_of=lambda _: self.version,
            discover_seconds=0.2,
            reopen_seconds=1.0,
            place_files=self.files,
            proved_on=pins,
            app=self.mac,
        )

    async def requalify(self, records: Qualifications, scenario=PASSING):
        return await requalify(
            records,
            self.runner,
            lambda name: _request(scenario, task_id=f"qualify-{name}", dispatch_id=name),
        )


def _records(tmp_path: Path) -> Qualifications:
    directory = tmp_path / "qualifications"
    directory.mkdir(exist_ok=True)
    return Qualifications(directory)


async def test_a_passing_requalification_moves_the_pin_and_the_next_claim_runs(tmp_path):
    """The done-when, end to end. Bugs caught:
    - an updated Studio still passing scenarios on the old pin;
    - a pin moved by a run that wasn't recorded, or a record that doesn't say what changed;
    - a worker that reads its pin only at start, so it refuses every claim after a passing
      re-qualification until a person restarts it."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    first, _ = await studio.requalify(records)
    worker = studio.runner(records)
    studio.update("0.748.0", insert_model={"readOnlyHint": True})

    refused = await worker.run(_request(PASSING))
    second, path = await studio.requalify(records)
    ran = await worker.run(_request(PASSING))

    assert refused.status is OperationStatus.NOT_EXECUTED
    assert "Studio is 0.748.0, and the operation was proved on 0.747.0" in refused.reason
    assert (first.passed, second.passed, second.failing) == (True, True, "")
    assert [s.name for s in second.steps] == ["play 1", "reset", "play 2"]
    assert (second.studio_version, second.replaces) == ("0.748.0", first.digest)
    assert (second.tools_added, second.tools_removed) == (("insert_model",), ())
    assert path.name.endswith("-passed.json") and records.pinned() == second
    assert ran.status is OperationStatus.COMPLETED, ran.reason
    assert ran.ran_with["qualified_by"] == second.digest[:16]


async def test_a_studio_that_moved_channel_runs_nothing_until_a_requalification_passes(tmp_path):
    """#3206's done-when, end to end, on a Studio whose version and tool list never change.
    Bugs caught:
    - a play run on a channel nothing was proved on, since the version check passed;
    - a failed re-qualification on the new channel moving the pin, or the worker running on
      the old pin after it;
    - a passing one whose record names no channel, or the old one, so the next move isn't seen;
    - a result that doesn't say which Studio it was qualified on and which it played on."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    first, _ = await studio.requalify(records)
    worker = studio.runner(records)
    studio.moves_to("zbeta")

    refused = await worker.run(_request(PASSING))
    failed, failed_path = await studio.requalify(records, _scenario())  # "gold" fails on it
    still_refused = await worker.run(_request(PASSING))
    passed, _ = await studio.requalify(records)
    ran = await worker.run(_request(PASSING))

    moved = "Studio is on channel zbeta, and the operation was proved on channel production"
    assert (first.studio_channel, first.studio_version) == ("production", "0.747.0")
    for result in (refused, still_refused):
        assert result.status is OperationStatus.NOT_EXECUTED
        assert moved in result.reason and result.tool_unready is True
    assert (failed.passed, failed.studio_channel) == (False, "zbeta")
    assert failed.failing == "play 1: gold: failed" and failed_path.name.endswith("-failed.json")
    assert (passed.passed, passed.studio_channel, passed.studio_version) == (
        True, "zbeta", "0.747.0",
    )  # fmt: skip
    assert passed.replaces == first.digest and records.pinned() == passed
    assert ran.status is OperationStatus.COMPLETED, ran.reason
    identity = {
        "studio_version": "0.747.0",
        "studio_channel": "zbeta",
        "studio_tools": first.studio_tools,
    }
    assert {k: v for k, v in ran.ran_with.items() if "." in k and "studio" in k} == {
        **{f"qualified.{k}": v for k, v in identity.items()},
        **{f"played.{k}": v for k, v in identity.items()},
    }
    assert ran.ran_with["qualified_by"] == passed.digest[:16]


async def test_a_requalification_on_a_studio_that_doesnt_say_its_channel_fails(tmp_path):
    """Bug caught: a re-qualification that pins a Studio whose channel it couldn't read, as an
    empty channel or as the last one recorded, so the pin names a Studio nobody identified."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    first, _ = await studio.requalify(records)
    studio.moves_to(OSError(_NO_LOG))
    (tmp_path / "calls.log").unlink(missing_ok=True)

    second, path = await studio.requalify(records)

    assert (second.passed, second.studio_channel) == (False, "")
    assert second.failing == f"tool check: failed: OSError: {_NO_LOG}"
    assert path.name.endswith("-failed.json") and records.pinned() == first
    assert not (tmp_path / "calls.log").exists()  # nothing was played on it


def _the_2_8_record(records: Qualifications, *, after: str | None = None) -> Path:
    """The 2.8 worker's record, written into the directory as it is on the Mac. ``after``
    restamps it later than another record, which changes its body, so it is digested again
    by the 2.8 rule (the body's sorted JSON)."""
    document = json.loads(RECORD_FROM_2_8)
    if after is not None:
        document["recorded_at"] = after
        body = {k: v for k, v in document.items() if k != "digest"}
        document["digest"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    path = records.directory / "20261118T191513.213301Z-passed.json"
    path.write_text(json.dumps(document, indent=2) + "\n")
    return path


async def test_a_record_from_before_the_channel_is_read_as_it_was_written(tmp_path):
    """The Mac's qualifications directory holds five records the 2.8 worker wrote. Bugs
    caught:
    - a record under the earlier schema refused as unreadable, so the directory can never be
      read again and a re-qualification can't say what it replaces;
    - one read back with another digest (its body rebuilt with a channel key), so the worker
      reports its own pin as edited by hand, and ``replaces`` names a record that isn't there."""
    records = _records(tmp_path)
    _the_2_8_record(records)

    [record] = records.records()

    assert (record.schema, record.studio_channel) == (SCHEMA_WITHOUT_CHANNEL, "")
    assert record.digest == json.loads(RECORD_FROM_2_8)["digest"]
    assert record.to_document() == json.loads(RECORD_FROM_2_8)
    assert records.pinned() == record


async def test_a_pin_that_names_no_channel_runs_nothing_and_no_older_record_stands_in(tmp_path):
    """#3206's rule for missing evidence. The newest passing record is the pin, and one made
    before the channel was recorded proves no channel. Bugs caught:
    - the worker playing on a pin that names no channel, as if it named the running one;
    - the worker skipping it for an older record that does name a channel, so a Studio is held
      to a proof a later run replaced."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    older, _ = await studio.requalify(records)
    _the_2_8_record(records, after="2999-01-01T00:00:00.000000Z")
    (tmp_path / "calls.log").unlink(missing_ok=True)

    result = await studio.runner(records).run(_request(PASSING))

    assert older.passed and older.studio_channel == "production"
    assert result.status is OperationStatus.NOT_EXECUTED and result.tool_unready is True
    assert (
        "the newest passing qualification of roblox-studio 2, recorded "
        "2999-01-01T00:00:00.000000Z, names no channel" in result.reason
    )
    assert "No older record and no assumed channel stands in for it; re-qualify" in result.reason
    assert not (tmp_path / "calls.log").exists()  # not a tool was called


@pytest.mark.parametrize(
    ("state", "says"),
    [
        ("a-pin-from-2.8", "nothing was run: the newest passing qualification of roblox-studio "
         "2, recorded 2999-01-01T00:00:00.000000Z, names no channel"),
        ("another-channel", "the worker's tool could not be reset (the worker has just "
         "started, and its tool's state is unknown): PlaceStateError: Studio is on channel "
         "zbeta, and the operation was proved on channel production: Studio moved channel at "
         "0.747.0. Re-qualify the worker on 0.747.0 on channel zbeta with the place open in it "
         "(scripts/dev/studio_requalify.py, #3048); nothing was touched"),
    ],
    ids=["a-pin-from-2.8", "another-channel"],
)  # fmt: skip
async def test_the_runtime_is_told_why_a_worker_on_an_unproved_channel_ran_nothing(
    tmp_path, state, says
):
    """#3206's wiring, entered at ``Worker.serve()`` with the runner as ``create_runner``
    builds it (its pins read from the qualifications directory), over the real registry. The
    two states the MacBook's worker meets:
    - its pin is the 2.8 record, which names no channel. That is the worker the day this
      ships, until it is re-qualified;
    - its pin names ``production`` and Studio came up on another channel, as on 2026-11-18.

    Bugs caught: the operation played; the reason the runtime stores naming no channel; and
    the result not flagged as the worker's own (R5.28), so the Campaign repairs the candidate."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    await studio.requalify(records)
    if state == "a-pin-from-2.8":
        _the_2_8_record(records, after="2999-01-01T00:00:00.000000Z")
    else:
        studio.moves_to("zbeta")
    (tmp_path / "calls.log").unlink(missing_ok=True)
    clock = Clock()
    store = MemoryWorkerRegistryStore()
    registry = WorkerRegistry(store, clock=clock)
    worker = Worker(
        RegistryWorkerApi(registry, clock), studio.runner(records),
        worker_id="macbook", platform="darwin-arm64", clock=clock, sleep=sleeping_on(clock),
    )  # fmt: skip
    asked = _request(PASSING, dispatch_id="dispatch-1")
    queued = await queue(registry, asked, max_attempts=1)

    async def settled() -> bool:
        await asyncio.sleep(0.01)  # the stand-in's sessions are real processes, in real time
        async with store.exclusive() as tx:
            return (await tx.operation(queued.operation_id)).state is OperationState.SETTLED

    async with Serving(worker) as serving:
        await serving.until(settled, turns=6000)  # a minute at most

    async with store.exclusive() as tx:
        result = (await tx.operation(queued.operation_id)).result
    assert worker._runner.serves() == (ServedOperation(PROVIDER, OPERATION),)
    assert result.status is OperationStatus.NOT_EXECUTED
    assert result.reason.startswith(says), result.reason
    assert result.tool_unready is True
    played = [c for c in (tmp_path / "calls.log").read_text().split() if c == "start_stop_play"]
    assert played == []


@pytest.mark.parametrize(
    ("break_it", "failing"),
    [
        (lambda s: None, "play 1: gold: failed"),
        (
            lambda s: s.files.baseline.write_bytes(b"another place"),
            "reset: failed: PlaceStateError: the baseline file",
        ),
    ],
    ids=["an-assertion-fails", "the-reset-fails"],
)
async def test_a_failing_requalification_leaves_the_pin_and_names_the_step(
    tmp_path, break_it, failing
):
    """Bugs caught: a failed run that moves the pin anyway, so the worker serves an updated
    Studio nothing passed on; a reset that fails after the update, read as qualified; a failure
    recorded with no step named, so the person can't tell what the update broke."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    first, _ = await studio.requalify(records)
    studio.update("0.748.0")
    break_it(studio)

    scenario = _scenario() if "gold" in failing else PASSING
    second, path = await studio.requalify(records, scenario)
    after = await studio.runner(records).run(_request(PASSING))

    assert (second.passed, second.studio_version) == (False, "0.748.0")
    assert second.failing.startswith(failing), second.failing
    assert path.name.endswith("-failed.json")
    assert records.pinned() == first
    assert after.status is OperationStatus.NOT_EXECUTED
    assert "proved on 0.747.0" in after.reason


def _hand_edited(path: Path) -> None:
    document = json.loads(path.read_text())
    document["studio_version"] = "0.748.0"
    path.write_text(json.dumps(document))


def _under_another_schema(path: Path) -> None:
    document = json.loads(path.read_text())
    document["schema"] = "squadops.studio-qualification/3"
    path.write_text(json.dumps(document))


def _without_its_channel(path: Path) -> None:
    """A record that names today's schema with the earlier one's keys."""
    document = json.loads(path.read_text())
    del document["studio_channel"]
    path.write_text(json.dumps(document))


@pytest.mark.parametrize(
    ("spoil", "says"),
    [
        (None, "no passing qualification of roblox-studio 2 is recorded"),
        (_hand_edited, "doesn't match its own digest"),
        (lambda path: path.write_text("{"), "can't be read"),
        (lambda path: path.write_text("[]"), "isn't one: it is a list"),
        (_under_another_schema, "names the schema 'squadops.studio-qualification/3'"),
        (_without_its_channel, "isn't one: its keys are"),
    ],
    ids=[
        "none-recorded",
        "a-record-edited-by-hand",
        "a-record-unreadable",
        "a-record-not-an-object",
        "a-record-under-a-schema-not-known",
        "a-record-missing-its-channel",
    ],
)
async def test_a_worker_with_no_record_it_can_trust_runs_nothing(tmp_path, spoil, says):
    """R2.4 and the owner's ruling against silent fallbacks. Bugs caught: a pin moved by
    editing a file; an unreadable newer record skipped, so an older pin is used in its place;
    a worker with no record running on whatever Studio it finds."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    if spoil is not None:
        _, path = await studio.requalify(records)
        spoil(path)
    (tmp_path / "calls.log").unlink(missing_ok=True)

    result = await studio.runner(records).run(_request(PASSING))

    assert result.status is OperationStatus.NOT_EXECUTED
    assert says in result.reason
    assert not (tmp_path / "calls.log").exists()  # not a tool was called


async def test_studio_is_used_by_one_process_at_a_time(tmp_path):
    """Bugs caught: a claim played while a re-qualification quits and reopens Studio under it;
    a worker's reset quitting Studio mid-qualification; a re-qualification started during a
    claim, recording a run the claim interfered with."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    await studio.requalify(records)
    held = list(records.directory.glob("*.json"))
    worker = studio.runner(records)

    with records.exclusive():
        claimed = await worker.run(_request(PASSING))
        with pytest.raises(StudioBusy):
            await worker.reset()
    with worker._proved.exclusive(), pytest.raises(StudioBusy):
        await studio.requalify(records)

    assert claimed.status is OperationStatus.NOT_EXECUTED
    assert "is locked" in claimed.reason
    assert list(records.directory.glob("*.json")) == held  # nothing recorded


@pytest.mark.parametrize(
    ("running", "channel", "ok", "says"),
    [
        (True, "production", True, "qualified on Studio 0.747.0, channel production ("),
        (False, "production", True, "channel production (", ),
        (True, "zbeta", False,
         "Studio is on channel zbeta, and the worker was qualified on channel production: "
         "re-qualify (scripts/dev/studio_requalify.py)"),
        (True, OSError(_NO_LOG),  False,
         f"the running Studio's channel can't be read ({_NO_LOG}), so every claim is refused"),
    ],
    ids=["on-the-qualified-channel", "no-studio-running", "on-another-channel",
         "a-channel-that-cant-be-read"],
)  # fmt: skip
async def test_doctor_reads_the_running_studios_channel_against_the_pin(
    tmp_path, running, channel, ok, says
):
    """``squadops doctor``'s ``qualified`` check (#3046), entered at the provider's
    ``host_checks``. Bugs caught: the doctor reading "qualified" on a Mac whose every claim
    is refused for its channel; and a Mac with Studio closed failing a check it has nothing to
    read for."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    await studio.requalify(records)
    studio.moves_to(channel)
    if not running:
        studio.mac.pid = None
    settings = {"roblox_studio_qualifications": str(records.directory)}

    checks = {c.name: c for c in studio_worker.host_checks(settings, studio.mac)}

    assert (checks["qualified"].passed, says in checks["qualified"].message) == (ok, True), checks
    if not running:
        assert checks["qualified"].message.endswith("no Studio is running to compare")


async def test_doctor_fails_a_pin_that_names_no_channel(tmp_path):
    """Bug caught: the doctor passing the 2.8 worker's record, which every claim refuses."""
    studio, records = _Studio(tmp_path), _records(tmp_path)
    _the_2_8_record(records)
    settings = {"roblox_studio_qualifications": str(records.directory)}

    checks = {c.name: c for c in studio_worker.host_checks(settings, studio.mac)}

    assert checks["qualified"].passed is False
    assert "names no channel" in checks["qualified"].message
