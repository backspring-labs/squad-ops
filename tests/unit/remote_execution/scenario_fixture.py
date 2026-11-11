"""One frozen scenario under the fixture's reader, and the worlds it reads (#3044 §6).

``DOOR_OPENS`` declares a player who has spawned (a precondition) and a door that opens when
its button is clicked (the named assertion). ``SHUT`` is a baseline world: the door is there
and closed, and the button isn't built yet. ``OPEN`` is a candidate's world: the door is open.
Campaign acceptance's tests (#3053) read the same three.
"""

from __future__ import annotations

import json

from adapters.remote_execution.fixture_operation_runner import VOCABULARY, WORLD_PATH
from squadops.remote_execution.models import Scenario
from squadops.remote_execution.scenario import frozen_scenario

#: Where the framework places a criterion's scenario in the tree (#3044 §2).
SCENARIO_PATH = ".squadops/scenarios/C-2.json"

DOOR_OPENS = {
    "schema": "squadops.scenario/1",
    "scenario_id": "C-2",
    "reader": "fixture/1",
    "setup": [
        {
            "action": "wait_until",
            "observe": {
                "kind": "property",
                "path": "Players.LocalPlayer.Character.Humanoid",
                "name": "Health",
                "context": "client",
            },
            "expect": {"op": "greater_than", "value": 0},
            "deadline_s": 15,
        }
    ],
    "steps": [
        {"action": "move_to", "point": [12, 3, -40], "deadline_s": 8},
        {"action": "click_gui", "path": "PlayerGui.DoorPanel.OpenButton"},
    ],
    "assertions": [
        {
            "id": "spawned",
            "observe": {
                "kind": "property",
                "path": "Players.LocalPlayer.Character.Humanoid",
                "name": "Health",
                "context": "client",
            },
            "expect": {"op": "greater_than", "value": 0},
        },
        {
            "id": "door-open",
            "observe": {
                "kind": "property",
                "path": "Workspace.Door",
                "name": "CanCollide",
                "context": "server",
            },
            "expect": {"op": "equals", "value": False},
        },
    ],
    "named_assertion": "door-open",
}

_SPAWNED = {"Players.LocalPlayer.Character.Humanoid": {"properties": {"Health": 100}}}
SHUT = {"client": _SPAWNED, "server": {"Workspace.Door": {"properties": {"CanCollide": True}}}}
OPEN = {
    "client": {**_SPAWNED, "PlayerGui.DoorPanel.OpenButton": {"gui": {"visible": True}}},
    "server": {"Workspace.Door": {"properties": {"CanCollide": False}}},
}


def door_opens() -> Scenario:
    """``DOOR_OPENS``, frozen."""
    return frozen_scenario(DOOR_OPENS, VOCABULARY)


def tree(world: dict, **files: str) -> dict[str, str]:
    """A staged tree: the scenario at its path, the world the fixture reads, and ``files``."""
    return {SCENARIO_PATH: door_opens().document, WORLD_PATH: json.dumps(world), **files}
