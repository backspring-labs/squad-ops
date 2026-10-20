"""A campaign's launches create cycles with every port the cycle-create route does (SIP-0109 §12b).

The route gathers ``CreationPorts`` from the request's app (``CreationPorts.of_request``); the launcher
is handed its own, built once in the composition root. What bug would this catch? A port added to
``CreationPorts`` and wired for the route only, so a campaign's cycles are created without it, and
nothing fails until a campaign meets the case. #2178's resolvers were the instance: dropping them
from the composition root passed every other test, and a campaign cycle's task instruction naming
``@current`` would then have been refused for want of a resolver the route had.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

from squadops.api.routes.cycles.cycles import CreationPorts
from squadops.api.runtime import main as runtime_main


def _creation_ports_calls(source: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "CreationPorts"
    ]


def test_the_launcher_is_given_every_port_a_cycle_is_created_with():
    [call] = _creation_ports_calls(Path(runtime_main.__file__).read_text(encoding="utf-8"))

    assert {k.arg for k in call.keywords} == {f.name for f in dataclasses.fields(CreationPorts)}


def test_a_call_leaving_a_port_out_is_told_apart():
    """The edge: the reading this guard relies on, against a call that leaves a port out."""
    [call] = _creation_ports_calls("CreationPorts(project_registry=a, squad_profile=b)")

    assert {k.arg for k in call.keywords} != {f.name for f in dataclasses.fields(CreationPorts)}
