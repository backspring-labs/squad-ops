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


def aggregate_verification(
    results: Sequence[CheckResult],
    required_check_ids: Collection[str] = (),
) -> RunVerificationSummary:
    """Pure aggregation choke point (SIP-0096 §6.2, §6.4).

    Classifies every recorded result into an evidence family and computes the run
    verdict. Side-effect free — no persistence, no dispatch (architecture-tested,
    AC#13).

    Requiredness is **never inferred** from names, types, or history:
    ``required_check_ids`` is supplied by the caller from explicit profile
    declarations only (§6.3, AC#5).

    Verdict rule (§6.2):
      - any **required** check not-executed (including a required check that
        produced *no* result at all — e.g. ``required_files`` #291) →
        ``blocked_unverified`` (AC#2), taking precedence over a plain failure so
        the incomplete-evidence signal is never hidden behind a product failure;
      - else any executed-and-failed → ``rejected``;
      - else ``accepted``.

    Not-executed results are excluded from ``executed_count``/``passed_count`` and
    from all success credit, and are always disclosed in ``unverified`` (§6.6.3).
    """
    required = frozenset(required_check_ids)
    verified: list[str] = []
    failed: list[str] = []
    unverified: list[UnverifiedCheck] = []
    seen_ids: set[str] = set()

    for r in results:
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
