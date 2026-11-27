"""SIP-0117 R5.32's provider half (#3200): the script error a play's console names.

The blocks are the shapes the Spark lane read in six stored consoles on 2026-11-26 (rehearsal 3,
``cyc_4c0ec08c327d``; #3222's diagnostic, ``cyc_e8260793f781``), with the player's name as a
stand-in. The product's own text isn't reproduced here: only the lines that make each shape.

What bugs would these catch?
- A follow-on reported as the error: a failed module load writes one more block in each script
  up its require chain, each naming a staged file the candidate may not have changed.
- An error raised in the provider's own probe, or in Studio's code, reported as the candidate's.
- A client script's error left out because its frame names the player's copy of the script.
- An earlier play's error read as this play's, when the console carries more than one play.
"""

from __future__ import annotations

import pytest

from adapters.remote_execution.game_dev_roblox_studio.console_errors import (
    ConsoleError,
    Window,
    first_script_error,
    place_path,
    this_plays_lines,
)
from squadops.remote_execution.models import (
    RAN_WITH_ENVIRONMENT,
    OperationStatus,
    ScriptError,
    result_defects,
)
from tests.unit.remote_execution.test_roblox_studio_play_scenario import (
    _played,
    _request,
    _runner,
)

HUD = "StarterPlayer.StarterPlayerScripts.Client.UI.Screens.HUD"
CONTROLLER = "StarterPlayer.StarterPlayerScripts.Client.Controllers.UIController"
MAIN = "StarterPlayer.StarterPlayerScripts.Client.Main"
STAGED = {HUD: "src/Client/UI/Screens/HUD.luau", CONTROLLER: "src/Client/Controllers/UIController.luau",
          MAIN: "src/Client/Main.client.luau"}  # fmt: skip
PLAYER = "Players.PlayerOne.PlayerScripts.Client"

#: Rehearsal 3's block: a property its screen object doesn't have, raised as the client starts.
REHEARSAL_3 = f"""\
The server is starting
Visible is not a valid member of ScreenGui "TA_HUD"
Stack Begin
Script '{PLAYER}.UI.Screens.HUD', Line 311 - function new
Script '{PLAYER}.Controllers.UIController', Line 444 - function Init
Script '{PLAYER}.Main', Line 3
Stack End
PlayerOne joined the game
"""

#: #3222's injected fault: the module's own block, then one follow-on per step up the chain.
MODULE_LOAD = f"""\
{PLAYER}.UI.Screens.HUD:6: __squadops_injected_fault__ the screen failed
Stack Begin
Script '{PLAYER}.UI.Screens.HUD', Line 6
Stack End
Requested module experienced an error while loading
Stack Begin
Script '{PLAYER}.Controllers.UIController', Line 31
Stack End
Requested module experienced an error while loading
Stack Begin
Script '{PLAYER}.Main', Line 34
Stack End
"""


@pytest.mark.parametrize(
    ("console", "reported"),
    [
        (REHEARSAL_3, ConsoleError(HUD, 311, 'Visible is not a valid member of ScreenGui "TA_HUD"')),
        (MODULE_LOAD, ConsoleError(
            HUD, 6, f"{PLAYER}.UI.Screens.HUD:6: __squadops_injected_fault__ the screen failed")),
    ],
    ids=["rehearsal-3", "a-module-that-failed-to-load"],
)  # fmt: skip
def test_the_first_block_raised_in_a_staged_script_is_reported(console, reported):
    assert first_script_error(console, STAGED) == reported


@pytest.mark.parametrize(
    "console",
    [
        # The module's own error was raised outside the staged tree: its follow-ons, all in
        # staged scripts, are never the error.
        MODULE_LOAD.replace(
            f"'{PLAYER}.UI.Screens.HUD', Line 6", "'CoreGui.RobloxGui.Modules.X', Line 6"
        ),
        # Raised in the command the provider's probe ran.
        "attempt to index nil with 'Name'\nStack Begin\nScript 'AssistantCommand', Line 2\nStack End\n",
        # An engine or network error carries no stack.
        "HTTP 403 (Forbidden)\nRequested module experienced an error while loading\n",
        # A block that ends before any frame.
        "Something failed\nStack Begin\nStack End\n",
        # The engine's warning for a wait that may never end, with a staged frame: a warning.
        "Infinite yield possible on 'Players.PlayerOne.PlayerGui:WaitForChild(\"HUD\")'\nStack Begin\n"
        f"Script '{PLAYER}.Main', Line 7\nStack End\n",
        # A stack whose frame is a script the request didn't stage.
        f"boom\nStack Begin\nScript '{PLAYER}.Vendor.Lib', Line 9\nStack End\n",
        "",
    ],
    ids=[
        "follow-ons-of-an-unstaged-fault",
        "the-probe",
        "no-stack",
        "no-frame",
        "an-infinite-yield",
        "unstaged",
        "empty",
    ],
)
def test_what_isnt_a_staged_scripts_own_error_is_never_reported(console):
    assert first_script_error(console, STAGED) is None


