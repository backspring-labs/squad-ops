"""Unit tests for SIP-0090 Phase 1 embodiment model + lifecycle (slice 1a).

Each test answers: what bug would it catch?

Bug classes guarded:
- an illegal attachment shortcut (e.g. unattached→attached, attached→reconnecting,
  or any edge out of terminal `detached`) being silently permitted;
- the single-active-embodiment set (§5.5) drifting from attached/desynced/reconnecting;
- a raw credential landing in an Embodiment record (§9 security invariant);
- the failure-termination edges the plan §4.1 matrix adds to SIP §5.2 going missing.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from squadops.runtime.embodiment import (
    _ALLOWED_ATTACHMENT_TRANSITIONS,
    Embodiment,
    Location,
    is_active_attachment,
    is_allowed_attachment_transition,
    is_valid_credentials_ref,
)

ALL_STATES = ("unattached", "attaching", "attached", "desynced", "reconnecting", "detached")


def _embodiment(**overrides):
    base = dict(
        embodiment_id="emb-1",
        agent_id="max",
        embodiment_type="discord",
        platform="discord.com",
        attachment_state="unattached",
        health="healthy",
    )
    base.update(overrides)
    return Embodiment(**base)


# ── Lifecycle transitions (plan §4.1) ────────────────────────────────────────


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("unattached", "attaching"),
        ("attaching", "attached"),
        ("attaching", "detached"),  # failed attach terminates
        ("attached", "desynced"),
        ("attached", "detached"),
        ("desynced", "reconnecting"),
        ("desynced", "detached"),  # abandoned desync terminates
        ("reconnecting", "attached"),
        ("reconnecting", "detached"),  # failed reconnect terminates
    ],
)
def test_allowed_transitions_are_permitted(current, target):
    assert is_allowed_attachment_transition(current, target) is True


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("unattached", "attached"),  # never skip `attaching`
        ("attached", "reconnecting"),  # recovery only via `desynced`
        ("attached", "attaching"),  # no going backward
        ("desynced", "attached"),  # must reconnect first
        ("attaching", "desynced"),  # not live yet
        ("detached", "attaching"),  # `detached` is terminal
        ("detached", "attached"),
        ("unattached", "detached"),  # can't detach before attaching
    ],
)
def test_illegal_transitions_are_rejected(current, target):
    assert is_allowed_attachment_transition(current, target) is False


def test_detached_is_terminal():
    """No transition may leave `detached` — the embodiment record is done (Phase 1)."""
    assert not any(frm == "detached" for (frm, _to) in _ALLOWED_ATTACHMENT_TRANSITIONS)


def test_every_non_terminal_state_has_an_exit():
    """No non-terminal state is a dead end — otherwise an embodiment could get stuck."""
    with_exit = {frm for (frm, _to) in _ALLOWED_ATTACHMENT_TRANSITIONS}
    non_terminal = set(ALL_STATES) - {"detached"}
    assert non_terminal <= with_exit


# ── Single-active rule (§5.5) ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("attached", True),
        ("desynced", True),
        ("reconnecting", True),
        ("unattached", False),
        ("attaching", False),  # connecting, not yet live — must not block a re-attach
        ("detached", False),
    ],
)
def test_is_active_attachment(state, expected):
    assert is_active_attachment(state) is expected


def test_embodiment_is_active_property_tracks_state():
    assert _embodiment(attachment_state="attached").is_active is True
    assert _embodiment(attachment_state="unattached").is_active is False
    # frozen — a lifecycle move goes through replace(), and is_active follows
    detached = replace(_embodiment(attachment_state="attached"), attachment_state="detached")
    assert detached.is_active is False


# ── Credentials security invariant (§9) ──────────────────────────────────────


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        (None, True),  # no credentials
        ("secret://discord/bot-token", True),
        ("raw-bot-token", False),  # a raw secret must be rejected
        ("", False),
        ("secret:/typo", False),  # malformed scheme
    ],
)
def test_is_valid_credentials_ref(ref, expected):
    assert is_valid_credentials_ref(ref) is expected


def test_embodiment_rejects_raw_credential_at_construction():
    """A raw credential must never be storable — the record cannot be constructed."""
    with pytest.raises(ValueError, match="secret://"):
        _embodiment(credentials_ref="raw-bot-token")


def test_embodiment_accepts_secret_ref_and_none():
    assert _embodiment(credentials_ref="secret://x").credentials_ref == "secret://x"
    assert _embodiment(credentials_ref=None).credentials_ref is None


# ── Model invariants ─────────────────────────────────────────────────────────


def test_embodiment_is_frozen():
    """Frozen: mutation must go through dataclasses.replace(), not attribute set."""
    emb = _embodiment()
    with pytest.raises(FrozenInstanceError):
        emb.attachment_state = "attached"  # type: ignore[misc]


def test_location_exposes_only_opaque_fields():
    """Opacity (§5.4): Location carries a routing tag + an opaque ref, nothing parsed."""
    loc = Location(location_type="discord_channel", ref="guild/123/chan/456")
    assert (loc.location_type, loc.ref) == ("discord_channel", "guild/123/chan/456")
    # no parsed sub-fields leaked onto the model
    assert set(vars(loc)) == {"location_type", "ref"}
