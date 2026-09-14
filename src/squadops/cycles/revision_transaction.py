"""The revision transaction — one agent-proposed change, resolved, authorized and applied
atomically against a known base (SIP-0107 §6, §11, §13, §14; rollout step 2).

A producer proposes revisions to regions of existing artifacts. The framework — never the
model — resolves each to an exact source range in the base, checks it against the
:class:`~squadops.cycles.write_authorization.WriteGrant` the transaction carries, and applies
every accepted revision to the immutable base or none of them. The result names its candidate
with step 1's identity (:func:`~squadops.cycles.patch_verification.candidate_revision_id`).

**Two operations.** Rollout step 2 shipped :attr:`RevisionOperation.REPLACE_REGION` — §9.3's
authorized-region replacement, the shape the qa fill path has always had (a slot body replaced
wholesale); the fill merge is its first caller, byte-identical to the merge it replaced. Step 4
adds :attr:`RevisionOperation.REPLACE_ANCHOR` — §9.2's exact anchored target: the producer
supplies existing source text, and the framework replaces it only where it occurs **exactly
once** inside the authorized region. Zero matches and several matches both refuse; nothing is
normalized, fuzzed or chosen (#451). Structural replace/insert/remove (steps 5–6) add operations
and resolvers; the atomic validation, the canonical edit and the identity stay as they are here.

**Locus.** Pure — no I/O, no clock. Resolution runs wherever the base is in hand: the qa
handler and the qa repair handler today, the runtime verifier when a repair arrives as a
transaction. A region is found by a :class:`RegionResolver` the caller supplies for the
artifact's kind, so this module holds no marker grammar of its own.

**Atomic.** Every revision is validated before any is applied (§13): the base is the one the
transaction names, the artifact exists, the grant permits its path, the region resolves, and no
two resolved ranges overlap. One failure refuses the whole transaction with every reason named
(§14) — partial acceptance would recreate the #1323 class at smaller granularity.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from squadops.cycles.write_authorization import (
    AuthzDecision,
    WorkspaceOwnership,
    WriteAuthorization,
    WriteGrant,
)


class RevisionOperation(StrEnum):
    """What a revision does to its resolved range (SIP-0107 §8)."""

    #: §9.3: replace the whole body of an explicitly authorized region (a scaffold slot).
    REPLACE_REGION = "replace_region"
    #: §9.2: replace the one exact occurrence of an anchor inside the authorized region.
    REPLACE_ANCHOR = "replace_anchor"


class RefusalReason(StrEnum):
    """Why a transaction was refused (SIP-0107 §21) — typed, one per failed revision."""

    STALE_BASE = "stale_base"
    UNKNOWN_ARTIFACT = "unknown_artifact"
    OUT_OF_GRANT = "out_of_grant"
    UNRESOLVED_REGION = "unresolved_region"
    OVERLAPPING_RANGES = "overlapping_ranges"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    #: §21: the anchor occurs nowhere in the authorized region.
    ANCHOR_NOT_FOUND = "anchor_not_found"
    #: §21: the anchor occurs more than once — the framework never chooses between matches.
    ANCHOR_AMBIGUOUS = "anchor_ambiguous"
    #: An anchored revision with no anchor text, which would match everywhere.
    EMPTY_ANCHOR = "empty_anchor"


@dataclass(frozen=True, kw_only=True)
class Revision:
    """One revision as a producer proposes it: a target in an artifact, and its new source.

    The producer names the target — a region (a slot id), or an anchor inside the authorized
    region — and never supplies coordinates. An anchored revision with no ``region_id`` searches
    the whole artifact, the region a whole-file grant authorizes.
    """

    artifact_path: str
    operation: RevisionOperation
    replacement: str
    region_id: str = ""
    anchor: str | None = None


@dataclass(frozen=True, kw_only=True)
class RevisionTransaction:
    """Revisions proposed together, against one base, under one grant (§13)."""

    base_revision_id: str
    grant: WriteGrant
    task_id: str
    revisions: tuple[Revision, ...]


@dataclass(frozen=True, kw_only=True)
class RangeEdit:
    """The canonical internal revision (SIP-0107 §11): what the framework resolved and applied.

    Offsets are character offsets into the base artifact's content. ``base_artifact_sha256`` and
    ``pre_sha256`` fingerprint the artifact and the replaced span, so a replay against a
    different base is detectable rather than silently shifted (§12).
    """

    artifact_path: str
    base_artifact_sha256: str
    region_id: str
    start: int
    end: int
    pre_sha256: str
    replacement: str
    operation: RevisionOperation
    producer: str
    task_id: str


@dataclass(frozen=True, kw_only=True)
class Refusal:
    """One revision that could not be accepted, and why."""

    revision_index: int
    reason: RefusalReason
    detail: str


@dataclass(frozen=True, kw_only=True)
class TransactionOutcome:
    """An accepted transaction's candidate, or every reason it was refused.

    ``candidate_files`` is the whole candidate tree — the base with every edit applied — and is
    empty on refusal, because nothing was applied.
    """

    accepted: bool
    edits: tuple[RangeEdit, ...] = ()
    candidate_files: Mapping[str, str] = field(default_factory=dict)
    candidate_revision_id: str | None = None
    refusals: tuple[Refusal, ...] = ()

    def changed_files(self) -> dict[str, str]:
        """The artifacts the transaction edited, with their candidate content."""
        paths = {e.artifact_path for e in self.edits}
        return {p: c for p, c in dict(self.candidate_files).items() if p in paths}


class RegionResolver(Protocol):
    """Finds a region's replaceable span in an artifact's content, or ``None``."""

    def __call__(self, artifact_path: str, content: str, region_id: str) -> tuple[int, int] | None:
        """``(start, end)`` character offsets of the region's body, end exclusive."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def base_revision_id(base_files: Mapping[str, str]) -> str:
    """The identity of a base tree — ``compute_revision_id``, the same content addressing every
    revision in the framework uses."""
    from squadops.sandbox.models import compute_revision_id

    return compute_revision_id(base_files)


