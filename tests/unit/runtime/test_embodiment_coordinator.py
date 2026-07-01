"""Unit tests for SIP-0090 Phase 1 EmbodimentCoordinator (slice 4).

This is the model-level "transitions cleanly" acceptance (§13). Each test answers:
what bug would it catch?

Bug classes guarded:
- an illegal transition being persisted / evented instead of rejected (§5.2);
- a rejection still writing to the store or emitting an event (partial application);
- a second live embodiment for one agent slipping past the single-active rule (§5.5);
- the single-active guard false-positiving on an active→active move (e.g. attached→
  desynced) and blocking a legitimate transition;
- the coordinator coupling to a concrete adapter early (D26).
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import squadops.runtime.embodiment_coordinator as coordinator_module
from squadops.ports.runtime.embodiment import EmbodimentStatePort
from squadops.ports.runtime.event_publisher import RuntimeEventPublisher
from squadops.runtime import events, reasons
from squadops.runtime.embodiment import Embodiment
from squadops.runtime.embodiment_coordinator import EmbodimentCoordinator

pytestmark = pytest.mark.asyncio


def _embodiment(
    embodiment_id="emb-1", agent_id="max", attachment_state="unattached", health="healthy"
):
    return Embodiment(
        embodiment_id=embodiment_id,
        agent_id=agent_id,
        embodiment_type="discord",
        platform="discord.com",
        attachment_state=attachment_state,
        health=health,
    )


class _FakeStatePort(EmbodimentStatePort):
    """Records transition writes; returns a configurable active embodiment."""

    def __init__(self, active: Embodiment | None = None) -> None:
        self._active = active
        self.transitions: list[tuple[str, str]] = []
        self.get_active_calls = 0

    async def create_embodiment(self, embodiment, *, conn=None):
        return embodiment

    async def get_embodiment(self, embodiment_id):
        return None

    async def get_active_embodiment(self, agent_id):
        self.get_active_calls += 1
        return self._active

    async def list_for_agent(self, agent_id):
        return ()

    async def transition_state(self, embodiment_id, target_state, *, conn=None):
        self.transitions.append((embodiment_id, target_state))
        return _embodiment(embodiment_id=embodiment_id, attachment_state=target_state)

    async def update_health(self, embodiment_id, health, *, conn=None):  # pragma: no cover
        raise NotImplementedError

    async def update_location(self, embodiment_id, location_ref, *, conn=None):  # pragma: no cover
        raise NotImplementedError


class _FakePublisher(RuntimeEventPublisher):
    def __init__(self) -> None:
        self.emitted: list[tuple[str, str, str, dict | None]] = []

    def emit(self, event_name, *, agent_id, reason_code, payload=None):
        self.emitted.append((event_name, agent_id, reason_code, payload))


# ── Applied transitions ──────────────────────────────────────────────────────


async def test_valid_transition_persists_and_emits_target_event():
    port, pub = _FakeStatePort(), _FakePublisher()
    coord = EmbodimentCoordinator(port, events_publisher=pub)

    outcome = await coord.request_transition(
        _embodiment(attachment_state="unattached"),
        "attaching",
        reasons.EMBODIMENT_ATTACH_REQUESTED,
    )

    assert outcome.applied is True
    assert outcome.event_name == events.EMBODIMENT_ATTACHING
    assert port.transitions == [("emb-1", "attaching")]
    assert pub.emitted == [
        (
            events.EMBODIMENT_ATTACHING,
            "max",
            reasons.EMBODIMENT_ATTACH_REQUESTED,
            {"embodiment_id": "emb-1"},
        )
    ]


async def test_attach_completes_when_no_other_active_embodiment():
    port = _FakeStatePort(active=None)
    coord = EmbodimentCoordinator(port)

    outcome = await coord.request_transition(
        _embodiment(attachment_state="attaching"), "attached", reasons.EMBODIMENT_ATTACH_SUCCEEDED
    )

    assert outcome.applied is True
    assert outcome.event_name == events.EMBODIMENT_ATTACHED
    assert port.get_active_calls == 1  # the single-active guard ran


async def test_applies_without_an_events_publisher():
    """Emission is best-effort: no publisher wired must not break the transition."""
    port = _FakeStatePort()
    outcome = await EmbodimentCoordinator(port).request_transition(
        _embodiment(attachment_state="attached"), "desynced", reasons.EMBODIMENT_DESYNC_DETECTED
    )
    assert outcome.applied is True and port.transitions == [("emb-1", "desynced")]


# ── Rejections write nothing and emit nothing ────────────────────────────────


async def test_illegal_transition_is_rejected_without_write_or_event():
    port, pub = _FakeStatePort(), _FakePublisher()
    coord = EmbodimentCoordinator(port, events_publisher=pub)

    outcome = await coord.request_transition(
        _embodiment(attachment_state="unattached"),  # unattached→attached skips `attaching`
        "attached",
        reasons.EMBODIMENT_ATTACH_SUCCEEDED,
    )

    assert outcome.applied is False
    assert outcome.rejected_reason == reasons.INVALID_ATTACHMENT_TRANSITION
    assert port.transitions == [] and pub.emitted == []


async def test_missing_reason_code_is_rejected():
    port = _FakeStatePort()
    outcome = await EmbodimentCoordinator(port).request_transition(
        _embodiment(attachment_state="unattached"), "attaching", ""
    )
    assert outcome.applied is False
    assert outcome.rejected_reason == reasons.MISSING_REASON_CODE
    assert port.transitions == []


# ── Single-active rule (§5.5) ────────────────────────────────────────────────


async def test_second_live_embodiment_is_rejected():
    other_active = _embodiment(embodiment_id="emb-2", agent_id="max", attachment_state="attached")
    port, pub = _FakeStatePort(active=other_active), _FakePublisher()
    coord = EmbodimentCoordinator(port, events_publisher=pub)

    outcome = await coord.request_transition(
        _embodiment(embodiment_id="emb-1", attachment_state="attaching"),
        "attached",
        reasons.EMBODIMENT_ATTACH_SUCCEEDED,
    )

    assert outcome.applied is False
    assert outcome.rejected_reason == reasons.EMBODIMENT_ALREADY_ACTIVE
    assert port.transitions == [] and pub.emitted == []


async def test_same_embodiment_already_active_does_not_block_itself():
    """The agent's active embodiment being *this* one must not reject its own move."""
    self_active = _embodiment(embodiment_id="emb-1", agent_id="max", attachment_state="attached")
    port = _FakeStatePort(active=self_active)
    outcome = await EmbodimentCoordinator(port).request_transition(
        _embodiment(embodiment_id="emb-1", attachment_state="attaching"),
        "attached",
        reasons.EMBODIMENT_ATTACH_SUCCEEDED,
    )
    assert outcome.applied is True


