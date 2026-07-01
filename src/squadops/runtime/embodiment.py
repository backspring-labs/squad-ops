"""
Embodiment domain model + lifecycle for SIP-0090 (Agent Embodiment Substrate).

Phase 1 (§13, slice 1a): the core embodiment record, its attachment lifecycle
state machine, and the opaque ``Location``. No adapter — this is pure,
migration-free substrate (plan: ``docs/plans/SIP-0090-phase-1-plan.md``).

Mirrors the SIP-0089 ``runtime/models.py`` conventions: frozen dataclasses mutated
via ``dataclasses.replace()``, module-level ``Literal`` types that mirror the DB
``CHECK`` constraints landed in 1b (D3), and an explicit transition allow-list
(like the coordinator's ``_ALLOWED_TRANSITIONS``) so a malformed transition is
rejected, not applied. Budgets live in ``runtime/budgets.py``; the state port and
``EmbodimentCoordinator`` are separate modules (plan §4.3 / §4.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

# §5.2 attachment lifecycle; §5.3 health + embodiment_type. Literals mirror the DB
# CHECK constraints landed in 1b (D3).
AttachmentState = Literal[
    "unattached", "attaching", "attached", "desynced", "reconnecting", "detached"
]
Health = Literal["healthy", "degraded", "failed"]
EmbodimentType = Literal["discord", "browser", "minecraft", "cli", "other"]

_CREDENTIALS_REF_SCHEME = "secret://"

# §5.2 lifecycle state machine, spelled out per plan §4.1 as an explicit allow-list
# of (from, to) pairs. This COMPLETES the SIP §5.2 ASCII (which draws only the happy
# path plus attached ↘ detached) by making the failure-termination edges explicit:
# a failed attach, an abandoned desync, and a failed reconnect all terminate at
# `detached`. `detached` is terminal in Phase 1 (no outgoing). Kept explicit so an
# illegal shortcut (e.g. unattached→attached, attached→reconnecting) is rejected,
# not applied.
_ALLOWED_ATTACHMENT_TRANSITIONS: frozenset[tuple[AttachmentState, AttachmentState]] = frozenset(
    {
        ("unattached", "attaching"),
        ("attaching", "attached"),
        ("attaching", "detached"),
        ("attached", "desynced"),
        ("attached", "detached"),
        ("desynced", "reconnecting"),
        ("desynced", "detached"),
        ("reconnecting", "attached"),
        ("reconnecting", "detached"),
    }
)

# The attachment states in which an embodiment counts as "live" for the single-
# active-embodiment rule (§5.5): at most one of these may exist per agent.
_ACTIVE_ATTACHMENT_STATES: frozenset[AttachmentState] = frozenset(
    {"attached", "desynced", "reconnecting"}
)


def is_allowed_attachment_transition(current: AttachmentState, target: AttachmentState) -> bool:
    """True iff ``current → target`` is a legal §5.2 attachment transition (plan §4.1)."""
    return (current, target) in _ALLOWED_ATTACHMENT_TRANSITIONS


def is_active_attachment(state: AttachmentState) -> bool:
    """True iff ``state`` counts as a live embodiment for the single-active rule (§5.5)."""
    return state in _ACTIVE_ATTACHMENT_STATES


def is_valid_credentials_ref(credentials_ref: str | None) -> bool:
    """True iff ``credentials_ref`` is absent or a ``secret://`` reference (§9).

    A raw credential must never land in an Embodiment record — only an indirection
    the SecretManager resolves at attach (1b / Phase 2). ``None`` means "no
    credentials" and is allowed.
    """
    return credentials_ref is None or credentials_ref.startswith(_CREDENTIALS_REF_SCHEME)


@dataclass(frozen=True)
class Location:
    """An **opaque** handle to where an embodiment is attached (§5.4).

    Core stores and compares ``ref`` (by equality) and routes it back to the owning
    adapter, but MUST NOT parse or branch on its contents. ``location_type`` is a
    coarse routing tag for choosing the adapter; it is *not* parsed for meaning by
    core code (no ``location_type == "discord_channel"`` branching — plan §7). This
    dataclass deliberately exposes no parsed sub-fields.
    """

    location_type: str
    ref: str


@dataclass(frozen=True)
class Embodiment:
    """A single agent↔surface attachment record (SIP-0090 §5.3).

    Frozen; mutate via ``dataclasses.replace()``. ``attachment_state`` moves only
    along the §5.2 allow-list (:func:`is_allowed_attachment_transition`); the
    :class:`EmbodimentCoordinator` (plan §4.5) owns transitions and the single-active
    rule (§5.5). ``location_ref`` is opaque (§5.4). ``credentials_ref`` is a
    ``secret://`` indirection, never a raw secret (§9) — enforced at construction so
    a raw credential can never land in a record.
    """

    embodiment_id: str
    agent_id: str
    embodiment_type: EmbodimentType
    platform: str
    attachment_state: AttachmentState
    health: Health
    capability_set: tuple[str, ...] = ()
    location_ref: str | None = None
    last_health_check_at: datetime | None = None
    credentials_ref: str | None = None

    def __post_init__(self) -> None:
        # Security invariant (§9 / hard rule "credentials via secret:// refs"): a raw
        # credential must never be storable in a record.
        if not is_valid_credentials_ref(self.credentials_ref):
            raise ValueError(
                "credentials_ref must be a `secret://` reference, never a raw credential"
            )

    @property
    def is_active(self) -> bool:
        """Whether this embodiment currently counts as live for the single-active rule (§5.5)."""
        return is_active_attachment(self.attachment_state)
