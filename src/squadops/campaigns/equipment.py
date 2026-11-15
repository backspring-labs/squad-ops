"""A Campaign's pinned equipment (SIP-0116 §10, phase 5, #3037).

**The equipment** is what a Campaign's work was assigned, read from a cycle's skillset record: the
base set's version, the requirements, the assignment (each requirement's agent, and the skillset's
id, version and digest), the offered contracts, and each kept skill's digest. The rest of the
record (the squad's roster hash, which covers models and unassigned agents, and the development
profile's fingerprint) changes no equipment, so it isn't compared.

**The pin** is the equipment of the Campaign's first launched cycle, written to its control log
(``EQUIPMENT_PINNED``). Each later launch compares its own record's equipment with the pin:
- equal, the launch proceeds, and its skills are the pinned ones, digest for digest;
- different, the launch is refused (``EQUIPMENT_CHANGED``, each changed part named), and the
  Campaign escalates as for any refused launch.

**It continues only through the owner's recorded transition** (``EQUIPMENT_TRANSITION``), which
accepts exactly the equipment the refused launch found, by its digest. A catalog that moves again
before the retry is refused again. Every row is records-only, so earlier cycles' records, frozen
verifier bundles and the lesson snapshot are untouched (SIP-0110's rebind is the precedent).

Pure: the launch service and the transition route read and write the log.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from squadops.campaigns.models import (
    Campaign,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
)
from squadops.core.hashing import canonical_sha256

#: The refusal code a launch whose equipment changed is escalated with.
EQUIPMENT_CHANGED_CODE = "SKILLSET_EQUIPMENT_CHANGED"

#: The record's parts that are the equipment, in the order a difference is named.
EQUIPMENT_PARTS = ("base_set", "requirements", "assignment", "offered", "content")


class EquipmentUnreadable(ValueError):
    """A cycle's record, or the Campaign's pin, can't be read as equipment."""


def equipment(record: Mapping[str, Any] | None) -> dict[str, Any]:
    """The equipment in ``record``, or :class:`EquipmentUnreadable` naming the missing part. A
    cycle created since SIP-0116 phase 1 always has a record; one without is never pinned as
    if it had no equipment."""
    if not isinstance(record, Mapping):
        raise EquipmentUnreadable("the cycle has no skillset record to pin or compare")
    missing = [part for part in EQUIPMENT_PARTS if part not in record]
    if missing:
        raise EquipmentUnreadable(f"the cycle's skillset record has no {', '.join(missing)}")
    base_set = record["base_set"]
    return {
        "base_set": base_set.get("version") if isinstance(base_set, Mapping) else base_set,
        "requirements": record["requirements"],
        "assignment": record["assignment"],
        "offered": record["offered"],
        "content": record["content"],
    }


def equipment_digest(held: Mapping[str, Any]) -> str:
    return "sha256:" + canonical_sha256(dict(held))


def changed_parts(pinned: Mapping[str, Any], found: Mapping[str, Any]) -> list[str]:
    """Each part of the equipment that differs, named with what it was and what it is."""
    changes: list[str] = []
    for part in EQUIPMENT_PARTS:
        if pinned.get(part) == found.get(part):
            continue
        if part == "assignment":
            changes += _assignment_changes(pinned.get(part) or [], found.get(part) or [])
        elif part == "content":
            changes += _content_changes(pinned.get(part) or [], found.get(part) or [])
        elif part == "base_set":
            changes.append(f"the base set was {pinned.get(part)} and is {found.get(part)}")
        else:
            changes.append(f"the {part} differ from the pinned ones")
    return changes


def _assignment_changes(pinned: Iterable[Mapping], found: Iterable[Mapping]) -> list[str]:
    def by_role(rows: Iterable[Mapping]) -> dict[str, Mapping]:
        return {str(r.get("role")): r for r in rows}

    def said(row: Mapping | None) -> str:
        if row is None:
            return "nothing"
        digest = str(row.get("digest") or "")
        return (
            f"{row.get('skillset')} {row.get('version')} (digest {digest[:12]}…) "
            f"from {row.get('agent_id')}"
        )

    before, after = by_role(pinned), by_role(found)
    return [
        f"assignment {role}: {said(before.get(role))} is now {said(after.get(role))}"
        for role in sorted(set(before) | set(after))
        if before.get(role) != after.get(role)
    ]