def _grant_permits(grant: WriteGrant, path: str) -> bool:
    # Ownership-free on purpose: the transaction's authority is the grant it carries (§6.2),
    # not a permission reconstructed from the producer's task type downstream.
    authz = WriteAuthorization(WorkspaceOwnership(frozenset(), frozenset(), frozenset()), grant)
    return authz.authorize(path) == AuthzDecision.ALLOWED


def resolve_and_apply(
    base_files: Mapping[str, str],
    transaction: RevisionTransaction,
    resolve_region: RegionResolver,
) -> TransactionOutcome:
    """Resolve every revision against ``base_files``, then apply all of them or none (§13, §14).

    Edits are applied per artifact from the highest offset down, so one edit never moves the
    range another was resolved to — every range is resolved against the same starting base, as
    §13 requires, and no revision may depend on another having been applied first.
    """
    refusals: list[Refusal] = []
    if base_revision_id(base_files) != transaction.base_revision_id:
        refusals.append(
            Refusal(
                revision_index=-1,
                reason=RefusalReason.STALE_BASE,
                detail=(
                    f"the transaction names base {transaction.base_revision_id}; the tree it "
                    f"was handed is {base_revision_id(base_files)}"
                ),
            )
        )
        return TransactionOutcome(accepted=False, refusals=tuple(refusals))

    edits: list[RangeEdit] = []
    for index, revision in enumerate(transaction.revisions):
        if revision.operation not in (
            RevisionOperation.REPLACE_REGION,
            RevisionOperation.REPLACE_ANCHOR,
        ):
            refusals.append(
                Refusal(
                    revision_index=index,
                    reason=RefusalReason.UNSUPPORTED_OPERATION,
                    detail=f"{revision.operation!s} is not an operation this step supports",
                )
            )
            continue
        content = base_files.get(revision.artifact_path)
        if content is None:
            refusals.append(
                Refusal(
                    revision_index=index,
                    reason=RefusalReason.UNKNOWN_ARTIFACT,
                    detail=f"{revision.artifact_path} is not in the base",
                )
            )
            continue
        if not _grant_permits(transaction.grant, revision.artifact_path):
            refusals.append(
                Refusal(
                    revision_index=index,
                    reason=RefusalReason.OUT_OF_GRANT,
                    detail=(
                        f"{revision.artifact_path} is outside the {transaction.grant.stage} grant "
                        f"of {transaction.grant.producer}"
                    ),
                )
            )
            continue
        target = _resolve_target(index, revision, content, resolve_region)
        if isinstance(target, Refusal):
            refusals.append(target)
            continue
        start, end = target
        edits.append(
            RangeEdit(
                artifact_path=revision.artifact_path,
                base_artifact_sha256=_sha256(content),
                region_id=revision.region_id,
                start=start,
                end=end,
                pre_sha256=_sha256(content[start:end]),
                replacement=revision.replacement,
                operation=revision.operation,
                producer=transaction.grant.producer,
                task_id=transaction.task_id,
            )
        )

    refusals.extend(_overlaps(edits))
    if refusals:
        return TransactionOutcome(accepted=False, refusals=tuple(refusals))

    candidate = dict(base_files)
    for path in sorted({e.artifact_path for e in edits}):
        text = base_files[path]
        for edit in sorted((e for e in edits if e.artifact_path == path), key=lambda e: -e.start):
            text = text[: edit.start] + edit.replacement + text[edit.end :]
        candidate[path] = text

    from squadops.cycles.patch_verification import candidate_revision_id

    changed = [
        {"name": p, "content": candidate[p]} for p in sorted({e.artifact_path for e in edits})
    ]
    return TransactionOutcome(
        accepted=True,
        edits=tuple(edits),
        candidate_files=candidate,
        candidate_revision_id=candidate_revision_id(base_files, changed),
    )


