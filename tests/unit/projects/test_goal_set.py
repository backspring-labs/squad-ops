"""A Project's goal set: what is refused, and what a revision carries (SIP-0115 §4, #2884)."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from squadops.cycles.models import ProjectNotFoundError
from squadops.projects.goal_set import (
    API_VERSION,
    GoalSetInvalid,
    parse_goal_set,
    revise_goal_set,
)
from tests.fixtures.goal_set import goal_set_document

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def test_a_goal_set_reads_back_as_it_was_written_and_its_order_is_kept():
    """Bugs caught: a field dropped between the submission and the stored document (a size note,
    a candidate's evidence); the backlog re-sorted, which would be a reorder nobody wrote."""
    doc = goal_set_document()
    doc["backlog"].reverse()

    parsed = parse_goal_set(doc)

    assert parsed.to_document() == {"api_version": API_VERSION, **doc}
    assert [b.id for b in parsed.backlog] == ["B-2", "B-1"]
    assert parse_goal_set(parsed.to_document()) == parsed


def _without(path: tuple, doc: dict) -> dict:
    *parents, last = path
    target = doc
    for key in parents:
        target = target[key]
    del target[last]
    return doc


def _set(path: tuple, value, doc: dict) -> dict:
    *parents, last = path
    target = doc
    for key in parents:
        target = target[key]
    target[last] = value
    return doc


@pytest.mark.parametrize(
    ("change", "field"),
    [
        # an empty goal: a goal set that says nothing would still be "the active goal set"
        (lambda d: _set(("goal",), "  ", d), "goal"),
        (lambda d: _without(("goal",), d), "goal"),
        # a misspelt list silently dropped would read as an emptied one
        (lambda d: _set(("expected_result",), [], d), "goal_set"),
        (lambda d: _set(("backlog", 0, "priority"), 1, d), "backlog[0]"),
        # two items under one id: slice 2 derives each item's status by its id
        (lambda d: _set(("backlog", 1, "id"), "B-1", d), "backlog"),
        (lambda d: _set(("expected_results", 1, "id"), "ER-log", d), "expected_results"),
        # an item serving a result the goal set doesn't have, or none at all
        (lambda d: _set(("backlog", 0, "serves"), ["ER-gone"], d), "backlog[0].serves"),
        (lambda d: _set(("backlog", 0, "serves"), [], d), "backlog[0].serves"),
        (lambda d: _set(("backlog", 0, "serves"), ["ER-log", "ER-log"], d), "backlog[0].serves"),
        # a surface that names no kind, or no place, or no reason for having none
        (
            lambda d: _set(("expected_results", 0, "surface", "kind"), "api", d),
            "expected_results[0].surface.kind",
        ),
        (
            lambda d: _without(("expected_results", 0, "surface", "ref"), d),
            "expected_results[0].surface.ref",
        ),
        (
            lambda d: _without(("expected_results", 2, "surface", "reason"), d),
            "expected_results[2].surface.reason",
        ),
        (
            lambda d: _set(("expected_results", 2, "surface", "ref"), "/calm", d),
            "expected_results[2].surface.ref",
        ),
        (lambda d: _without(("expected_results", 0, "surface"), d), "expected_results[0].surface"),
        # a candidate whose finding can't be placed in time, or that shares a backlog item's id
        (
            lambda d: _set(("candidates", 0, "found_at"), "2026-11-02T09:30:00", d),
            "candidates[0].found_at",
        ),
        (lambda d: _set(("candidates", 0, "found_at"), "yesterday", d), "candidates[0].found_at"),
        (lambda d: _set(("candidates", 0, "id"), "B-2", d), "candidates"),
        (lambda d: _set(("candidates", 0, "evidence"), "one link", d), "candidates[0].evidence"),
        # an id with a space or a slash can't be named in a path or a control-log row
        (lambda d: _set(("backlog", 0, "id"), "B 1", d), "backlog[0].id"),
        (lambda d: _set(("constraints",), ["No account", ""], d), "constraints[1]"),
        (lambda d: _set(("out_of_scope",), "Sharing a log", d), "out_of_scope"),
        # a later major version is refused before anything else is read
        (lambda d: _set(("api_version",), "squadops.project-goal-set/v2", d), "api_version"),
    ],
)
def test_an_invalid_goal_set_is_refused_naming_its_field(change, field):
    doc = change(copy.deepcopy(goal_set_document()))

    with pytest.raises(GoalSetInvalid) as refused:
        parse_goal_set(doc)

    assert refused.value.field == field


def test_a_goal_alone_is_a_goal_set():
    """Bug caught: the lists made required, so the owner can't write the goal before its
    backlog."""
    parsed = parse_goal_set({"goal": "A reader keeps a log"})

    assert (parsed.goal, parsed.backlog, parsed.expected_results) == (
        "A reader keeps a log",
        (),
        (),
    )


class TestRevising:
    @pytest.fixture
    def ports(self):
        projects = AsyncMock()
        goal_sets = AsyncMock()

        async def record(revision, **kwargs):
            return revision, False

        goal_sets.record_revision.side_effect = record
        return projects, goal_sets

    async def _revise(self, ports, doc, **overrides):
        projects, goal_sets = ports
        kwargs = {
            "expected_revision": 2,
            "reason": "the owner reordered after review",
            "source_ref": None,
            "projects": projects,
            "goal_sets": goal_sets,
            "author": "owner",
            "idempotency_key": "k-1",
            "now": NOW,
        } | overrides
        return await revise_goal_set("prj-lantern", doc, **kwargs)

    async def test_an_unknown_project_is_refused_and_nothing_is_written(self, ports):
        projects, goal_sets = ports
        projects.get_project.side_effect = ProjectNotFoundError("Project not found: prj-lantern")

        with pytest.raises(ProjectNotFoundError):
            await self._revise(ports, goal_set_document())

        goal_sets.record_revision.assert_not_awaited()

    async def test_a_revision_without_a_reason_is_refused(self, ports):
        with pytest.raises(GoalSetInvalid) as refused:
            await self._revise(ports, goal_set_document(), reason=" ")

        assert refused.value.field == "reason"
        ports[1].record_revision.assert_not_awaited()

    async def test_a_retry_spelt_differently_is_the_same_request_and_a_new_reason_is_not(
        self, ports
    ):
        """The key's hash is taken over the validated goal set. Bugs caught: a retry whose file
        omits a default (an empty description) refused as a conflict; a second write under the
        same key with another reason replayed as if it were the first."""
        sparse = goal_set_document()
        for item in sparse["backlog"]:
            del item["description"]

        await self._revise(ports, goal_set_document())
        await self._revise(ports, sparse)
        await self._revise(ports, goal_set_document(), reason="another reason")

        hashes = [c.kwargs["request_hash"] for c in ports[1].record_revision.await_args_list]
        assert hashes[0] == hashes[1] != hashes[2]
