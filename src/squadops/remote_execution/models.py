"""What a remote operation is asked for and what it returns (SIP-0117 R3.3, R3.7, R4.4).

Engine-neutral. A handler asks the remote-execution port to run one operation of a provider
for a capability contract in a verification mode, against a source revision, with a frozen
scenario. The provider behind the port (an editor on a worker, for example) owns everything
about the engine: its tools, its harness, its reader. Nothing here names one.

Three things are kept apart, because each means something different to a verdict:

- an assertion that **executed** (``passed`` or ``failed``);
- an assertion that **did not execute** (``missing``, ``setup_failed``, ``unsupported_input``,
  ``wrong_context``). Only ``failed`` is an executed behavioural failure;
- an operation that **did not run at all** (``not_executed``, before the session started) or
  was **interrupted** (after it started). Neither reads as a failure or a pass.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

#: The artifact types of an operation's evidence: the assertion records, and the provider's
#: own items (a console log, a manifest). They describe one run of the operation, so a later
#: run of the same task supersedes them, and they are never the product's files.
ASSERTION_RECORDS_ARTIFACT_TYPE = "remote_operation_assertions"
OPERATION_EVIDENCE_ARTIFACT_TYPE = "remote_operation_evidence"
OPERATION_ARTIFACT_TYPES = frozenset(
    {ASSERTION_RECORDS_ARTIFACT_TYPE, OPERATION_EVIDENCE_ARTIFACT_TYPE}
)

#: #3049, with #3118: the most a request's staged tree may hold, in UTF-8 bytes. It travels
#: inline, is stored with the operation and is sent again at every claim. It is the evaluation
#: tree's own limit (``context_assembly.ARTIFACT_CONTENTS_LIMIT_BYTES``, held equal by a test),
#: so a tree a run carries whole is never refused here. Measured on z_tower-ascension at
#: ``0beaac0`` (2026-11-16): its 2.3 MB of source and config, and 3.06 MB as a request on the wire.
REQUEST_TREE_LIMIT_BYTES = 4 * 1024 * 1024
#: #3049: the most one evidence item may hold, in UTF-8 bytes. Measured on the real Studio
#: (2026-11-16): a play log of 197 bytes and a console tail of 6,936. The runner keeps at most
#: 20,000 characters of console, 80,000 bytes at the most, so the limit is about three times that.
EVIDENCE_ITEM_LIMIT_BYTES = 256 * 1024


class AssertionOutcome(StrEnum):
    """One assertion's result (R3.7)."""

    PASSED = "passed"
    FAILED = "failed"
    #: An assertion the scenario declares produced no record.
    MISSING = "missing"
    #: The scenario's fixtures didn't establish.
    SETUP_FAILED = "setup_failed"
    #: The scenario needs input the provider doesn't give.
    UNSUPPORTED_INPUT = "unsupported_input"
    #: It ran in a context other than the one it was declared for.
    WRONG_CONTEXT = "wrong_context"

    @property
    def executed(self) -> bool:
        """Whether the assertion ran and produced a verdict. Only these two did."""
        return self in (AssertionOutcome.PASSED, AssertionOutcome.FAILED)


class OperationStatus(StrEnum):
    """Whether the operation ran (R3.3)."""

    COMPLETED = "completed"
    #: Failed before execution began: staging, sync, verification of the tested state, or no
    #: provider to run it.
    NOT_EXECUTED = "not_executed"
    #: Interrupted after the session started.
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class Scenario:
    """A frozen scenario: its identity, its digest, the assertions it declares, the one that
    is its criterion's, and its declaration's text (#3044). The digest is taken before
    development, so a pass means the scenario that was approved. The provider runs the text it
    is handed only when that text's digest is this one (``scenario.handed_scenario_defects``).
    """

    scenario_id: str
    digest: str
    assertions: tuple[str, ...]
    #: The assertion the criterion names: it must execute and fail on the baseline, and pass on
    #: the candidate. Every other declared assertion is a precondition.
    named_assertion: str
    #: The declaration's canonical text, as frozen (``scenario.canonical_text``).
    document: str


class ReadingSide(StrEnum):
    """Which tree a reading was taken on (#3044 §4)."""

    #: The accepted baseline, with the criterion's scenario file laid over it.
    BASELINE = "baseline"
    #: The candidate the work produced.
    CANDIDATE = "candidate"


def acceptance_task_id(
    campaign_id: str, increment_id: str, criterion_id: str, side: ReadingSide
) -> str:
    """The task a scenario reading is asked for under, by the runtime itself (#3053, #3044): one
    per criterion and side. The registry stops a task's older sends' operations when a newer
    send asks, so two criteria, or a criterion's baseline and candidate, never stop each other;
    a re-evaluation (a new dispatch id) stops the older one's. Core's, so the executor's
    baseline step and acceptance's delivery readings name one task the same way."""
    return f"campaign:{campaign_id}:{increment_id}:{criterion_id}:{side.value}"


