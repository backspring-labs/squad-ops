"""#377: ``RunStatus`` is the run's only status vocabulary inward of the Prefect adapter.

The leak: ``terminal_status`` carried Prefect's ``State`` type strings (``"COMPLETED"``,
``"FAILED"`` …) through ``TerminalOutcome``, ``finalize`` and into ``run_report_builder`` —
domain presentation reasoning in a vendor's words. It coincided with
``RunStatus.value.upper()`` only for the terminal subset: ``QUEUED.upper()`` is not a Prefect
state (Prefect says SCHEDULED), so the first non-terminal status through that path would
have sent an invalid state. The port now takes ``RunStatus``; the adapter owns the
translation, total over the enum (``test_prefect_workflow_tracker``).

This guard keeps the retired identifier and the Prefect-shaped port signature from returning.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_ROOTS = (_REPO / "src" / "squadops", _REPO / "adapters")
_RETIRED = "terminal_status"


def _identifier_hits(path: Path) -> list[int]:
    """Lines where ``terminal_status`` is an identifier — a name, an argument, an attribute
    or a keyword — not prose. The WORKLOAD_COMPLETED payload's ``"terminal_status"`` key is a
    string carrying a lowercase ``RunStatus`` value, the domain's own words, and is not the
    thing retired; docstrings that name the history are not either."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == _RETIRED:
            hits.append(node.lineno)
        elif isinstance(node, ast.arg) and node.arg == _RETIRED:
            hits.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr == _RETIRED:
            hits.append(node.lineno)
        elif isinstance(node, ast.keyword) and node.arg == _RETIRED:
            hits.append(node.value.lineno)
    return sorted(set(hits))


def test_the_identifier_that_carried_prefects_vocabulary_is_retired():
    """Bug caught: a new ``terminal_status`` parameter, field, attribute or keyword — the
    name under which the uppercase strings travelled — reintroduced in the domain or the
    adapters."""
    hits = []
    for root in _ROOTS:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for line in _identifier_hits(path):
                hits.append(f"{path.relative_to(_REPO)}:{line}")
    assert not hits, "terminal_status is retired (#377); carry RunStatus:\n  " + "\n  ".join(hits)


def test_the_tracker_port_speaks_run_status_not_prefect_state():
    """The boundary: the port's parameter is the domain enum, and the Prefect-shaped
    ``state_type``/``state_name`` pair is nowhere on it."""
    from squadops.ports.cycles.workflow_tracker import WorkflowTrackerPort

    params = inspect.signature(WorkflowTrackerPort.set_flow_run_state).parameters
    assert "run_status" in params
    assert "state_type" not in params and "state_name" not in params


def test_terminal_outcome_carries_the_enum_only():
    """``TerminalOutcome`` held ``terminal_status: str`` beside ``run_status: RunStatus`` —
    a Prefect-shaped shadow of a field it already had."""
    import dataclasses

    from adapters.cycles.run_completion import TerminalOutcome

    names = {f.name for f in dataclasses.fields(TerminalOutcome)}
    assert "run_status" in names and "terminal_status" not in names
