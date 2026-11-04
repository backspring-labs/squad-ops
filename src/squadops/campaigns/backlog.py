"""A goal set's backlog as one Campaign stands on it (SIP-0115 §4, §5.3, §5.5a; SIP-0109 §24cy).

Each item's status is **derived** from the Campaign's control log and launch outbox, never stored
(§4, as #2578 part 4's increments are). There is no writable table: this is a pure projection of
the rows already written, read with the goal set's revisions:
- a ``submit`` row names the item its proposal serves and the goal-set revision it was created
  under (``backlog_item``, ``goals_revision``), from the change request the rails accepted;
- the ``rule`` row on it, and the cycles that carried it (``ledger``'s mapping, a repair or retry
  by its own launch's binding), say whether it is live, building, accepted or abandoned:
  - a ``promote`` row of a carrying cycle accepts it;
  - a decision or an owner's word that abandons its increment (``abandon_and_propose``), or a
    terminal decision or an abort while it was unresolved, abandons it, with the row and reason;
  - a return or a rejection leaves it ``pending``: no live proposal names it;
  - a rebase that superseded its repair or retry (``upstream_moved``) leaves it ``pending`` too:
    the squad's work didn't fail, the tree under it moved (SIP-0109 §24cd point 2).

Everything above ``campaign_backlog`` is pure; it alone reads the stores, through their ports.

The statuses (§4): ``pending``, ``proposed``, ``in_increment``, ``accepted``, ``abandoned`` and
``removed``. An accepted item carries the revision it was accepted under, and reads
``accepted (removed in rN)`` or ``accepted (results changed in rN)`` when a later revision dropped
it or changed an expected result it serves (§5.5a). ``accepted (carried)`` (an item accepted in
another Campaign, verified on this one's calibration tree) is not built (SIP-0115 §10b).

**An abandoned item is skipped** by the next proposal (§5.3) until a later revision changes the
item itself (its title, description, ``serves`` or size): that edit is the re-queue (§10b).

**Eligibility is read against the transition being prepared** (SIP-0109 §24cy item 7, the outside
second review of PR #2901). The owner's word and a rebase's supersession build their proposal
before their row commits, so the view takes that row as ``pending_word`` (the owner's action on the
decided cycle, read as ``_owners_word`` would read its ``resume`` row) or ``superseding`` (the
launch a rebase supersedes, read as ``_superseded_versions`` would read its row).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from squadops.campaigns.continuation import PendingAction
from squadops.campaigns.ledger import BACKLOG_ITEM_KEY, GOALS_REVISION_KEY, ledger
from squadops.campaigns.models import (
    Campaign,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
    LaunchIntent,
)
from squadops.cycles.models import GateDecisionValue, GoalSetNotFoundError

if TYPE_CHECKING:
    # Annotations only: ``projects`` imports ``campaigns`` at module level (#1985's direction).
    from squadops.ports.cycles.campaign_registry import CampaignRegistryPort
    from squadops.ports.projects.goal_sets import GoalSetRegistryPort
    from squadops.projects.goal_set import BacklogItem, GoalSet, GoalSetRevision


class ItemStatus(StrEnum):
    PENDING = "pending"
    PROPOSED = "proposed"
    IN_INCREMENT = "in_increment"
    ACCEPTED = "accepted"
    ABANDONED = "abandoned"
    REMOVED = "removed"


@dataclass(frozen=True)
class ItemView:
    """One item as the Campaign stands on it."""

    item_id: str
    title: str
    serves: tuple[str, ...]
    status: ItemStatus
    #: Its place in the order of the revision read, from 1; ``None`` when that revision dropped it.
    position: int | None
    #: The proposal version that last named it, and the cycle it was proposed in.
    proposal_id: str | None = None
    version: int | None = None
    cycle_id: str | None = None
    #: The goal-set revision that proposal was created under: for an accepted item, the revision
    #: it was accepted under (§5.5a).
    revision: int | None = None
    #: ``abandoned`` (or ``removed`` after one): the row that abandoned it, and why.
    row: int | None = None
    reason: str | None = None
    #: The first revision after the one it was accepted (or last proposed) under that dropped it.
    removed_in: int | None = None
    #: Accepted only: the first later revision that changed an expected result it serves.
    results_changed_in: int | None = None
    #: Dropped by a split (§5.5a): the items that took its place, read from that revision's
    #: ``change``; empty for an item the owner removed.
    split_into: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        """The status as the SIP writes it: ``accepted (removed in r4)``, say."""
        if self.status is ItemStatus.ACCEPTED and self.removed_in is not None:
            return f"accepted (removed in r{self.removed_in})"
        if self.status is ItemStatus.ACCEPTED and self.results_changed_in is not None:
            return f"accepted (results changed in r{self.results_changed_in})"
        return self.status.value


@dataclass(frozen=True)
class BacklogView:
    """The backlog of one goal-set revision, as one Campaign stands on it."""

    revision: int
    items: tuple[ItemView, ...]

    @property
    def next_item(self) -> ItemView | None:
        """The next eligible item (§5.3): the first of the revision's order that is ``pending``.
        An ``abandoned`` one is skipped. ``None`` when none is pending."""
        return next(
            (i for i in self.items if i.position is not None and i.status is ItemStatus.PENDING),
            None,
        )

    @property
    def done(self) -> bool:
        """§5.5a: every item of the revision is accepted in this Campaign. An item a revision
        removed isn't one of its items, so it is done by definition (``removed``)."""
        return all(i.status is ItemStatus.ACCEPTED for i in self.items if i.position is not None)