@dataclass(frozen=True)
class RemoteOperationRequest:
    """One operation to run. Its inputs are named, never a live tree."""

    contract: str
    mode: str
    provider: str
    operation: str
    #: Where the operation runs (SIP-0116 §8): ``agent``, ``sandbox`` or ``worker``.
    location: str
    #: The revision of the candidate tree the operation verifies.
    source_revision: str
    #: The candidate tree's files, path to content, as staged for the provider.
    source_files: Mapping[str, str]
    scenario: Scenario
    #: The task the operation verifies for.
    task_id: str
    #: The send of that task this request belongs to (#2932): the runtime mints one per
    #: dispatch, and the result echoes it. A task's operation is asked for once per send, and a
    #: newer send's request supersedes an older one's (SIP-0117 R5.6).
    dispatch_id: str


@dataclass(frozen=True)
class AssertionRecord:
    """One structured record per assertion (R3.7). A reader reads only these: console prose
    never establishes a pass."""

    assertion_id: str
    outcome: AssertionOutcome
    observed: str = ""
    expected: str = ""
    #: Where it ran: ``server``, ``client``, or a provider's own name for it.
    context: str = ""


@dataclass(frozen=True)
class EvidenceItem:
    """One piece of the operation's evidence: a console log, a manifest, a digest."""

    name: str
    content: str
    media_type: str = "text/plain"


