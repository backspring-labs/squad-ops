"""Verification evidence integrity — the pure aggregation core (SIP-0096).

The single, side-effect-free choke point that classifies every recorded
verification result into exactly one **evidence family** and computes the run's
verification **verdict**. No persistence, no dispatch, no I/O — side effects
live only at the boundary that acts on the summary (the ``RunCompletion`` seam,
SIP-0096 §6.4). Architecture-tested for purity (AC#13).

Three deliberately-separate layers (SIP-0096 §6.1):

  - **persisted result status** — what producers emit today (``CheckOutcome``
    ``passed/failed/skipped/error``, ``RunTestsResult.executed``,
    ``SuiteOutcome``). *Unchanged* — this module adds no persisted vocabulary.
  - **evidence family** — derived *here*, at aggregation time.
  - **run verdict** — computed once *here* per run; recorded on the roll-up,
    **not** a ``RunStatus`` (§6.5).

The load-bearing integrity rule (§6.1) lives in exactly one place — ``classify``
— so every producer routes through the same law:

    Only executed-and-passed credits as success. Not-executed results are
    non-creditable: they never improve a pass count, threshold, or all-green
    rule, and — when the check is required — they block acceptance as
    ``blocked_unverified`` rather than disappearing.

**Phase 1 (this module) is inert by construction.** It ships with no profile
``required_checks`` lists and no producer wiring, so every default-profile run
aggregates to ``accepted`` with its evidence honestly disclosed. Phase 2 wires
the real producers (normalizing them into ``CheckResult``) and per-profile
required lists — the throttle — turning silently-green paths honestly red only
where a profile requires them.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ResultStatus:
    """The persisted-status literals this module classifies *from* (SIP-0096 §6.1).

    Mirrors ``CheckOutcome``'s vocabulary (SIP-0092); it is the declared input
    contract for the normalized ``CheckResult``. Producers with other
    vocabularies (``SuiteOutcome`` pass/fail/skip, ``RunTestsResult.executed``)
    are normalized into these tokens by their Phase-2 adapters — a runner
    ``not_executed`` becomes ``SKIPPED`` with a machine-readable reason (§7),
    lossless for aggregation because both are the not-executed family.

    Not persisted here — a drift test asserts these still match what
    ``CheckOutcome`` emits.
    """

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class EvidenceFamily(StrEnum):
    """Aggregation-time classification of one verification result (SIP-0096 §6.1).

    Derived, never persisted per-producer. Only ``EXECUTED_PASSED`` credits as
    success; ``NOT_EXECUTED`` is non-creditable (never improves a count,
    threshold, or all-green rule) and, when the check is required, blocks
    acceptance.
    """

    EXECUTED_PASSED = "executed_passed"
    EXECUTED_FAILED = "executed_failed"
    NOT_EXECUTED = "not_executed"


class RunVerdict(StrEnum):
    """Per-run verification verdict computed by ``aggregate_verification`` (§6.1).

    Recorded on the roll-up; **not** a ``RunStatus`` (§6.5). ``blocked_unverified``
    is a harness/evidence-integrity verdict — the framework cannot honestly claim
    verification (repair target: harness/environment/profile/source set) — and is
    deliberately distinct from ``rejected`` (the product failed a criterion;
    repair target: the product).
    """

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BLOCKED_UNVERIFIED = "blocked_unverified"


class NotExecutedReason(StrEnum):
    """Machine-readable reason taxonomy for not-executed results (SIP-0096 §7).

    Mandatory on every not-executed result. These are semantically different
    diagnoses; the invariant is not that they are identical — it is that **none
    of them can aggregate as success** (§6.1). Producers/adapters target this
    vocabulary; unrecognized reason strings are still disclosed, never dropped.
    """

    # Designed skips (SIP-0092 RC-12a) — non-blocking by design, still disclosed.
    CONFIG_DISABLED = "config_disabled"
    UNSUPPORTED_STACK = "unsupported_stack"
    # Environment gaps.
    MISSING_TOOLING = "missing_tooling"
    # Subject gaps.
    SUBJECT_MISSING = "subject_missing"
    IMPORT_ERROR = "import_error"
    FILTERED_OUT = "filtered_out"
    # Timing.
    TIMEOUT_BEFORE_EXECUTION = "timeout_before_execution"


# Fallback reason for a producer that emits a not-executed result WITHOUT the
# mandatory §7 reason. We disclose the gap honestly rather than mask it as a
# specific diagnosis (the "no fallback that masks a missing data source" rule).
UNSPECIFIED_REASON = "unspecified"


@dataclass(frozen=True)
class CheckProvenance:
    """Bounded execution provenance for a verification result (SIP-0096 §7).

    Bounded identifiers, hashes, exit metadata, and digests **only** — never
    unbounded logs or payload copies (§7). Phase 1 defines the contract and
    carries it optionally on ``CheckResult``; Phase 2 retrofits the real
    producers (#289/#290 checks) to populate it and the roll-up to surface it.
    """

    executed_at: str | None = None  # ISO-8601; str keeps this module clock-free/pure
    duration_ms: int | None = None
    subject_ref: str | None = None  # what was checked — file-set hash, artifact ID, endpoint
    executor_ref: str | None = None  # where it ran
    exit_code: int | None = None  # command-backed checks
    output_digest: str | None = None  # bounded digest, never the raw output


@dataclass(frozen=True)
class CheckResult:
    """Normalized verification result — the aggregation input (SIP-0096 §6.1).

    Producers (``CheckOutcome``, ``PulseVerificationRecord``, generated-test
    execution, ``required_files``) are adapted into this shape and appended to
    the ``RunLedger``; the pure classifier owns the mapping rule so it lives in
    exactly one place.

    ``status`` is the producer's **persisted** status literal (``ResultStatus``);
    ``reason`` is required when the result is not-executed (a ``NotExecutedReason``
    value). ``is_stub``/``stub_disclosed`` carry the §6.6.1 anti-stub signal: a
    substituted stub reporting ``passed`` is not executed-passed unless the
    substitution is itself the disclosed subject under test.
    """

    check_id: str
    status: str
    reason: str | None = None
    is_stub: bool = False
    stub_disclosed: bool = False
    provenance: CheckProvenance | None = None
    subject: str | None = None
    # The producing subject's identity (§6.3) — the plan-task id that emitted this
    # result. DISTINCT from ``provenance.subject_ref`` (the *thing* under test — a
    # file-set hash/artifact/endpoint, which legitimately *differs* between a failed
    # check and its re-run against patched artifacts, so it is the wrong grouping
    # key). ``subject`` is stable across a task's re-verification, so aggregation can
    # supersede a repaired-and-re-run check to its final state (§6.5) without
    # collapsing distinct producers that share a ``check_id`` (e.g. ``tests_pass``
    # emitted once per develop task). ``None`` = no producer identity → never
    # collapsed (each such result is its own evidence).


@dataclass(frozen=True)
class UnverifiedCheck:
    """A not-executed result disclosed in the roll-up — never dropped (§6.6.3)."""

    check_id: str
    reason: str
    required: bool


@dataclass(frozen=True)
class RunVerificationSummary:
    """Per-run verification roll-up — the honest evidence contract (§6.2, §10).

    References only (``check_id``s), never copies of the underlying records.
    Feeds the ``CycleOutcome`` roll-up (Phase 3) and, later, the Campaign
    continuation decision (1.6). ``verdict`` is **not** a ``RunStatus`` (§6.5).
    """

    verdict: RunVerdict
    verified: tuple[str, ...]  # executed-and-passed
    failed: tuple[str, ...]  # executed-and-failed
    unverified: tuple[UnverifiedCheck, ...]  # not-executed, with reasons — always disclosed
    required_unmet: tuple[str, ...]  # required check_ids not-executed (drove blocked_unverified)
    executed_count: int
    passed_count: int

    @property
    def pass_rate(self) -> float:
        """Executed-and-passed / executed.

        ``0`` executed → ``0.0``. "0 failed of 0 executed" is zero evidence, never
        100% (SIP-0096 §6.2, AC#1) — not-executed results are excluded from the
        denominator, so they can never inflate this toward success.
        """
        return self.passed_count / self.executed_count if self.executed_count else 0.0


@dataclass(frozen=True)
class WaivedCheck:
    """An operator gate waiver, recorded *above* the evidence (SIP-0096 §6.5).

    A waiver is an operator decision recorded on the roll-up — never a mutation of
    the underlying check result (SIP-0092 §6.3.2: results stand un-loosened). Empty
    until the Phase-3 gate-waiver slice wires it; part of the contract shape now so
    downstream consumers can depend on it.
    """

    check_id: str
    reason: str
    waived_by: str | None = None


@dataclass(frozen=True)
class CycleOutcome:
    """The durable per-cycle verification-evidence roll-up (SIP-0096 §10).

    The contract downstream consumers read, in order of arrival: **wrap-up**
    (SIP-0080 confidence classification gets an honest basis), **operator gates**
    (a ``blocked_unverified`` gate sees the harness-vs-product distinction + the
    waiver option), and — the strategic one — the **Campaign continuation
    decision** (1.6). References only (``check_id``s / disclosure records), never
    copies of the underlying SIP-0070/0092 records (§10).

    This is also the substrate the later cycle-evaluation scorecard derives its
    outcome/quality/efficiency/stability dimensions from — those are *projections*
    over this honest evidence, not new raw fields here.

    ``verdict`` is the cycle-level roll-up of the per-run verdicts (worst wins, so
    the incomplete-evidence signal is never hidden); it is **not** a cycle status,
    and it is the **un-waived** evidence verdict — a waiver sits beside it in
    ``waived`` and never alters it (§6.5).
    """

    verdict: RunVerdict
    verified: tuple[str, ...]  # executed-and-passed across the cycle's runs
    failed: tuple[str, ...]  # executed-and-failed
    unverified: tuple[UnverifiedCheck, ...]  # not-executed, with reasons — always disclosed
    run_count: int
    inert: tuple[str, ...] = ()  # §9 chronic not-executed — populated by the inert-detection slice
    waived: tuple[WaivedCheck, ...] = ()  # §6.5 operator waivers — populated by the waiver slice

    @property
    def required_unmet(self) -> tuple[str, ...]:
        """Required check_ids not-executed in any run (what drove ``blocked_unverified``).

        Derived from ``unverified`` rather than stored, so the required set and its
        disclosure can never drift apart.
        """
        return tuple(u.check_id for u in self.unverified if u.required)


def classify(result: CheckResult) -> EvidenceFamily:
    """Map one result to its evidence family — the integrity rule (SIP-0096 §6.1).

    In exactly one place:

      - ``passed`` → executed-and-passed, **unless** an undisclosed stub
        substitution (the real subject was never evaluated, §6.6.1) →
        not-executed.
      - ``failed`` → executed-and-failed.
      - ``error`` → executed-and-failed (SIP-0092 §6.1.4 preserved: an evaluator
        that crashed *attempting* the real subject is executed context, not
        silence; it blocks per severity downstream, and does not credit here).
      - ``skipped`` / anything unrecognized → not-executed. Nothing
        unclassifiable may credit as success — an unknown status is treated as
        zero evidence, never a silent pass.
    """
    status = (result.status or "").strip().lower()
    if status == ResultStatus.PASSED:
        # §6.6.1: a substituted stub reporting pass is NOT executed-passed unless
        # the substitution is itself the disclosed subject under test.
        if result.is_stub and not result.stub_disclosed:
            return EvidenceFamily.NOT_EXECUTED
        return EvidenceFamily.EXECUTED_PASSED
    if status in (ResultStatus.FAILED, ResultStatus.ERROR):
        return EvidenceFamily.EXECUTED_FAILED
    return EvidenceFamily.NOT_EXECUTED


def _not_executed_reason(result: CheckResult) -> str:
    """Resolve the disclosed reason for a not-executed result (§7).

    An undisclosed stub-pass is a subject-missing case (the real subject was
    never evaluated); otherwise the producer's declared reason, falling back to
    ``UNSPECIFIED_REASON`` when a producer violates §7 by omitting it — disclosed,
    never masked as a specific diagnosis.
    """
    if (result.status or "").strip().lower() == ResultStatus.PASSED and result.is_stub:
        return NotExecutedReason.SUBJECT_MISSING
    return result.reason or UNSPECIFIED_REASON


def _resolve_final_state(results: Sequence[CheckResult]) -> list[CheckResult]:
    """Collapse each identified producer's re-verified check to its final state (§6.5).

    A check that failed, was repaired, and re-ran lands on the append-only ledger
    twice (a FAILED then a PASSED ``CheckResult`` with the same ``(check_id,
    subject)``). The verdict must reflect the **final** state after correction's
    bounded attempts — not the union of all attempts (#379), which would pin a
    recovered run to ``rejected`` forever (the "stuck-red" mirror of the false-green
    this SIP kills). So the LAST-appended result per identity supersedes.

    The ledger is append-only, so append order *is* attempt order — resolution keys
    off position, never a timestamp, keeping this module clock-free.

    Results with ``subject is None`` carry no producer identity and are **never**
    collapsed: each is independent evidence (the correct default — e.g. distinct
    develop tasks emitting ``tests_pass`` must accumulate, "any subject failed →
    rejected"; only the *same* subject re-verified supersedes).
    """
    resolved: list[CheckResult] = []
    final_pos_by_identity: dict[tuple[str, str], int] = {}
    for r in results:
        if r.subject is None:
            resolved.append(r)
            continue
        identity = (r.check_id, r.subject)
        prior = final_pos_by_identity.get(identity)
        if prior is None:
            final_pos_by_identity[identity] = len(resolved)
            resolved.append(r)
        else:
            resolved[prior] = r  # supersede the earlier attempt with the final one
    return resolved


def aggregate_verification(
    results: Sequence[CheckResult],
    required_check_ids: Collection[str] = (),
    *,
    run_succeeded: bool = True,
) -> RunVerificationSummary:
    """Pure aggregation choke point (SIP-0096 §6.2, §6.4).

    Classifies every recorded result into an evidence family and computes the run
    verdict. Side-effect free — no persistence, no dispatch (architecture-tested,
    AC#13).

    Requiredness is **never inferred** from names, types, or history:
    ``required_check_ids`` is supplied by the caller from explicit profile
    declarations only (§6.3, AC#5).

    ``run_succeeded`` is the one piece of run-level context the verdict needs but
    cannot see in the check ledger: whether the run reached a successful terminal
    state. The verdict is deliberately not a ``RunStatus`` (§6.5), but it must stay
    *consistent* with one — a run that FAILED/cancelled/aborted must never read
    ``accepted`` (#388). The caller derives this from the terminal status; it
    defaults ``True`` so a pure roll-up over a completed run is unchanged.

    Verdict rule (§6.2):
      - any **required** check not-executed (including a required check that
        produced *no* result at all — e.g. ``required_files`` #291) →
        ``blocked_unverified`` (AC#2), taking precedence over a plain failure so
        the incomplete-evidence signal is never hidden behind a product failure;
      - else any executed-and-failed → ``rejected``;
      - else if the run did **not** reach a successful terminal state →
        ``blocked_unverified`` (#388): zero-of-zero is zero evidence for the
        verdict exactly as it is for ``pass_rate`` (AC#1), so an aborted run with
        no failed check — or only passing checks recorded before it died — cannot
        be endorsed as ``accepted``; the framework simply never finished
        verifying it;
      - else ``accepted``.

    Not-executed results are excluded from ``executed_count``/``passed_count`` and
    from all success credit, and are always disclosed in ``unverified`` (§6.6.3).

    A check that was repaired and re-verified is first resolved to its final state
    per ``(check_id, subject)`` (§6.5, #379) — the verdict reflects the outcome
    after correction, not the union of every attempt. See ``_resolve_final_state``.
    """
    required = frozenset(required_check_ids)
    verified: list[str] = []
    failed: list[str] = []
    unverified: list[UnverifiedCheck] = []
    seen_ids: set[str] = set()

    # Resolve each producer's re-verified check to its final state first (§6.5, #379)
    # so a repaired-and-passed check no longer counts its superseded FAILED attempt.
    for r in _resolve_final_state(results):
        seen_ids.add(r.check_id)
        family = classify(r)
        if family is EvidenceFamily.EXECUTED_PASSED:
            verified.append(r.check_id)
        elif family is EvidenceFamily.EXECUTED_FAILED:
            failed.append(r.check_id)
        else:  # NOT_EXECUTED — non-creditable, always disclosed
            unverified.append(
                UnverifiedCheck(
                    check_id=r.check_id,
                    reason=_not_executed_reason(r),
                    required=r.check_id in required,
                )
            )

    # A required check that produced NO result is the strongest not-executed
    # case (#291: declared, enforced nowhere). It must be disclosed and block —
    # never silently absent (roll-up integrity, §6.6.3 / violation #3).
    for cid in sorted(required - seen_ids):
        unverified.append(
            UnverifiedCheck(check_id=cid, reason=NotExecutedReason.SUBJECT_MISSING, required=True)
        )

    required_unmet = tuple(u.check_id for u in unverified if u.required)
    executed_count = len(verified) + len(failed)
    passed_count = len(verified)

    if required_unmet:
        verdict = RunVerdict.BLOCKED_UNVERIFIED
    elif failed:
        verdict = RunVerdict.REJECTED
    elif not run_succeeded:
        # The run did not reach a successful terminal state, yet no check failed and
        # nothing required is unmet — so it would fall through to `accepted` on the
        # strength of zero (or only-passed) evidence. That is the #388 contradiction:
        # `Status: FAILED` next to `Verdict: accepted`. The run aborted before
        # verification could complete, so the framework cannot honestly claim the
        # deliverable is verified (§6.5) — disclose it as blocked_unverified, never
        # an endorsement.
        verdict = RunVerdict.BLOCKED_UNVERIFIED
    else:
        verdict = RunVerdict.ACCEPTED

    return RunVerificationSummary(
        verdict=verdict,
        verified=tuple(verified),
        failed=tuple(failed),
        unverified=tuple(unverified),
        required_unmet=required_unmet,
        executed_count=executed_count,
        passed_count=passed_count,
    )


def _dedupe(items: Collection[Any]) -> tuple[Any, ...]:
    """Order-preserving dedupe for the roll-up's reference lists.

    A ``check_id`` (or ``UnverifiedCheck``) can legitimately recur across a cycle's
    runs; the roll-up discloses each distinct value once, in first-seen order.
    """
    seen: set[Any] = set()
    out: list[Any] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return tuple(out)


def aggregate_cycle_outcome(
    run_summaries: Sequence[RunVerificationSummary],
    *,
    waived: Collection[WaivedCheck] = (),
    inert: Collection[str] = (),
) -> CycleOutcome:
    """Pure cycle-level roll-up over per-run summaries (SIP-0096 §10).

    Rolls each run's ``RunVerificationSummary`` into the durable per-cycle contract.
    Side-effect free — the ``CycleOutcome`` is constructible **only** here (AC#11),
    so no path can silently discard not-executed results.

    **Verdict precedence** mirrors the run-level rule (§6.2) so the
    incomplete-evidence signal is never hidden behind a product failure:

      - any run ``blocked_unverified`` → cycle ``blocked_unverified``;
      - else any run ``rejected`` → cycle ``rejected``;
      - else ``accepted``.

    The cycle verdict is the worst of the per-run verdicts — each run verdict
    already folded in its own required-unmet/failure state, so requiredness is not
    re-derived here. An empty cycle (no runs) rolls up to ``accepted`` (zero runs =
    zero adverse evidence — the inert default, matching the run-level empty case).

    **Evidence lists union** across the cycle's runs: framing and implementation
    runs are distinct evidence contexts, so everything executed / failed /
    not-executed is disclosed (a check that failed in one run and passed in another
    is honestly in *both* lists — runs are not collapsed), deduped to first-seen.

    ``waived`` (§6.5 operator) and ``inert`` (§9 chronic) are recorded **above** the
    evidence and passed through unchanged — a waiver never mutates a result and
    never alters the verdict. Both default empty until their Phase-3 slices wire
    them.
    """
    verified: list[str] = []
    failed: list[str] = []
    unverified: list[UnverifiedCheck] = []
    any_blocked = False
    any_rejected = False

    for s in run_summaries:
        verified.extend(s.verified)
        failed.extend(s.failed)
        unverified.extend(s.unverified)
        if s.verdict is RunVerdict.BLOCKED_UNVERIFIED:
            any_blocked = True
        elif s.verdict is RunVerdict.REJECTED:
            any_rejected = True

    if any_blocked:
        verdict = RunVerdict.BLOCKED_UNVERIFIED
    elif any_rejected:
        verdict = RunVerdict.REJECTED
    else:
        verdict = RunVerdict.ACCEPTED

    return CycleOutcome(
        verdict=verdict,
        verified=_dedupe(verified),
        failed=_dedupe(failed),
        unverified=_dedupe(unverified),
        run_count=len(run_summaries),
        inert=_dedupe(inert),
        waived=tuple(waived),
    )
