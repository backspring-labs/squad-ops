"""An increment's acceptance (SIP-0109 §8.1–§8.3; #1707, #1796).

Discrimination runs through the real test runner (``run_generated_tests``: pytest in an isolated
directory, its real ``-q --tb=short`` output parsed into rows by the runner's own parser), on a
baseline tree and a candidate tree: what the runner reports is what is judged.
"""

from __future__ import annotations

import asyncio

import pytest

from squadops.campaigns.acceptance import (
    DiscriminationReason,
    FrozenResult,
    Held,
    IncrementVerdict,
    RouteResult,
    TreeRun,
    accumulated_acceptance,
    discrimination,
    increment_acceptance,
    route_rendering,
)
from squadops.capabilities.handlers.test_runner import run_generated_tests

_BASELINE_APP = [{"path": "app.py", "content": "def join(capacity, joined):\n    return 200\n"}]
_CANDIDATE_APP = [
    {
        "path": "app.py",
        "content": "def join(capacity, joined):\n    return 409 if joined >= capacity else 200\n",
    },
    {"path": "capacity.py", "content": "def limit():\n    return 2\n"},
]
_TESTS = [
    # C2: new behaviour through the app's surface — fails on the baseline as an assertion.
    {
        "path": "criteria/test_C2.py",
        "content": "from app import join\n\ndef test_a_full_run_refuses_a_join():\n    assert join(2, 2) == 409\n",
    },
    # C9: imports a module only the candidate has — on the baseline that is setup, not behaviour.
    {
        "path": "criteria/test_C9.py",
        "content": "from capacity import limit\n\ndef test_the_limit_is_two():\n    assert limit() == 2\n",
    },
    # C1: already true on the baseline — it discriminates nothing.
    {
        "path": "criteria/test_C1.py",
        "content": "from app import join\n\ndef test_an_open_run_accepts_a_join():\n    assert join(2, 0) == 200\n",
    },
]


@pytest.fixture(scope="module")
def runs() -> dict[str, tuple[TreeRun, TreeRun]]:
    """Each criterion's file run alone by the real runner, on the baseline and on the candidate."""

    async def per_criterion():
        out = {}
        for test in _TESTS:
            baseline = await run_generated_tests(_BASELINE_APP, [test])
            candidate = await run_generated_tests(_CANDIDATE_APP, [test])
            out[test["path"]] = (TreeRun.from_runner(baseline), TreeRun.from_runner(candidate))
        return out

    return asyncio.run(per_criterion())


def test_one_collection_error_abandons_every_other_criterion_in_a_shared_run():
    """Why each criterion runs alone (§8.4). Bug caught: criteria evaluated in one session, where
    C9's missing module stops pytest before C2 runs, and C2 reads as never failing."""

    async def shared():
        return TreeRun.from_runner(await run_generated_tests(_BASELINE_APP, _TESTS))

    together = asyncio.run(shared())
    assert together.failed_titles("criteria/test_C2.py") == set()  # C2 never ran
    assert together.suite_died("criteria/test_C9.py")


@pytest.mark.parametrize(
    ("criterion", "path", "met", "reason"),
    [
        ("C2", "criteria/test_C2.py", True, DiscriminationReason.DISCRIMINATES),
        ("C9", "criteria/test_C9.py", False, DiscriminationReason.ONLY_SETUP_FAILURES),
        ("C1", "criteria/test_C1.py", False, DiscriminationReason.NO_BASELINE_FAILURE),
    ],
)
def test_discrimination_reads_the_real_runners_rows(runs, criterion, path, met, reason):
    """§8.2 on real pytest output. Bug caught: an import error on the baseline counted as the new
    behaviour being absent — a 'discriminating' test that proves only that a module is new."""
    baseline, candidate = runs[path]

    result = discrimination(criterion, path, baseline, candidate)

    assert (result.met, result.reason) == (met, reason)
    if met:
        assert result.discriminating == ("test_a_full_run_refuses_a_join",)


def test_a_test_that_fails_on_both_trees_discriminates_nothing(runs):
    baseline, _ = runs["criteria/test_C2.py"]
    assert discrimination("C2", "criteria/test_C2.py", baseline, baseline).reason is (
        DiscriminationReason.FAILS_ON_CANDIDATE
    )


