"""A remote operation's request and result as JSON, and back (SIP-0117 R3.3, R5.4).

The request crosses to a worker on another machine and its result comes back, and both are
stored between. One reading in each direction, used by the store, the routes and the worker.

Reading is strict. A document with a key missing, a key this version doesn't know, or a value
of the wrong kind raises ``ValueError`` naming it. Nothing is filled in: a result that arrives
without its status is refused, never read as some default one.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from squadops.remote_execution.models import (
    AssertionOutcome,
    AssertionRecord,
    EvidenceItem,
    OperationStatus,
    RemoteOperationRequest,
    RemoteOperationResult,
    Scenario,
)

#: The error codes of ``/api/v1/workers`` that a worker acts on. The route writes them and the
#: worker reads them, so each is named once.
ERROR_SESSION_NOT_FOUND = "WORKER_SESSION_NOT_FOUND"
ERROR_RESULT_REFUSED = "RESULT_REFUSED"
#: The error codes of ``/api/v1/remote-operations`` that a requester acts on (R5.6).
ERROR_NO_WORKER = "NO_WORKER_FOR_OPERATION"
ERROR_OPERATION_NOT_FOUND = "REMOTE_OPERATION_NOT_FOUND"

_REQUEST_KEYS = frozenset(
    {
        "contract",
        "mode",
        "provider",
        "operation",
        "location",
        "source_revision",
        "source_files",
        "scenario",
        "task_id",
        "dispatch_id",
    }
)
_SCENARIO_KEYS = frozenset({"scenario_id", "digest", "assertions"})
_RESULT_KEYS = frozenset(
    {"status", "reason", "records", "evidence", "provider_version", "ran_with", "dispatch_id"}
)
_RECORD_KEYS = frozenset({"assertion_id", "outcome", "observed", "expected", "context"})
_EVIDENCE_KEYS = frozenset({"name", "content", "media_type"})


def request_to_wire(request: RemoteOperationRequest) -> dict[str, Any]:
    return {
        "contract": request.contract,
        "mode": request.mode,
        "provider": request.provider,
        "operation": request.operation,
        "location": request.location,
        "source_revision": request.source_revision,
        "source_files": dict(request.source_files),
        "scenario": {
            "scenario_id": request.scenario.scenario_id,
            "digest": request.scenario.digest,
            "assertions": list(request.scenario.assertions),
        },
        "task_id": request.task_id,
        "dispatch_id": request.dispatch_id,
    }


def request_from_wire(document: Any) -> RemoteOperationRequest:
    body = _object(document, "request", _REQUEST_KEYS)
    scenario = _object(body["scenario"], "request.scenario", _SCENARIO_KEYS)
    return RemoteOperationRequest(
        contract=_text(body, "contract", "request"),
        mode=_text(body, "mode", "request"),
        provider=_text(body, "provider", "request"),
        operation=_text(body, "operation", "request"),
        location=_text(body, "location", "request"),
        source_revision=_text(body, "source_revision", "request"),
        source_files=_text_map(body["source_files"], "request.source_files"),
        scenario=Scenario(
            scenario_id=_text(scenario, "scenario_id", "request.scenario"),
            digest=_text(scenario, "digest", "request.scenario"),
            assertions=tuple(_text_list(scenario["assertions"], "request.scenario.assertions")),
        ),
        task_id=_named(body, "task_id", "request"),
        dispatch_id=_named(body, "dispatch_id", "request"),
    )


def result_to_wire(result: RemoteOperationResult) -> dict[str, Any]:
    return {
        "status": result.status.value,
        "reason": result.reason,
        "records": [
            {
                "assertion_id": record.assertion_id,
                "outcome": record.outcome.value,
                "observed": record.observed,
                "expected": record.expected,
                "context": record.context,
            }
            for record in result.records
        ],
        "evidence": [
            {"name": item.name, "content": item.content, "media_type": item.media_type}
            for item in result.evidence
        ],
        "provider_version": result.provider_version,
        "ran_with": dict(result.ran_with),
        "dispatch_id": result.dispatch_id,
    }


def result_from_wire(document: Any) -> RemoteOperationResult:
    body = _object(document, "result", _RESULT_KEYS)
    records = []
    for index, raw in enumerate(_list(body["records"], "result.records")):
        where = f"result.records[{index}]"
        record = _object(raw, where, _RECORD_KEYS)
        records.append(
            AssertionRecord(
                assertion_id=_text(record, "assertion_id", where),
                outcome=_member(AssertionOutcome, record["outcome"], f"{where}.outcome"),
                observed=_text(record, "observed", where),
                expected=_text(record, "expected", where),
                context=_text(record, "context", where),
            )
        )
    evidence = []
    for index, raw in enumerate(_list(body["evidence"], "result.evidence")):
        where = f"result.evidence[{index}]"
        item = _object(raw, where, _EVIDENCE_KEYS)
        evidence.append(
            EvidenceItem(
                name=_text(item, "name", where),
                content=_text(item, "content", where),
                media_type=_text(item, "media_type", where),
            )
        )
    return RemoteOperationResult(
        status=_member(OperationStatus, body["status"], "result.status"),
        reason=_text(body, "reason", "result"),
        records=tuple(records),
        evidence=tuple(evidence),
        provider_version=_text(body, "provider_version", "result"),
        ran_with=_text_map(body["ran_with"], "result.ran_with"),
        dispatch_id=_text(body, "dispatch_id", "result"),
    )


def _object(document: Any, where: str, keys: frozenset[str]) -> Mapping[str, Any]:
    if not isinstance(document, Mapping):
        raise ValueError(f"{where} is {type(document).__name__}, and an object is needed")
    missing = sorted(keys - document.keys())
    unknown = sorted(str(key) for key in document.keys() - keys)
    if missing or unknown:
        parts = []
        if missing:
            parts.append(f"lacks {', '.join(missing)}")
        if unknown:
            parts.append(f"has unknown {', '.join(unknown)}")
        raise ValueError(f"{where} {' and '.join(parts)}")
    return document


def _text(body: Mapping[str, Any], key: str, where: str) -> str:
    value = body[key]
    if not isinstance(value, str):
        raise ValueError(f"{where}.{key} is {type(value).__name__}, and text is needed")
    return value


def _named(body: Mapping[str, Any], key: str, where: str) -> str:
    """An identity: text, and never blank, since a blank one names nothing."""
    value = _text(body, key, where)
    if not value.strip():
        raise ValueError(f"{where}.{key} is blank, and it names what the request belongs to")
    return value


def _list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{where} is {type(value).__name__}, and a list is needed")
    return value


def _text_list(value: Any, where: str) -> list[str]:
    items = _list(value, where)
    for index, item in enumerate(items):
        if not isinstance(item, str):
            raise ValueError(f"{where}[{index}] is {type(item).__name__}, and text is needed")
    return items


def _text_map(value: Any, where: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} is {type(value).__name__}, and an object is needed")
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"{where}[{key!r}] is not text to text")
    return dict(value)


def _member(enum: Any, value: Any, where: str) -> Any:
    try:
        return enum(value)
    except ValueError:
        known = ", ".join(member.value for member in enum)
        raise ValueError(f"{where} is {value!r}, and it is one of {known}") from None