def test_a_later_staged_block_is_reported_when_an_earlier_one_isnt_a_staged_scripts():
    console = (
        "Studio said\nStack Begin\nScript 'AssistantCommand', Line 1\nStack End\n" + REHEARSAL_3
    )

    assert first_script_error(console, STAGED).script == HUD


@pytest.mark.parametrize(
    ("script", "placed"),
    [
        (f"{PLAYER}.Main", MAIN),
        ("ServerScriptService.Server.Main", "ServerScriptService.Server.Main"),
        (
            "ReplicatedStorage.Shared.Modules.SalePricing",
            "ReplicatedStorage.Shared.Modules.SalePricing",
        ),
        # Only the player's copy is read back: a path that merely mentions PlayerScripts isn't.
        (
            "ServerScriptService.Players.X.PlayerScripts.Y",
            "ServerScriptService.Players.X.PlayerScripts.Y",
        ),
    ],
)
def test_a_client_scripts_player_copy_is_read_as_the_place_holds_it(script, placed):
    assert place_path(script) == placed


@pytest.mark.parametrize(
    ("before", "early", "after", "this_play", "kind"),
    [
        # As read on the Mac: Studio cleared the console when play started.
        ("edit\nlines", "start\n", "start\nmore\n", ["start", "more"], "cleared"),
        # Cleared, and nothing written yet when it was read just after the start.
        ("edit\nlines", "", "start\nmore\n", ["start", "more"], "cleared"),
        # Not cleared: the console appended this play's lines to what it held.
        ("edit\n", "edit\nstart\n", "edit\nstart\nmore\n", ["start", "more"], "appended"),
        # Nothing before, and the console begins with the play.
        ("", "start\n", "start\nmore\n", ["start", "more"], "appended"),
    ],
    ids=["cleared-at-start", "cleared-and-empty-when-read", "appended", "nothing-before"],
)
def test_this_plays_lines_are_read_by_exact_prefixes(before, early, after, this_play, kind):
    assert this_plays_lines(before, early, after) == Window(kind, tuple(this_play))


@pytest.mark.parametrize(
    ("before", "early", "after"),
    [
        # The read after the start came before Studio cleared it, then the clear: the final
        # read no longer starts with what was there before, so whose lines are whose is unknown.
        ("edit\n", "edit\n", "start\nmore\n"),
        # Cleared at start, then rolled past the play's start (the tool's read is capped).
        ("edit\n", "start\n", "later\nlines\n"),
        # Not cleared, then rolled past what was there before.
        ("edit\n", "edit\nstart\n", "dit\nstart\nmore\n"),
    ],
    ids=["cleared-after-the-early-read", "rolled-after-a-clear", "rolled-without-one"],
)
def test_a_window_that_cant_be_established_is_none_never_everything(before, early, after):
    """The Spark lane's hardening: reading the whole console here could put an earlier play's
    error on this one, and on a baseline lose one that scrolled out."""
    assert this_plays_lines(before, early, after) == Window("unestablished", None)


# --- the provider's half, at the runner a worker calls (``RobloxStudioRunner.run``) -------------

#: The server script the stand-in's request stages, and Studio's name for it.
STAGED_MAIN, SERVER_MAIN = "src/Server/Main.server.luau", "ServerScriptService.Server.Main"
RAISED = (
    "ServerScriptService.Server.Main:4: attempt to index nil with 'Gold' for PlayerOne\n"
    "Stack Begin\n"
    f"Script '{SERVER_MAIN}', Line 4 - function award\n"
    "Stack End\n"
)


