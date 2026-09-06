"""#381: ``TaskResult.status`` is one typed vocabulary — ``TaskResultStatus`` — not an
UPPERCASE bare-string twin of the lowercase capability-layer ``TaskStatus``.

The footgun: eleven sites compared ``result.status`` against ``"SUCCEEDED"`` and were held
together by everyone remembering never to reach for the obviously-named enum; the moment
someone wrote ``result.status == TaskStatus.SUCCEEDED`` it would have been silently
``False`` forever. Producers and comparisons now use the member; the wire string becomes
the member at ``from_dict``, the one boundary.
"""

from __future__ import annotations

import json

import pytest

from squadops.tasks.models import TaskResult, TaskResultStatus

pytestmark = [pytest.mark.domain_agents]


@pytest.mark.parametrize("wire", ["SUCCEEDED", "FAILED", "CANCELED"])
def test_the_wire_string_becomes_the_member_at_the_boundary(wire):
    result = TaskResult.from_dict({"task_id": "t", "status": wire, "outputs": {}})
    assert result.status is TaskResultStatus(wire)
    # and still compares as the string every existing caller hands it
    assert result.status == wire


def test_an_unknown_wire_status_is_refused_not_carried():
    """Bug caught: a status nothing downstream compares equal to — ``"CANCELLED"`` (two
    Ls) from a mismatched producer — carried silently as a fourth state."""
    with pytest.raises(ValueError, match="not a wire value"):
        TaskResult.from_dict({"task_id": "t", "status": "CANCELLED"})


def test_the_member_serializes_as_the_wire_string():
    """Rule 1 of #559, applied here: no transport change."""
    result = TaskResult(task_id="t", status=TaskResultStatus.FAILED, error="x")
    payload = json.loads(json.dumps(result.to_dict()))
    assert payload["status"] == "FAILED"
    assert TaskResult.from_dict(payload).status is TaskResultStatus.FAILED


def test_the_enum_is_not_the_lowercase_task_status():
    """The two vocabularies must never compare across — the whole reason this enum exists
    instead of adopting ``TaskStatus``."""
    from squadops.capabilities.models import TaskStatus

    assert TaskResultStatus.SUCCEEDED != TaskStatus.SUCCEEDED
    assert {m.value for m in TaskResultStatus} == {"SUCCEEDED", "FAILED", "CANCELED"}
