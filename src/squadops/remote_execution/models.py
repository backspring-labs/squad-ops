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
    """A frozen scenario: its identity, its digest, and the assertions it declares. The
    digest is taken before development, so a pass means the scenario that was approved."""

    scenario_id: str
    digest: str
    assertions: tuple[str, ...]


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
    #: The dispatch this request belongs to, echoed in the result (#2932's convention).
    dispatch_id: str = ""


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


def result_defects(request: RemoteOperationRequest, result: RemoteOperationResult) -> list[str]:
    """Why ``result`` can't be read as the answer to ``request``, or ``[]``.

    A provider is outside the framework, so what it returns is checked before it is believed:
    a stale echo, a completion with no reason given for not completing, a record for an
    assertion the scenario never declared, or two records for one assertion.
    """
    defects: list[str] = []
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