@dataclass(frozen=True)
class _Named:
    """One submitted proposal version that named an item."""

    proposal_id: str
    version: int
    item_id: str
    revision: int | None
    cycle_id: str
    status: ItemStatus
    row: int | None = None
    reason: str | None = None


def backlog_view(
    revisions: Iterable[GoalSetRevision],
    at: int,
    log: Sequence[ControlLogEntry],
    launches: Iterable[LaunchIntent] = (),
    *,
    leaving_out: tuple[str, int] | None = None,
    pending_word: tuple[str, str] | None = None,
    superseding: str | None = None,
) -> BacklogView:
    """The backlog of revision ``at`` of the goal set ``revisions`` hold, as the Campaign whose
    control log and launch outbox these are stands on it.

    ``leaving_out`` is a ``(proposal_id, version)`` read as if never submitted: the proposal a
    ruling is about to decide, so the item it names reads as it would for a fresh proposal.

    ``pending_word`` is ``(cycle_id, action)``: the owner's word on that decided cycle, whose
    ``resume`` row is being prepared and not yet committed, read as if it were. ``superseding`` is
    the launch id a rebase is about to supersede, read as if its row were committed.

    Raises ``ValueError`` when ``revisions`` holds no revision ``at``."""
    by_number = {r.revision: r for r in revisions}
    if at not in by_number:
        raise ValueError(f"the goal set holds no revision {at}")
    read = by_number[at].goal_set
    latest_named = _latest_named(log, list(launches), leaving_out, pending_word, superseding)
    items = [_in_revision(item, n, latest_named.get(item.id), by_number, at)
             for n, item in enumerate(read.backlog, start=1)]  # fmt: skip
    present = {item.id for item in read.backlog}
    for item_id, named in latest_named.items():
        if item_id not in present:
            items.append(_dropped(item_id, named, by_number, at))
    return BacklogView(revision=at, items=tuple(items))


def results_changed(item_id: str, since: GoalSet, now: GoalSet) -> bool:
    """Whether ``now`` changed the item or an expected result it served in ``since``: its
    ``serves``, or a served result's statement or surface, or dropped either (§5.5a)."""
    before = _item(since, item_id)
    after = _item(now, item_id)
    if before is None:
        return False
    if after is None or after.serves != before.serves:
        return True
    then = {r.id: r for r in since.expected_results}
    current = {r.id: r for r in now.expected_results}
    return any(then.get(s) != current.get(s) for s in before.serves)