def _resolve_target(
    index: int, revision: Revision, content: str, resolve_region: RegionResolver
) -> tuple[int, int] | Refusal:
    """The span a revision replaces: its region's body, or its anchor's one match inside the
    authorized region (the named region, else the whole artifact the grant permits)."""
    if revision.operation == RevisionOperation.REPLACE_ANCHOR and not revision.region_id:
        region: tuple[int, int] | None = (0, len(content))
    else:
        region = resolve_region(revision.artifact_path, content, revision.region_id)
    if region is None:
        return Refusal(
            revision_index=index,
            reason=RefusalReason.UNRESOLVED_REGION,
            detail=f"{revision.region_id} does not resolve in {revision.artifact_path}",
        )
    if revision.operation == RevisionOperation.REPLACE_ANCHOR:
        return _resolve_anchor(index, revision, content, region)
    return region


def _anchor_matches(content: str, anchor: str, lo: int, hi: int) -> list[int]:
    """Every start offset of ``anchor`` lying wholly inside ``[lo, hi)``, overlapping matches
    included — ``aa`` occurs twice in ``aaa``, and a count that said once would choose."""
    matches: list[int] = []
    at = content.find(anchor, lo, hi)
    while at != -1:
        matches.append(at)
        at = content.find(anchor, at + 1, hi)
    return matches


def _resolve_anchor(
    index: int, revision: Revision, content: str, region: tuple[int, int]
) -> tuple[int, int] | Refusal:
    """The anchor's one exact span inside the authorized region, or the refusal (§9.2).

    Exact means exact: no whitespace normalization, no case folding, no nearest match (#451 — an
    unanchored replace of ``'0'`` rewrote every zero in a manifest).
    """
    where = f"{revision.artifact_path}" + (
        f" region {revision.region_id}" if revision.region_id else ""
    )
    if not revision.anchor:
        return Refusal(
            revision_index=index,
            reason=RefusalReason.EMPTY_ANCHOR,
            detail=f"an anchored revision of {where} carries no anchor text",
        )
    lo, hi = region
    matches = _anchor_matches(content, revision.anchor, lo, hi)
    if not matches:
        return Refusal(
            revision_index=index,
            reason=RefusalReason.ANCHOR_NOT_FOUND,
            detail=f"the anchor does not occur in {where}",
        )
    if len(matches) > 1:
        return Refusal(
            revision_index=index,
            reason=RefusalReason.ANCHOR_AMBIGUOUS,
            detail=f"the anchor occurs {len(matches)} times in {where}; it must occur exactly once",
        )
    return matches[0], matches[0] + len(revision.anchor)


def _overlaps(edits: Sequence[RangeEdit]) -> list[Refusal]:
    """Resolved ranges in one artifact that intersect, or that name one region twice (§13)."""
    refusals: list[Refusal] = []
    by_path: dict[str, list[RangeEdit]] = {}
    for edit in edits:
        by_path.setdefault(edit.artifact_path, []).append(edit)
    for path, path_edits in sorted(by_path.items()):
        ordered = sorted(path_edits, key=lambda e: (e.start, e.end))
        for first, second in zip(ordered, ordered[1:], strict=False):
            if second.start < first.end or (second.start, second.end) == (first.start, first.end):
                refusals.append(
                    Refusal(
                        revision_index=-1,
                        reason=RefusalReason.OVERLAPPING_RANGES,
                        detail=(
                            f"{path}: {first.region_id} [{first.start},{first.end}) and "
                            f"{second.region_id} [{second.start},{second.end}) overlap"
                        ),
                    )
                )
    return refusals