async def test_a_play_whose_console_names_a_staged_scripts_error_reports_it_as_the_file(tmp_path):
    """Studio cleared its console at play start, as it does: the edit-mode log is never read as
    this play's. Bugs caught: the error reported as Studio's name for the script and not the
    staged file core compares with the candidate's change; the player's name left in it; an
    earlier play's error in the edit-mode log reported as this one's."""
    world = _played(
        tmp_path,
        console_edit="an earlier play's error\nStack Begin\n"
        f"Script '{SERVER_MAIN}', Line 9\nStack End\n",  # fmt: skip
        console="PlayerOne joined the game\n" + RAISED,
    )
    asked = _request()

    result = await _runner(world).run(asked)

    assert result.status is OperationStatus.COMPLETED, result.reason
    assert result.script_errors == (
        ScriptError(STAGED_MAIN, 4, "ServerScriptService.Server.Main:4: attempt to index nil with "
                    "'Gold' for @player"),
    )  # fmt: skip
    assert result.ran_with["console_window"] == "cleared"
    assert len(result.ran_with[RAN_WITH_ENVIRONMENT]) == 16
    assert result_defects(asked, result) == []


async def test_a_play_with_no_staged_error_names_none_and_still_names_its_environment(tmp_path):
    """The baseline's case: condition 5 reads its empty list as a provider that looked."""
    world = _played(tmp_path, console_edit="edit-mode lines\n", console="PlayerOne joined\n")

    first = await _runner(world).run(_request())
    second = await _runner(world).run(_request())

    assert (first.script_errors, second.script_errors) == ((), ())
    # Two plays on one pinned place, one qualified Studio and one harness share an environment.
    assert first.ran_with[RAN_WITH_ENVIRONMENT] == second.ran_with[RAN_WITH_ENVIRONMENT]


async def test_an_error_raised_outside_the_staged_tree_is_never_reported(tmp_path):
    console = RAISED.replace(f"'{SERVER_MAIN}'", "'CoreGui.RobloxGui.Modules.Chat'")
    world = _played(tmp_path, console_edit="", console=console)

    result = await _runner(world).run(_request())

    assert (result.status, result.script_errors) == (OperationStatus.COMPLETED, ())


async def test_a_console_that_rolled_past_the_plays_start_names_no_error_and_no_environment(
    tmp_path,
):
    """The Spark lane's hardening: a play whose lines can't be told from an earlier play's names
    neither, so condition 2 fails for it on either side and nothing is attributed."""
    world = _played(tmp_path, console_edit="edit-mode lines\n",
                    console_reads_in_play=["the play began\n", "rolled past it\n" + RAISED])  # fmt: skip

    result = await _runner(world).run(_request())

    assert result.status is OperationStatus.COMPLETED, result.reason
    assert result.script_errors == ()
    assert RAN_WITH_ENVIRONMENT not in result.ran_with
    assert result.ran_with["console_window"] == "unestablished"


async def test_the_providers_readings_satisfy_the_six_conditions_for_an_attributable_fault(
    tmp_path, monkeypatch
):
    """R5.32 end to end over this provider: a baseline play and a candidate play whose setup
    failed with an error in the file it changed, both read as core keeps them
    (``records_document``), with ``served_by`` as the registry stamps it. Bug caught: a provider
    half that names the error and the environment in some shape the six conditions don't read,
    so no Studio play could ever be attributed."""
    from adapters.remote_execution.game_dev_roblox_studio import play
    from squadops.remote_execution.models import ReadingSide, records_document
    from squadops.remote_execution.setup_attribution import attribute
    from tests.unit.remote_execution.test_roblox_studio_play_scenario import (
        PLAY_BUTTON,
        PLAYING,
    )

    monkeypatch.setattr(play, "READY_SECONDS", 0.5)
    asked = _request()
    for side in ("baseline", "candidate"):
        (tmp_path / side).mkdir()
    baseline_world = _played(tmp_path / "baseline", console_edit="", console="PlayerOne joined\n")
    candidate_world = _played(
        tmp_path / "candidate",
        console_edit="",
        console=RAISED,
        play={**PLAYING, "client": {**PLAYING["client"], PLAY_BUTTON: {"gui": {"visible": False}}}},
    )

    def reading(result, side):
        document = records_document(asked, result, side, not_staged=())
        document["ran_with"] = {**document["ran_with"], "served_by": "macbook"}
        return document

    baseline = reading(await _runner(baseline_world).run(asked), ReadingSide.BASELINE)
    candidate = reading(await _runner(candidate_world).run(asked), ReadingSide.CANDIDATE)
    attribution = attribute(candidate, baseline, changed={STAGED_MAIN}, in_footprint=lambda _: True)

    assert {r.condition.value: r.holds for r in attribution.readings} == dict.fromkeys(
        (
            "baseline_setup_met",
            "same_environment",
            "error_in_changed_footprint_file",
            "error_before_setup_stopped",
            "error_absent_from_baseline",
            "no_environment_refusal",
        ),
        True,
    )
    assert attribution.attributed is True
    assert [e.path for e in attribution.errors] == [STAGED_MAIN]
