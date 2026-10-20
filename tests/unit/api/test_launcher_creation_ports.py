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

import pytest

from squadops.api.routes.cycles.cycles import CreationPorts
from squadops.api.runtime import main as runtime_main


def _creation_ports_calls(source: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "CreationPorts"
    ]


def _gaps(call: ast.Call) -> set[str]:
    """The ports the call leaves out, or passes as a literal (``{}``, ``None``), which is the
    same port left empty."""
    passed = {k.arg: k.value for k in call.keywords}
    literal = (ast.Constant, ast.Dict, ast.List, ast.Tuple, ast.Set)
    return {f.name for f in dataclasses.fields(CreationPorts)
            if f.name not in passed or isinstance(passed[f.name], literal)}  # fmt: skip


def test_the_launcher_is_given_every_port_a_cycle_is_created_with():
    [call] = _creation_ports_calls(Path(runtime_main.__file__).read_text(encoding="utf-8"))

    assert _gaps(call) == set()


@pytest.mark.parametrize(
    ("source", "gap"),
    [
        ("CreationPorts(project_registry=a, squad_profile=b)", "memory_records"),
        ("CreationPorts(project_registry=a, reference_resolvers={})", "reference_resolvers"),
    ],
    ids=["a-port-left-out", "a-port-passed-empty"],
)
def test_a_call_leaving_a_port_out_or_empty_is_told_apart(source, gap):
    """The edge: the reading this guard relies on. The second read of the task part: the
    composition root passing ``reference_resolvers={}`` passed a guard that read names only."""
    [call] = _creation_ports_calls(source)

    assert gap in _gaps(call)