def goals_revised(
    *,
    item_id: str,
    bound: GoalSetRevision,
    latest: GoalSetRevision,
    view_at_latest: BacklogView,
) -> str | None:
    """§5.5a: why a proposal created under ``bound`` naming ``item_id`` is returned at its ruling
    as ``goals_revised``, or ``None``. Only a later revision returns it, and only when the item is
    no longer the next eligible one there, or an expected result it serves changed.
    ``view_at_latest`` is the backlog at ``latest`` with this proposal left out."""
    if latest.revision <= bound.revision:
        return None
    following = view_at_latest.next_item
    if following is None or following.item_id != item_id:
        now = f"{following.item_id}" if following else "no item"
        return (
            f"the goal set was revised to r{latest.revision} after this proposal was created "
            f"under r{bound.revision}: {item_id} is no longer the next item, {now} is"
        )
    if results_changed(item_id, bound.goal_set, latest.goal_set):
        return (
            f"the goal set was revised to r{latest.revision} after this proposal was created "
            f"under r{bound.revision}: an expected result {item_id} serves changed"
        )
    return None


@dataclass(frozen=True)
class Acceptance:
    """One increment a Campaign accepted: the control-log row that did, and the expected results
    its item served in the revision its proposal is bound to (§5.5a)."""

    seq: int
    item_id: str
    serves: tuple[str, ...]


def acceptances(
    revisions: Iterable[GoalSetRevision],
    log: Sequence[ControlLogEntry],
    launches: Iterable[LaunchIntent] = (),
) -> tuple[Acceptance, ...]:
    """The Campaign's accepted increments that named a backlog item, in log order: what makes an
    assessment of a result they served stale (SIP-0115 §5.7)."""
    by_number = {r.revision: r for r in revisions}
    promoted = {
        str(e.target): e.seq
        for e in log
        if e.outcome is ControlOutcome.APPLIED
        and e.operation is ControlOperation.PROMOTE
        and e.target is not None
    }
    found = []
    for entry in ledger(list(log), launches):
        bound = by_number.get(entry.goals_revision) if entry.goals_revision else None
        item = _item(bound.goal_set, entry.backlog_item or "") if bound else None
        cycles = [c["cycle_id"] for c in entry.cycles] or [entry.cycle_id]
        rows = [promoted[c] for c in cycles if c in promoted]
        if item is not None and rows:
            found.append(Acceptance(min(rows), item.id, item.serves))
    return tuple(sorted(found, key=lambda a: a.seq))


# --- reading the control log ---


def _latest_named(
    log: Sequence[ControlLogEntry],
    launches: list[LaunchIntent],
    leaving_out: tuple[str, int] | None,
    pending_word: tuple[str, str] | None = None,
    superseding: str | None = None,
) -> dict[str, _Named]:
    """Each item's last naming proposal version, by submission order, with its status."""
    applied = [e for e in log if e.outcome is ControlOutcome.APPLIED]
    named_by: dict[tuple[str, int], tuple[str, int | None]] = {}
    for e in applied:
        b = e.binding
        if e.operation is ControlOperation.SUBMIT and b.get(BACKLOG_ITEM_KEY):
            key = (str(b["proposal_id"]), int(b["version"]))
            if key != leaving_out:
                revision = b.get(GOALS_REVISION_KEY)
                named_by[key] = (str(b[BACKLOG_ITEM_KEY]), int(revision) if revision else None)
    if not named_by:
        return {}
    promoted = {
        str(e.target)
        for e in applied
        if e.operation is ControlOperation.PROMOTE and e.target is not None
    }
    superseded = _superseded_versions(applied, launches, superseding)
    owners_word = _owners_word(applied)
    if pending_word is not None:
        cycle_id, action = pending_word
        owners_word[cycle_id] = (action, "abandoned by the owner's word, being written")
    ended = _campaign_end(applied)
    latest: dict[str, _Named] = {}
    for entry in ledger(list(log), launches):
        key = (entry.proposal_id, entry.version)
        if key not in named_by:
            continue
        item_id, revision = named_by[key]
        status, row, reason = _status(entry, promoted, superseded, owners_word, ended)
        latest[item_id] = _Named(
            entry.proposal_id, entry.version, item_id, revision, entry.cycle_id, status, row, reason
        )
    return latest