@dataclass(frozen=True)
class RemoteOperationResult:
    """What the provider returned for one request."""

    status: OperationStatus
    #: Why, when the operation didn't complete. Required then, and empty otherwise.
    reason: str = ""
    records: tuple[AssertionRecord, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()
    #: The provider's version, and the versions of what it ran with (a worker, an editor, a
    #: tool schema digest). Recorded in the evidence, since provider code can't be kept with
    #: a cycle (R4.6).
    provider_version: str = ""
    ran_with: Mapping[str, str] = field(default_factory=dict)
    #: The request's ``dispatch_id``, echoed. A result that echoes another is stale.
    dispatch_id: str = ""
    #: #3045: no worker took it. None served or reached the operation when it was asked for,
    #: or none claimed it before its requester's wait ran out. A fact about the workers, never
    #: about the work: set only by a requester, from the registry's ``NoWorker`` or its own
    #: wait, and never on a result a worker returned. A worker that claimed it and then went
    #: silent is not this (its lease lapsing is ``interrupted``; whether it ran is unknown).
    unavailable: bool = False
    #: #3192: a worker took it, and its tool couldn't run it now, for a reason of the worker's
    #: own environment and never of the request: the tool not in front, not the version it was
    #: proved on, busy, or not reset to a known state. Set only by a worker (the provider, or the
    #: serving loop for a tool it couldn't reset), and only on ``not_executed``: nothing ran, so
    #: building the candidate again changes nothing. A fact about the worker, never the work,
    #: which the Campaign reads as it reads ``unavailable``.
    tool_unready: bool = False


def request_size_defect(request: RemoteOperationRequest) -> str | None:
    """Why ``request`` is too large to send, or ``None`` (#3049). Nothing is truncated: a request
    past the limit is refused whole, naming its size, the limit and its largest files."""
    sizes = {path: len(text.encode()) for path, text in request.source_files.items()}
    total = sum(sizes.values())
    if total <= REQUEST_TREE_LIMIT_BYTES:
        return None
    largest = sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return (
        f"the request's staged tree is {total:,} bytes over {len(sizes)} files, past the "
        f"{REQUEST_TREE_LIMIT_BYTES:,}-byte limit a remote operation carries, so nothing was "
        "sent. Its largest files: " + ", ".join(f"{path} ({size:,})" for path, size in largest)
    )


def evidence_size_defects(result: RemoteOperationResult) -> list[str]:
    """Each evidence item past :data:`EVIDENCE_ITEM_LIMIT_BYTES`, named (#3049)."""
    return [
        f"evidence item {item.name!r} is {size:,} bytes, past the "
        f"{EVIDENCE_ITEM_LIMIT_BYTES:,}-byte limit"
        for item in result.evidence
        if (size := len(item.content.encode())) > EVIDENCE_ITEM_LIMIT_BYTES
    ]


def result_defects(request: RemoteOperationRequest, result: RemoteOperationResult) -> list[str]:
    """Why ``result`` can't be read as the answer to ``request``, or ``[]``.

    A provider is outside the framework, so what it returns is checked before it is believed:
    a stale echo, a completion with no reason given for not completing, a record for an
    assertion the scenario never declared, two records for one assertion, or an evidence item
    past its limit (#3049).
    """
    defects: list[str] = evidence_size_defects(result)
    if result.dispatch_id != request.dispatch_id:
        defects.append(
            f"the result echoes dispatch {result.dispatch_id!r}, and the request was "
            f"{request.dispatch_id!r}"
        )
    if result.status is not OperationStatus.COMPLETED and not result.reason.strip():
        defects.append(f"the operation is {result.status.value} and gives no reason")
    if result.status is not OperationStatus.COMPLETED and result.records:
        defects.append(f"the operation is {result.status.value} and still returned records")
    declared = set(request.scenario.assertions)
    if request.scenario.named_assertion not in declared:
        defects.append(
            f"the request names {request.scenario.named_assertion!r} as its criterion's "
            "assertion, and its scenario doesn't declare it"
        )
    seen: set[str] = set()
    for record in result.records:
        if record.assertion_id not in declared:
            defects.append(
                f"a record for {record.assertion_id!r}, which the scenario doesn't declare"
            )
        elif record.assertion_id in seen:
            defects.append(f"more than one record for {record.assertion_id!r}")
        seen.add(record.assertion_id)
    return defects


def outcomes_by_assertion(
    request: RemoteOperationRequest, result: RemoteOperationResult
) -> dict[str, AssertionRecord]:
    """Every assertion the scenario declares, with its record. A declared assertion with no
    record is ``missing`` (R3.7): the absence of a record is never read as a pass."""
    recorded = {record.assertion_id: record for record in result.records}
    return {
        assertion_id: recorded.get(assertion_id)
        or AssertionRecord(assertion_id, AssertionOutcome.MISSING)
        for assertion_id in request.scenario.assertions
    }


def reading_unavailable(reading: Mapping | None) -> bool:
    """Whether a stored reading's operation was taken by no worker (#3045). A reading kept
    before the field was written carries no key, and reads as not flagged: it keeps the routing
    it had then (a delivery gap it leaves is repaired, not retried)."""
    return reading is not None and reading.get("unavailable") is True


def reading_for_want_of_a_worker(reading: Mapping | None) -> bool:
    """Whether a stored reading went unread for the workers' sake, never the work's: no worker
    took its operation (#3045), or the one that took it found its tool not ready to run it
    (#3192). A reading kept before either key was written reads as not flagged, as
    :func:`reading_unavailable` says."""
    return reading_unavailable(reading) or (
        reading is not None and reading.get("tool_unready") is True
    )


def records_document(
    request: RemoteOperationRequest,
    result: RemoteOperationResult,
    side: ReadingSide,
    *,
    not_staged: tuple[str, ...],
    **operation: str,
) -> dict[str, object]:
    """One reading as the assertion-records artifact (``ASSERTION_RECORDS_ARTIFACT_TYPE``)
    holds it (#3044 §4): the side and revision it was taken on, the scenario with its digest
    and named assertion, the operation's status, and one record per declared assertion when it
    completed. ``operation`` adds what the caller knows of who supplied the operation (the
    handler's skillset and its digest). Every lane that keeps a reading writes it here, so a
    reader reads one shape.

    ``not_staged`` names the paths of the tree being judged that the request didn't carry (the
    wire stages text only). The revision binds to what was staged, so a reading on a tree that
    lacks them says so here, and nothing reads it as the whole tree's."""
    return {
        "side": side.value,
        "contract": request.contract,
        "mode": request.mode,
        "provider": request.provider,
        "operation": request.operation,
        "location": request.location,
        **operation,
        "source_revision": request.source_revision,
        "not_staged": sorted(not_staged),
        "scenario": {
            "scenario_id": request.scenario.scenario_id,
            "digest": request.scenario.digest,
            "assertions": list(request.scenario.assertions),
            "named_assertion": request.scenario.named_assertion,
            "document": request.scenario.document,
        },
        "named_assertion": request.scenario.named_assertion,
        "status": result.status.value,
        "reason": result.reason,
        # #3045: written on every reading, so "not flagged" is read, never inferred.
        "unavailable": result.unavailable,
        # #3192: written on every reading too, for the same reason.
        "tool_unready": result.tool_unready,
        "provider_version": result.provider_version,
        "ran_with": dict(result.ran_with),
        "assertions": [
            {
                "assertion_id": record.assertion_id,
                "outcome": record.outcome.value,
                "observed": record.observed,
                "expected": record.expected,
                "context": record.context,
            }
            for record in outcomes_by_assertion(request, result).values()
        ]
        if result.status is OperationStatus.COMPLETED
        else [],
    }
