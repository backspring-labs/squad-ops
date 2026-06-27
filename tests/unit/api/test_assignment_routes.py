"""Unit tests for the SIP-0089 §2.7 assignment route DTOs.

These deliberately avoid `TestClient` (blocked locally per #217) and test the
serialization layer directly: the `Assignment` <-> wire-DTO mapping and the
D7/§11.4 reserve-buffer defaults applied at create time. The HTTP wiring itself
(routing, 404 envelope) is exercised by the CLI command tests via an injected
client.

Each test answers: what bug would it catch?
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from squadops.api.routes.assignments import (
    AssignmentCreate,
    AssignmentResponse,
)
from squadops.runtime.models import Assignment, DutyWindow

pytestmark = [pytest.mark.domain_api]

WIN_START = datetime(2026, 6, 24, 1, 0, tzinfo=UTC)
WIN_END = datetime(2026, 6, 24, 6, 0, tzinfo=UTC)


def _assignment(**overrides) -> Assignment:
    base = dict(
        assignment_id="a-1",
        agent_id="max",
        assignment_type="duty",
        assigned_role="support",
        priority=10,
        strictness="hard",
        active_window=DutyWindow(start=WIN_START, end=WIN_END, timezone="America/New_York"),
        reserve_before_window=timedelta(minutes=15),
        reserve_after_window=timedelta(minutes=10),
        recall_policy="graceful",
        graceful_window=timedelta(minutes=5),
        missed_window_policy="require_operator_review",
        allowed_off_window_modes=("ambient", "cycle"),
        active=True,
    )
    base.update(overrides)
    return Assignment(**base)  # type: ignore[arg-type]


def _create_from_response(resp: AssignmentResponse) -> AssignmentCreate:
    """Rebuild a create-request from a response, passing reserve buffers
    explicitly so no defaults are re-applied — this makes the trip lossless."""
    return AssignmentCreate(
        agent_id=resp.agent_id,
        assigned_role=resp.assigned_role,
        window_start=resp.active_window.start,
        window_end=resp.active_window.end,
        timezone=resp.active_window.timezone,
        assignment_id=resp.assignment_id,
        assignment_type=resp.assignment_type,
        priority=resp.priority,
        strictness=resp.strictness,
        reserve_before_window_seconds=resp.reserve_before_window_seconds,
        reserve_after_window_seconds=resp.reserve_after_window_seconds,
        recall_policy=resp.recall_policy,
        graceful_window_seconds=resp.graceful_window_seconds,
        missed_window_policy=resp.missed_window_policy,
        allowed_off_window_modes=resp.allowed_off_window_modes,
        active=resp.active,
    )


def test_dto_round_trip_preserves_all_fields():
    """Bug class: a dropped or mistyped field in `from_domain`/`to_domain` (e.g.
    forgetting the timezone, coercing the tuple to a list, or losing a reserve
    buffer) would silently corrupt an assignment as it crosses the API. A full
    round-trip equality is the only assertion that catches every such omission."""
    original = _assignment()
    rebuilt = _create_from_response(AssignmentResponse.from_domain(original)).to_domain()
    assert rebuilt == original
    # Spot-check the easy-to-lose nested/typed members explicitly.
    assert rebuilt.active_window.timezone == "America/New_York"
    assert rebuilt.allowed_off_window_modes == ("ambient", "cycle")
    assert isinstance(rebuilt.allowed_off_window_modes, tuple)
    assert rebuilt.reserve_before_window == timedelta(minutes=15)


def test_response_serializes_timedeltas_as_integer_seconds():
    """Bug class: using `.seconds` instead of `.total_seconds()`, or emitting a
    `timedelta`/float, would break every JSON consumer. Pin the exact integers."""
    resp = AssignmentResponse.from_domain(_assignment())
    assert resp.reserve_before_window_seconds == 900
    assert resp.reserve_after_window_seconds == 600
    assert resp.graceful_window_seconds == 300
    assert isinstance(resp.reserve_before_window_seconds, int)


@pytest.mark.parametrize(
    ("strictness", "expected_before"),
    [
        ("hard", timedelta(minutes=15)),
        ("soft", timedelta(0)),
    ],
)
def test_create_applies_reserve_defaults_when_omitted(strictness, expected_before):
    """Bug class (§11.4/D7): if `to_domain` failed to apply the strictness default
    when the operator omits the reserve fields, a hard duty would persist with a
    0-minute buffer and the §2.5 recruitment guard would never gate it."""
    body = AssignmentCreate(
        agent_id="max",
        assigned_role="support",
        window_start=WIN_START,
        window_end=WIN_END,
        strictness=strictness,
    )
    domain = body.to_domain()
    assert domain.reserve_before_window == expected_before
    assert domain.reserve_after_window == timedelta(0)


def test_create_explicit_zero_reserve_is_not_overridden_by_default():
    """Bug class: distinguishing 'omitted' (apply default) from 'explicitly 0'
    (honor it) matters — a hard duty that the operator deliberately set to a
    0-minute buffer must NOT silently get the 15-minute default back."""
    body = AssignmentCreate(
        agent_id="max",
        assigned_role="support",
        window_start=WIN_START,
        window_end=WIN_END,
        strictness="hard",
        reserve_before_window_seconds=0,
    )
    assert body.to_domain().reserve_before_window == timedelta(0)


def test_create_generates_id_when_omitted():
    """Bug class: the upsert is keyed by assignment_id; if create left it empty,
    every created assignment would collide on the same row."""
    body = AssignmentCreate(
        agent_id="max",
        assigned_role="support",
        window_start=WIN_START,
        window_end=WIN_END,
    )
    assert body.to_domain().assignment_id


@pytest.mark.parametrize(
    "kwargs",
    [
        {"window_start": WIN_END, "window_end": WIN_START},  # inverted
        {"window_start": WIN_START, "window_end": WIN_START},  # empty
    ],
)
def test_create_rejects_non_positive_window(kwargs):
    """Bug class: an inverted or empty window passes type-checking but is rejected
    by the DB CHECK (§2.2/D3) as a 500. Validating it as a 422 at the DTO turns a
    server error into a clear client error."""
    with pytest.raises(ValidationError):
        AssignmentCreate(agent_id="max", assigned_role="support", **kwargs)


def test_create_rejects_negative_reserve():
    """Bug class: a negative reserve buffer would make `window_state` open the
    reserve window *after* the duty start — nonsensical geometry the guard relies
    on. Reject it at the edge."""
    with pytest.raises(ValidationError):
        AssignmentCreate(
            agent_id="max",
            assigned_role="support",
            window_start=WIN_START,
            window_end=WIN_END,
            reserve_before_window_seconds=-60,
        )