def _status(entry, promoted, superseded, owners_word, ended):
    """``(status, row, reason)`` of one proposal version, from its ruling and its cycles."""
    ruling = entry.ruling
    cycles = [c["cycle_id"] for c in entry.cycles] or [entry.cycle_id]
    if ruling is None:
        if entry.outcome is not None or ended is not None:
            # Its cycle ended with nobody ruling (an abort, a stop): nothing live names it.
            return ItemStatus.PENDING, None, None
        return ItemStatus.PROPOSED, None, None
    if ruling["decision"] != GateDecisionValue.APPROVED.value:
        return ItemStatus.PENDING, None, None
    if any(c in promoted for c in cycles):
        return ItemStatus.ACCEPTED, None, None
    outcome = entry.outcome or {}
    if outcome.get("action") == PendingAction.ABANDON_AND_PROPOSE.value:
        return (
            ItemStatus.ABANDONED,
            outcome.get("row"),
            f"§10 row {outcome.get('row')}: its increment was abandoned "
            f"({outcome.get('ending')}, {outcome.get('verdict')})",
        )
    word = owners_word.get(cycles[-1])
    if word is not None:
        action, said = word
        if action == PendingAction.ABANDON_AND_PROPOSE.value:
            return ItemStatus.ABANDONED, None, said
        if action == PendingAction.PROPOSE.value:
            # The owner moved on to a fresh proposal without abandoning the increment: it ended
            # unaccepted, and nothing live names the item.
            return ItemStatus.PENDING, None, None
    if (entry.proposal_id, entry.version) in superseded:
        return ItemStatus.PENDING, None, None
    if outcome.get("outcome"):
        return (
            ItemStatus.ABANDONED,
            outcome.get("row"),
            f"the campaign ended at §10 row {outcome.get('row')} ({outcome.get('cause')}) with "
            "its increment unaccepted",
        )
    if ended is not None:
        return ItemStatus.ABANDONED, None, ended
    return ItemStatus.IN_INCREMENT, None, None


def _owners_word(applied: list[ControlLogEntry]) -> dict[str, tuple[str, str]]:
    """The owner's word on each decided cycle: the action a ``resume`` executed after the decision
    that decided it (``progress._last_decided_cycle``), with what it said. A later word on the same
    cycle replaces an earlier one; a repair or retry continues the increment, and is read from its
    own cycle's decision."""
    out: dict[str, tuple[str, str]] = {}
    last_decided: str | None = None
    for e in applied:
        if e.operation is ControlOperation.DECIDE and "row" in e.binding:
            last_decided = e.binding.get("cycle_id") or None
        elif e.operation is ControlOperation.RESUME and e.binding.get("action") and last_decided:
            out[last_decided] = (
                str(e.binding["action"]),
                f"abandoned by {e.actor}'s word: {e.reason}",
            )
    return out


def _superseded_versions(
    applied: list[ControlLogEntry], launches: list[LaunchIntent], superseding: str | None = None
) -> set[tuple[str, int]]:
    """The proposal versions whose repair or retry a rebase superseded (``upstream_moved``), and
    the one ``superseding`` is about to."""
    superseded = {
        str(e.binding["superseded_launch_id"])
        for e in applied
        if e.operation is ControlOperation.BRANCH_REBASED and e.binding.get("superseded_launch_id")
    }
    if superseding is not None:
        superseded.add(superseding)
    out: set[tuple[str, int]] = set()
    for intent in launches:
        if intent.launch_id in superseded:
            body = intent.cycle_request.get("body") or {}
            block = (body.get("execution_overrides") or {}).get("campaign_proposal") or {}
            if block.get("proposal_id") and block.get("version") is not None:
                out.add((str(block["proposal_id"]), int(block["version"])))
    return out


