"""A request and a result survive the trip to a worker and back exactly, and a document that
isn't one is refused by name (SIP-0117 R3.3, R5.4)."""

from __future__ import annotations

import copy
import json

import pytest

from squadops.remote_execution.models import OperationStatus, RemoteOperationResult
from squadops.remote_execution.wire import (
    request_from_wire,
    request_to_wire,
    result_from_wire,
    result_to_wire,
)
from tests.unit.remote_execution.registry_contract import passing, request


def test_a_request_and_a_result_read_back_as_they_were_sent():
    """Through JSON text, as a store and a worker see them. Bug caught: a field dropped on
    one side (the scenario's digest, an assertion's context), so the worker runs against, or
    the handler reads, something other than what was sent."""
    not_run = RemoteOperationResult(
        status=OperationStatus.NOT_EXECUTED, reason="Studio is not running", dispatch_id="d-1"
    )

    asked = request()
    assert request_from_wire(json.loads(json.dumps(request_to_wire(asked)))) == asked
    for result in (passing(), not_run):
        assert result_from_wire(json.loads(json.dumps(result_to_wire(result)))) == result
    assert result_to_wire(not_run) == {
        "status": "not_executed",
        "reason": "Studio is not running",
        "records": [],
        "evidence": [],
        "provider_version": "",
        "ran_with": {},
        "dispatch_id": "d-1",
    }


def _result(**changes):
    document = result_to_wire(passing())
    for path, value in changes.items():
        target = document
        *parents, last = path.split("__")
        for step in parents:
            target = target[int(step) if step.isdigit() else step]
        if value is _ABSENT:
            del target[last]
        else:
            target[last] = value
    return document


_ABSENT = object()


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (_result(status=_ABSENT), "result lacks status"),
        (_result(status="passed"), "result.status is 'passed', and it is one of completed, "),
        (_result(verdict="pass"), "result has unknown verdict"),
        (
            _result(status=_ABSENT, reason=_ABSENT, verdict="pass"),
            "result lacks reason, status and has unknown verdict",
        ),
        (_result(records__0__outcome="ok"), r"result.records\[0\].outcome is 'ok'"),
        (_result(records__1__context=_ABSENT), r"result.records\[1\] lacks context"),
        (_result(records={}), "result.records is dict, and a list is needed"),
        (_result(ran_with={"worker": 3}), r"result.ran_with\['worker'\] is not text to text"),
        (_result(reason=None), "result.reason is NoneType, and text is needed"),
        ("completed", "result is str, and an object is needed"),
    ],
    ids=[
        "no status",
        "a status outside the vocabulary",
        "an unknown key",
        "every defect of the object named",
        "an outcome outside the vocabulary",
        "a record missing a field",
        "records that aren't a list",
        "a version that isn't text",
        "a null reason",
        "not an object",
    ],
)
def test_a_result_that_is_not_one_is_refused_by_name(document, message):
    """Bug caught: a result with no status read as completed, or an unknown outcome read as
    passed. A worker is outside the framework; what it sends is refused, never repaired."""
    with pytest.raises(ValueError, match=message):
        result_from_wire(document)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d.pop("dispatch_id"), "request lacks dispatch_id"),
        (lambda d: d["scenario"].pop("digest"), "request.scenario lacks digest"),
        (
            lambda d: d["scenario"].__setitem__("assertions", ["a", 2]),
            r"request.scenario.assertions\[1\] is int",
        ),
        (lambda d: d.__setitem__("source_files", ["a.luau"]), "request.source_files is list"),
        (lambda d: d.__setitem__("shell", "rm -rf /"), "request has unknown shell"),
    ],
    ids=["no dispatch", "a scenario with no digest", "an assertion id", "files", "an extra key"],
)
def test_a_request_that_is_not_one_is_refused_by_name(change, message):
    """Bug caught: a stored request read back with its scenario's digest filled in as empty,
    so a worker verifies against a scenario nobody approved."""
    document = copy.deepcopy(request_to_wire(request()))
    change(document)

    with pytest.raises(ValueError, match=message):
        request_from_wire(document)
