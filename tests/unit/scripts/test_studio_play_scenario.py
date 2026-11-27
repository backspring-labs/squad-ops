"""#3243 (the 2.9 plan's item 10): a hand play's log carries ``ran_with``.

Entered at ``scripts/dev/studio_play_scenario.py``'s ``main``, as a person runs it, with a stub
for the worker's ``create_runner`` and the script's own output read back.

What bugs would these catch?
- The output dropping the result's ``ran_with``, so a hand play's log names neither the Studio
  it ran on nor the qualification it was held to. The 32 hand plays of 2026-11-20 had that
  gap, and their identity had to be read another way at the 2.8.1 cut.
- A log that prints the two identities and leaves the reader to compare them by eye, so a play
  on a Studio other than the qualified one reads the same as one on it.
- A result with no ``ran_with`` printed as nothing at all, which reads as "the script doesn't
  print it" rather than "the result had none".
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from squadops.remote_execution.models import OperationStatus, RemoteOperationResult

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "studio_play_scenario.py"
_spec = importlib.util.spec_from_file_location("studio_play_scenario", _SCRIPT)
script = importlib.util.module_from_spec(_spec)
sys.modules["studio_play_scenario"] = script
_spec.loader.exec_module(script)

#: A worker's result's ``ran_with``, as ``RobloxStudioRunner.run`` builds it for a completed play.
RAN_WITH = {
    "roblox-studio": "2",
    "reader": "roblox-studio/1",
    "place_baseline": "354636ad417cda41",
    "source_revision": "65dd3c6d8b9ce286b0e4a5873b3eb9d2271d64f0725f5b1ccb46ad279c994b52",
    "harness.sync": "0123456789abcdef",
    "play_session": "play-7f3a",
    "qualified.studio_version": "0.748.0.7481526",
    "qualified.studio_channel": "production",
    "qualified.studio_tools": "41:8f661f40cfd0",
    "played.studio_version": "0.748.0.7481526",
    "played.studio_channel": "production",
    "played.studio_tools": "41:8f661f40cfd0",
    "qualified_by": "16a94b79aa29ce31",
}

SCENARIO = {
    "schema": "squadops.scenario/1",
    "scenario_id": "qualify-screen-visible",
    "reader": "roblox-studio/1",
    "setup": [],
    "steps": [],
    "assertions": [
        {
            "id": "hud-enabled",
            "observe": {
                "kind": "property",
                "path": "@player.PlayerGui.TA_HUD",
                "name": "Enabled",
                "context": "client",
            },
            "expect": {"op": "equals", "value": True},
        }
    ],
    "named_assertion": "hud-enabled",
}


class _Runner:
    def __init__(self, result: RemoteOperationResult) -> None:
        self.result = result
        self.requests = []

    async def run(self, request):
        self.requests.append(request)
        return self.result


def _play(tmp_path, monkeypatch, capsys, result: RemoteOperationResult) -> tuple[int, str, _Runner]:
    repo = tmp_path / "repo"
    (repo / "src" / "Shared").mkdir(parents=True)
    (repo / "src" / "Shared" / "Rules.luau").write_text("return {}\n")
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps(SCENARIO))
    runner = _Runner(result)
    monkeypatch.setattr(script.worker, "create_runner", lambda settings: runner)
    monkeypatch.setattr(sys, "argv", ["studio_play_scenario.py", str(repo), str(scenario)])

    code = script.main()

    return code, capsys.readouterr().out, runner


def _result(status=OperationStatus.COMPLETED, ran_with=None, reason="") -> RemoteOperationResult:
    return RemoteOperationResult(
        status=status,
        reason=reason,
        ran_with=RAN_WITH if ran_with is None else ran_with,
        dispatch_id="by-hand",
    )


def test_a_hand_plays_output_names_both_identities_and_the_qualification(
    tmp_path, monkeypatch, capsys
):
    code, out, runner = _play(tmp_path, monkeypatch, capsys, _result())

    assert code == 0
    assert len(runner.requests) == 1
    for key, value in RAN_WITH.items():
        assert f"  {key}: {value}" in out, key
    assert "played on the qualified Studio" in out


def test_a_play_on_a_studio_other_than_the_qualified_one_says_which_parts_differ(
    tmp_path, monkeypatch, capsys
):
    """A same-version Studio whose tool list moved: the play the worker would refuse, run by a
    stub that doesn't refuse it, so only the log's reading is under test."""
    moved = {**RAN_WITH, "played.studio_tools": "43:aa11bb22cc33"}

    _code, out, _runner = _play(tmp_path, monkeypatch, capsys, _result(ran_with=moved))

    assert "played on a Studio other than the qualified one: studio_tools" in out
    assert "played on the qualified Studio" not in out


@pytest.mark.parametrize(
    ("ran_with", "says"),
    [
        ({}, "ran_with: none recorded"),
        (
            {"roblox-studio": "2", "reader": "roblox-studio/1"},
            "no Studio identity recorded: the result names neither the qualified nor the played",
        ),
    ],
    ids=["a-result-with-no-ran-with", "a-refusal-before-studio-was-read"],
)
def test_a_result_without_the_identities_says_so(tmp_path, monkeypatch, capsys, ran_with, says):
    result = _result(OperationStatus.NOT_EXECUTED, ran_with=ran_with, reason="Studio is behind")

    code, out, _runner = _play(tmp_path, monkeypatch, capsys, result)

    assert code == 1
    assert says in out