def _campaign_end(applied: list[ControlLogEntry]) -> str | None:
    """Why the campaign ended outside a cycle's decision (an abort), or ``None``."""
    for e in applied:
        if e.operation is ControlOperation.ABORT:
            return f"the campaign was aborted by {e.actor}: {e.reason}"
    return None


# --- the items ---


def _item(goal_set: GoalSet, item_id: str) -> BacklogItem | None:
    return next((i for i in goal_set.backlog if i.id == item_id), None)


def _in_revision(
    item: BacklogItem,
    position: int,
    named: _Named | None,
    revisions: Mapping[int, GoalSetRevision],
    at: int,
) -> ItemView:
    base = ItemView(item.id, item.title, item.serves, ItemStatus.PENDING, position)
    if named is None:
        return base
    view = _with(base, named)
    if named.status is ItemStatus.ABANDONED and _requeued(item.id, named.revision, revisions, at):
        return _with(base, named, status=ItemStatus.PENDING)
    if named.status is ItemStatus.ACCEPTED and named.revision is not None:
        return _with(
            view,
            named,
            results_changed_in=_first_change(item.id, named.revision, revisions, at),
        )
    return view


def _dropped(
    item_id: str, named: _Named, revisions: Mapping[int, GoalSetRevision], at: int
) -> ItemView:
    """An item this Campaign proposed that revision ``at`` doesn't hold. An accepted one stays
    accepted, naming the revision that dropped it; a running one keeps running (§5.5); any other
    reads ``removed``, with its last abandonment kept. One a split dropped names the items that
    took its place (§5.5a), from the dropping revision's ``change``."""
    since = named.revision or 0
    removed_in = next(
        (n for n in sorted(revisions) if since < n <= at and _item(revisions[n].goal_set, item_id) is None),
        at,
    )  # fmt: skip
    before = revisions.get(named.revision) if named.revision else None
    item = _item(before.goal_set, item_id) if before else None
    status = (
        named.status
        if named.status in (ItemStatus.ACCEPTED, ItemStatus.IN_INCREMENT, ItemStatus.PROPOSED)
        else ItemStatus.REMOVED
    )
    return _with(
        ItemView(
            item_id,
            item.title if item else item_id,
            item.serves if item else (),
            status,
            None,
        ),
        named,
        status=status,
        removed_in=removed_in,
        split_into=_split_into(item_id, revisions.get(removed_in)),
    )


def _split_into(item_id: str, revision: GoalSetRevision | None) -> tuple[str, ...]:
    """The items a split of ``item_id`` in ``revision`` produced, or none: the revision's
    ``change`` is an ``item_split`` of it."""
    # deferred (pair): squadops.projects imports this package at load (workspaces' FileTree)
    from squadops.projects.goal_set import ChangeKind

    change = revision.change if revision is not None else None
    if change is None or change.kind is not ChangeKind.ITEM_SPLIT or change.subject != item_id:
        return ()
    return change.split_into


def _with(view: ItemView, named: _Named, **changes: Any) -> ItemView:
    values: dict[str, Any] = {
        "status": named.status,
        "proposal_id": named.proposal_id,
        "version": named.version,
        "cycle_id": named.cycle_id,
        "revision": named.revision,
        "row": named.row,
        "reason": named.reason,
    }
    values.update(changes)
    return replace(view, **values)


def _requeued(
    item_id: str, since: int | None, revisions: Mapping[int, GoalSetRevision], at: int
) -> bool:
    """Whether a revision after ``since`` up to ``at`` edited the item itself: its title,
    description, ``serves`` or size. That edit re-queues an abandoned item (§5.3, §10b)."""
    if since is None or since not in revisions:
        return False
    then = _item(revisions[since].goal_set, item_id)
    return any(
        _item(revisions[n].goal_set, item_id) != then for n in sorted(revisions) if since < n <= at
    )


