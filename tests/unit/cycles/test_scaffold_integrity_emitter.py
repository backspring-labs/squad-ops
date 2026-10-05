"""#1990: the executor and the correction runner emit a scaffold-integrity enforcement through
one emitter, each on its own bus.

What bugs would these catch? The two copies differed only in the bus attribute's name and the
log prefix, which is exactly where a merged copy goes wrong: the runner's events sent to an
attribute it does not have (an ``AttributeError`` swallowed as a failed emit, so the event is
lost), or the repair path's log line losing the words that tell it from storage's.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from adapters.cycles.correction_runner import CorrectionRunner
from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
from squadops.cycles.scaffold_integrity_evidence import emit_enforcement
from squadops.events.types import EventType


def _record():
    return SimpleNamespace(
        to_dict=lambda: {"kind": "frozen_path_emission", "path": "backend/main.py"},
        normalized_path="backend/main.py",
        attempted_path="./backend/main.py",
        bound_run_id="run_1",
    )


@pytest.mark.parametrize(
    ("owner", "bus_attr", "prefix"),
    [
        (DispatchedFlowExecutor, "_cycle_event_bus", "SIP-0100 scaffold_integrity: "),
        (CorrectionRunner, "_event_bus", "SIP-0100 scaffold_integrity (repair path): "),
    ],
    ids=["executor", "correction-runner"],
)
def test_each_owner_emits_on_its_own_bus_with_its_own_prefix(owner, bus_attr, prefix, caplog):
    """Entered at each owner's ``_emit_scaffold_integrity_evidence``, the method its storage
    path and its repair path call."""
    bus = MagicMock()
    owner_self = SimpleNamespace(**{bus_attr: bus})

    with caplog.at_level(logging.WARNING):
        owner._emit_scaffold_integrity_evidence(
            owner_self, _record(), SimpleNamespace(cycle_id="cyc_1")
        )

    bus.emit.assert_called_once_with(
        EventType.ARTIFACT_OWNERSHIP_ENFORCED,
        entity_type="artifact",
        entity_id="backend/main.py",
        context={"cycle_id": "cyc_1", "run_id": "run_1"},
        payload={"kind": "frozen_path_emission", "path": "backend/main.py"},
    )
    assert prefix + "{'kind': 'frozen_path_emission'" in caplog.text


def test_a_bus_that_fails_never_breaks_the_caller(caplog):
    bus = MagicMock()
    bus.emit.side_effect = RuntimeError("bus down")

    with caplog.at_level(logging.WARNING):
        emit_enforcement(bus, _record(), "cyc_1")

    assert "SIP-0100 scaffold_integrity: " in caplog.text