def test_a_criterion_the_runner_never_reached_is_not_run():
    never = TreeRun(executed=False)
    assert discrimination("C2", "criteria/test_C2.py", never, never).reason is (
        DiscriminationReason.NOT_RUN
    )


# --- §8.1 ----------------------------------------------------------------------------------------


def test_a_frozen_criterion_holds_fails_or_is_blocked_never_silently_passes():
    """§8.1: a missing or unreadable bundle is blocked_unverified, never a pass. Bug caught: a
    criterion whose bundle vanished counted as held."""
    ok = TreeRun(executed=True)
    broke = TreeRun(executed=True, failures=({"file": "criteria/C2.test.jsx", "title": "refuses"},))
    import_broke = TreeRun(
        executed=True,
        failures=({"file": "criteria/C3.test.jsx", "title": "", "suite_level": True},),
    )

    results = accumulated_acceptance(
        "inc_2",
        "cand_abc",
        {
            "C1": ("addr1", "criteria/C1.test.jsx"),
            "C2": ("addr2", "criteria/C2.test.jsx"),
            "C3": ("addr3", "criteria/C3.test.jsx"),
            "C4": (None, "criteria/C4.test.jsx"),
            "C5": ("addr5", "criteria/C5.test.jsx"),
        },
        {"C1": ok, "C2": broke, "C3": import_broke, "C4": ok, "C5": TreeRun(executed=False)},
    )

    assert [(r.criterion_id, r.held) for r in results] == [
        ("C1", Held.HELD),
        ("C2", Held.BROKEN),
        ("C3", Held.BROKEN),  # the candidate broke what the frozen test imports: a break
        ("C4", Held.BLOCKED_UNVERIFIED),
        ("C5", Held.BLOCKED_UNVERIFIED),
    ]
    assert results[0] == FrozenResult("inc_2", "C1", "cand_abc", "addr1", Held.HELD)


# --- §8.3 ----------------------------------------------------------------------------------------


def test_a_route_renders_when_its_views_root_anchor_does():
    """§8.3 as read on a live page (§24p). Bugs caught: a correct list page failed because its
    empty state and its rows cannot both show (the strict reading), or a page that rendered
    something other than its view passed."""
    results = route_rendering(
        {
            # Roll 4's list page, read empty: the root and the empty state, no rows.
            "/": ("runs-list-view", "run-row", "empty-state"),
            "/runs/:run_id": ("run-detail-view", "capacity-status"),
        },
        {
            "/": frozenset({"runs-list-view", "empty-state", "create-run-link"}),
            "/runs/:run_id": frozenset({"capacity-status"}),  # not the detail view
        },
    )
    assert results == (
        RouteResult("/", Held.HELD, (), ("run-row",)),
        RouteResult("/runs/:run_id", Held.BROKEN, ("run-detail-view",)),
    )
    assert route_rendering({"/new": ("x",)}, {}) == (RouteResult("/new", Held.BLOCKED_UNVERIFIED),)


# --- the increment -------------------------------------------------------------------------------


def test_the_increment_is_accepted_only_when_everything_holds(runs):
    met = discrimination("C2", "criteria/test_C2.py", *runs["criteria/test_C2.py"])
    setup_only = discrimination("C9", "criteria/test_C9.py", *runs["criteria/test_C9.py"])
    held = FrozenResult("inc", "B1", "c", "a", Held.HELD)
    blocked = FrozenResult(
        "inc", "B2", "c", None, Held.BLOCKED_UNVERIFIED, "the verifier bundle is missing"
    )
    route_ok = RouteResult("/", Held.HELD)

    assert increment_acceptance((met,), (held,), (route_ok,)).verdict is IncrementVerdict.ACCEPTED
    rejected = increment_acceptance((met, setup_only), (held, blocked), (route_ok,))
    assert rejected.verdict is IncrementVerdict.REJECTED
    assert rejected.unmet == ("criterion C9: only_setup_failures",)
    only_blocked = increment_acceptance((met,), (held, blocked), (route_ok,))
    assert (only_blocked.verdict, only_blocked.blocked) == (
        IncrementVerdict.BLOCKED_UNVERIFIED,
        ("frozen B2: the verifier bundle is missing",),
    )