async def test_active_to_active_move_skips_the_single_active_check():
    """attached→desynced keeps the *same* live embodiment — it must not consult (nor
    be blocked by) another agent embodiment's active status."""
    other_active = _embodiment(embodiment_id="emb-2", agent_id="max", attachment_state="attached")
    port = _FakeStatePort(active=other_active)
    outcome = await EmbodimentCoordinator(port).request_transition(
        _embodiment(embodiment_id="emb-1", attachment_state="attached"),
        "desynced",
        reasons.EMBODIMENT_DESYNC_DETECTED,
    )
    assert outcome.applied is True
    assert port.get_active_calls == 0  # guard skipped: from-state is already active


# ── D26: substrate stays adapter-free (plan §4.5 named acceptance check) ──────


def test_coordinator_imports_no_concrete_adapter():
    src = pathlib.Path(coordinator_module.__file__).read_text()
    imported: list[str] = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)

    banned = ("adapters", "discord", "browser", "playwright", "minecraft")
    assert not any(any(b in m for b in banned) for m in imported), imported
    # only runtime models/ports/events/reasons + stdlib
    allowed_prefixes = (
        "squadops.runtime",
        "squadops.ports.runtime",
        "dataclasses",
        "typing",
        "__future__",
    )
    for m in imported:
        assert m == "" or m.startswith(allowed_prefixes), f"unexpected import: {m}"