def _first_change(
    item_id: str, since: int, revisions: Mapping[int, GoalSetRevision], at: int
) -> int | None:
    """The first revision after ``since`` up to ``at`` that changed an expected result the item
    serves, or ``None``."""
    if since not in revisions:
        return None
    for n in sorted(revisions):
        if since < n <= at and results_changed(
            item_id, revisions[since].goal_set, revisions[n].goal_set
        ):
            return n
    return None


# --- reading it for a Campaign ---


async def gate_goal_evidence(
    campaign: Campaign, *, goal_sets: GoalSetRegistryPort, campaigns: CampaignRegistryPort
) -> dict[tuple[str, int], dict[str, Any]]:
    """What a reviewer outside SquadOps judges an open gate against (SIP-0115 §8.5), by proposal
    version: the goal, the backlog item and the expected results it serves, as documents of the
    goal set, read from the revision the version is bound to (§5.5a), never a later one.

    Only a version an open gate can be on: its item ``proposed`` (the increment gate) or
    ``in_increment`` (the plan gate). A reviewer's request is bounded, and the rows already decided
    keep their item's id, so repeating each one's goal would spend that bound on nothing."""
    view, revisions = await campaign_backlog(campaign, goal_sets=goal_sets, campaigns=campaigns)
    by_number = {r.revision: r for r in revisions}
    evidence: dict[tuple[str, int], dict[str, Any]] = {}
    for held in view.items:
        if held.status not in (ItemStatus.PROPOSED, ItemStatus.IN_INCREMENT):
            continue
        bound = by_number.get(held.revision) if held.revision is not None else None
        if bound is None or held.proposal_id is None or held.version is None:
            continue
        document = bound.goal_set.to_document()
        item = next((i for i in document["backlog"] if i["id"] == held.item_id), None)
        if item is None:
            continue
        evidence[(held.proposal_id, held.version)] = {
            "goal": document["goal"],
            "item": item,
            "expected_results": [
                r for r in document["expected_results"] if r["id"] in item["serves"]
            ],
        }
    return evidence


async def campaign_backlog(
    campaign: Campaign,
    *,
    goal_sets: GoalSetRegistryPort,
    campaigns: CampaignRegistryPort,
    leaving_out: tuple[str, int] | None = None,
    pending_word: tuple[str, str] | None = None,
    superseding: str | None = None,
) -> tuple[BacklogView, tuple[GoalSetRevision, ...]]:
    """The Campaign's backlog at the revision it reads now: its pinned one, or its goal set's
    latest (``current``, §5.5), with every revision read. The one reading the proposal's input,
    the ruling, the continuation decision and the API share. ``pending_word`` and ``superseding``
    are ``backlog_view``'s: the transition being prepared.

    Raises:
        ValueError: The campaign names no goal set.
        GoalSetNotFoundError: Its Project has none written, or not its pinned revision.
    """
    goals = campaign.objective.goals
    if goals is None:
        raise ValueError(f"campaign {campaign.campaign_id} names no goal set (objective.goals)")
    revisions = tuple(await goal_sets.list_revisions(campaign.project_id))
    if not revisions:
        raise GoalSetNotFoundError(f"Project {campaign.project_id} has no goal set written")
    at = goals.pinned or max(r.revision for r in revisions)
    if at not in {r.revision for r in revisions}:
        raise GoalSetNotFoundError(f"Project {campaign.project_id}'s goal set has no revision {at}")
    view = backlog_view(
        revisions,
        at,
        await campaigns.control_log(campaign.campaign_id),
        await campaigns.launch_intents(campaign.campaign_id),
        leaving_out=leaving_out,
        pending_word=pending_word,
        superseding=superseding,
    )
    return view, revisions