def _content_changes(pinned: Iterable[Mapping], found: Iterable[Mapping]) -> list[str]:
    def by_skill(rows: Iterable[Mapping]) -> dict[str, str]:
        return {f"{r.get('skillset')}/{r.get('skill')}": str(r.get("digest")) for r in rows}

    before, after = by_skill(pinned), by_skill(found)
    return [
        f"skill {name}: "
        + (
            "added"
            if name not in before
            else "removed"
            if name not in after
            else f"digest {before[name][:12]}… is now {after[name][:12]}…"
        )
        for name in sorted(set(before) | set(after))
        if before.get(name) != after.get(name)
    ]


@dataclass(frozen=True)
class Pin:
    """The equipment the Campaign's launches are held to, and the row that set it."""

    digest: str
    held: Mapping[str, Any]
    set_by: ControlOperation


def current_pin(log: Iterable[ControlLogEntry]) -> Pin | None:
    """The latest pin or transition on the log, or ``None`` before the first launch."""
    pin: Pin | None = None
    for entry in _applied(log):
        if entry.operation is ControlOperation.EQUIPMENT_PINNED:
            pin = Pin(str(entry.binding["digest"]), entry.binding["equipment"], entry.operation)
        elif entry.operation is ControlOperation.EQUIPMENT_TRANSITION:
            pin = Pin(str(entry.binding["to_digest"]), entry.binding["equipment"], entry.operation)
    return pin


def last_change(log: Iterable[ControlLogEntry]) -> ControlLogEntry | None:
    """The latest ``EQUIPMENT_CHANGED`` row after the current pin was set, or ``None``: what a
    transition may accept."""
    found: ControlLogEntry | None = None
    for entry in _applied(log):
        if entry.operation in (
            ControlOperation.EQUIPMENT_PINNED,
            ControlOperation.EQUIPMENT_TRANSITION,
        ):
            found = None
        elif entry.operation is ControlOperation.EQUIPMENT_CHANGED:
            found = entry
    return found


def _applied(log: Iterable[ControlLogEntry]) -> list[ControlLogEntry]:
    """The rows that took effect, in the log's order: a refused row set nothing."""
    return [e for e in log if e.outcome is ControlOutcome.APPLIED]


class TransitionRefused(ValueError):
    """The owner's transition can't be recorded: ``code`` says why, the message what to do."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def equipment_transition(
    campaign: Campaign,
    log: Iterable[ControlLogEntry],
    to_digest: str,
    *,
    actor: str,
    actor_role: str,
    reason: str,
    idempotency_key: str,
) -> CampaignTransition:
    """The owner's recorded transition to the equipment the last refused launch found.

    It accepts that equipment by its digest, so a catalog that moved again since is refused
    again at the retry rather than accepted unseen. :class:`TransitionRefused` when no launch
    found other equipment since the pin (``EQUIPMENT_NOT_CHANGED``), or ``to_digest`` isn't
    what it found (``EQUIPMENT_DIGEST_MISMATCH``). ``reason`` is required: a transition is an
    intervention, and says why."""
    if not reason.strip():
        raise ValueError("an equipment transition is an intervention, so it says why")
    rows = list(log)
    change = last_change(rows)
    pin = current_pin(rows)
    if change is None or pin is None:
        raise TransitionRefused(
            "EQUIPMENT_NOT_CHANGED",
            f"no launch of campaign {campaign.campaign_id} has found equipment other than its "
            "pin, so there is nothing to transition to",
        )
    found = str(change.binding["found_digest"])
    if to_digest != found:
        raise TransitionRefused(
            "EQUIPMENT_DIGEST_MISMATCH",
            f"the last refused launch found equipment {found}; a transition accepts exactly "
            f"that, and {to_digest} was named",
        )
    return CampaignTransition(
        operation=ControlOperation.EQUIPMENT_TRANSITION,
        actor=actor,
        actor_role=actor_role,
        reason=reason,
        idempotency_key=idempotency_key,
        next_state=None,
        target=str(change.binding.get("launch_id") or "") or None,
        binding={
            "from_digest": pin.digest,
            "to_digest": found,
            "equipment": change.binding["equipment"],
            "parts": change.binding["parts"],
        },
    )
