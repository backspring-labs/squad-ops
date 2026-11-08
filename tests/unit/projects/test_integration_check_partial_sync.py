"""The integration check over a sync that fails part-way (SIP-0112 H.30; the outside review of
PR #2862's check, item 3).

Over the table-driven world of ``test_unintegrated_increments``: two accepted increments, each with
its own run's contribution, so one row can stand ``merged_not_synced`` while another is pending.
The clone is a table of ancestry, and the forge refuses every read, as one that answers 503 does.
The Project's writes are kept as Postgres keeps them (``tests.fixtures.project_writes``).
"""

from __future__ import annotations

import dataclasses

import pytest

from squadops.cycles.models import Project
from squadops.ports.projects.review_request import ReviewRequestFailed
from squadops.projects.development_configuration import parse_configuration
from squadops.projects.integration_check import check_integration
from squadops.projects.models import CheckoutTree, ProjectLifecycleStatus, ProjectSource
from tests.fixtures.project_writes import KeyedProjectWrites
from tests.fixtures.shared_contract.repository import recorded
from tests.unit.api.test_campaign_calibration_record import PROJECT
from tests.unit.api.test_unintegrated_increments import _goal_set_world, _per_run
from tests.unit.campaigns.builders import T0

BASE = "u" * 40
UPSTREAM = "w" * 40


class _Records:
    def __init__(self, contributions: list) -> None:
        self.project = Project(
            project_id=PROJECT, name="Tally", description="", created_at=T0,
            lifecycle_status=ProjectLifecycleStatus.READY,
            source=ProjectSource("https://forge.example.invalid/o/tally", "refs/heads/main",
                                 "review_request"),
            development_baseline_commit=BASE, integrated_upstream_commit=BASE,
        )  # fmt: skip
        self.held, self.syncs = contributions, []
        self.configuration = parse_configuration(recorded("development_configuration", "valid"))

    async def get_project(self, project_id):
        return self.project

    async def contributions(self, project_id):
        return list(self.held)

    async def source_syncs(self, project_id):
        return list(self.syncs)

    async def get_development_configuration(self, project_id, revision=None):
        return self.configuration


class _Clone:
    """Every fetch reads ``UPSTREAM``; ``ancestry`` holds the (ancestor, descendant) pairs."""

    def __init__(self, ancestry: set[tuple[str, str]]) -> None:
        self.ancestry, self.fetches = ancestry, 0

    async def sync(self, project_id, locator, ref, *, token=None):
        self.fetches += 1
        return UPSTREAM

    async def is_ancestor(self, project_id, ancestor, descendant):
        return ancestor == descendant or (ancestor, descendant) in self.ancestry

    async def tree_at(self, project_id, commit):
        return CheckoutTree(commit, {}, frozenset(), frozenset(), frozenset())


class _RefusingForge:
    async def review_request_state(self, *, url, token):
        raise ReviewRequestFailed("the forge answered 503 reading the pull request")


def _contribution(cycle_id: str, state: str, commit: str, integrated: str | None = None):
    return dataclasses.replace(
        _per_run(cycle_id, state, integrated), commit=commit, run_id=f"run_{cycle_id}"
    )


@pytest.mark.parametrize(
    "first",
    [
        # a row already merged_not_synced (an earlier sync took it; its validation never landed)
        _contribution("cyc_rep1", "integrated", "r1", integrated="s1"),
        # a row the failing sync itself records integrated, before the next one's read fails
        _contribution("cyc_rep1", "pending", "r1"),
    ],
    ids=["merged before the check", "merged by the failing sync"],
)
async def test_a_sync_that_fails_part_way_advances_nothing_and_answers_what_it_recorded(first):
    """Bugs caught: the Project re-validated after a sync that failed, because a row already stood
    ``merged_not_synced``, so a baseline moves on a reading that never completed; the answer built
    from the rows read before the sync, so a contribution it recorded integrated reads pending."""
    _held, log, goal_sets = _goal_set_world()
    records = _Records([first, _contribution("cyc_inc2", "pending", "r2")])
    writes = KeyedProjectWrites(records, records.held)
    clone = _Clone({("r1", UPSTREAM)})

    check = await check_integration(
        PROJECT, registry=records, repository=clone, forge=_RefusingForge(), campaigns=log,
        goal_sets=goal_sets, tokens={PROJECT: "github_pat_inventedPartial0005"}, actor="supervisor",
    )  # fmt: skip

    assert check.merge_state_unread.reason == "forge_unavailable"
    assert (writes.validations, clone.fetches, records.syncs) == ([], 1, [])
    assert records.project.development_baseline_commit == BASE
    assert [(w.increment.cycle_id, w.increment.standing.value, w.waits_on.value)
            for w in check.remaining] == [
        ("cyc_rep1", "merged_not_synced", "revalidation"),
        ("cyc_inc2", "contribution_pending", "merge_state_unread"),
    ]  # fmt: skip
    assert "the sync didn't complete" in check.remaining[0].clears_when
