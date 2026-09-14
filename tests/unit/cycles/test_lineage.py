"""The cycle series identity (the 1.8 lineage seam, ``squadops.cycles.lineage``).

The inert-detection tests (``test_inert_detection.py``) enter at ``resolve_cycle_outcome`` and
prove the walk still scopes by series; they pass unchanged across the extraction. These pin the
seam's own contract, which its second reader (SIP-0108's baseline comparison) will rely on.

Bug caught: a key that drops the request profile, so another profile's history accrues a
not-executed streak (the #684 false inert); and a lookback limit applied before the series
filter, which silently shrinks the window whenever other profiles' cycles are interleaved.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadops.cycles.lineage import SeriesKey, prior_in_series, series_for
from squadops.cycles.models import Cycle, TaskFlowPolicy

pytestmark = [pytest.mark.domain_orchestration]

_T0 = datetime(2026, 9, 13, 12, 0, 0, tzinfo=UTC)


def _cycle(
    cycle_id: str,
    hour: int,
    *,
    project: str = "group_run",
    squad: str = "full-38",
    request_profile: str | None = "validated-fullstack",
) -> Cycle:
    return Cycle(
        cycle_id=cycle_id,
        project_id=project,
        created_at=_T0 + timedelta(hours=hour),
        created_by="test",
        prd_ref=None,
        squad_profile_id=squad,
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential", gates=()),
        build_strategy="fresh",
        request_profile=request_profile,
        framework_version="1.8.0",
        framework_git_sha=f"sha{hour}",
    )


def test_the_key_is_project_squad_and_request_profile_and_nothing_else():
    """Code lineage (#80) differs across these two and does not split the series."""
    a, b = _cycle("cyc_a", 0), _cycle("cyc_b", 5)
    assert (
        series_for(a) == series_for(b) == SeriesKey("group_run", "full-38", "validated-fullstack")
    )


@pytest.mark.parametrize(
    "other",
    [
        {"project": "other_project"},
        {"squad": "lite"},
        {"request_profile": "selftest"},
        {"request_profile": None},
    ],
    ids=["project", "squad-profile", "request-profile", "request-profile-unset"],
)
def test_any_differing_field_is_another_series(other):
    assert series_for(_cycle("cyc_a", 0)) != series_for(_cycle("cyc_b", 0, **other))


def test_prior_members_come_back_in_the_order_given_and_nothing_else_does():
    perspective = _cycle("cyc_now", 10)
    newest_first = [
        _cycle("cyc_later", 11),  # created after: not prior
        perspective,  # itself
        _cycle("cyc_same_instant", 10),  # not strictly before
        _cycle("cyc_9", 9),
        _cycle("cyc_other_squad", 8, squad="lite"),
        _cycle("cyc_unset_profile", 7, request_profile=None),
        _cycle("cyc_6", 6),
    ]

    assert [c.cycle_id for c in prior_in_series(perspective, newest_first)] == ["cyc_9", "cyc_6"]


def test_the_limit_is_a_window_of_the_series_not_of_the_candidates():
    perspective = _cycle("cyc_now", 20)
    interleaved = []
    for hour in range(19, 9, -1):
        interleaved.append(_cycle(f"cyc_lite_{hour}", hour, squad="lite"))
        interleaved.append(_cycle(f"cyc_{hour}", hour))

    window = prior_in_series(perspective, interleaved, limit=3)

    assert [c.cycle_id for c in window] == ["cyc_19", "cyc_18", "cyc_17"]


def test_an_unset_request_profile_is_a_series_of_its_own():
    """Cycles from before ``request_profile`` existed group with each other only."""
    perspective = _cycle("cyc_now", 5, request_profile=None)
    candidates = [_cycle("cyc_old", 1, request_profile=None), _cycle("cyc_set", 2)]
    assert [c.cycle_id for c in prior_in_series(perspective, candidates)] == ["cyc_old"]
