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


# --- §10h: a result seen in a play session is observed on a scenario ---------------------------

#: The goal set the owner approved for z_tower-ascension on 2026-11-17 (#3042), as written.
_PLAYED = """
goal: A player in the lobby can tell at a glance where to go and how long they have been playing
expected_results:
  - id: ER-lobby-hint
    statement: While the player stands in the lobby, the HUD shows one line telling them to step into the portal. On a floor the line is gone
    surface: {kind: scenario, ref: the HUD in a play session}
  - id: ER-session-clock
    statement: The HUD shows how long this play session has lasted, in minutes and seconds, and the time advances
    surface: {kind: scenario, ref: the HUD in a play session}
constraints:
  - Nothing a player's save holds is added, renamed, moved or removed
  - "Scripts only: nothing is built in Studio, and each new HUD element is created in code from Client/UI/Theme"
  - Each rule that only computes (which line to show, how a duration is written) is a module the headless tests load
  - No existing HUD element changes its text
out_of_scope:
  - Sound
  - Anything that needs a fight, a second player or a saved value to observe
  - Time played across sessions
backlog:
  - id: B-1
    title: The lobby hint
    description: In the lobby the HUD shows "Step into the portal to climb". It is hidden on a floor.
    serves: [ER-lobby-hint]
    size: one increment
  - id: B-2
    title: The session clock
    description: The HUD shows the time since the session began as m:ss, such as 1:05, and counts up each second.
    serves: [ER-session-clock]
    size: one increment
"""


def test_a_goal_set_whose_results_are_seen_in_play_is_read_as_written():
    """Bug caught: a game's goal set refused at registration, or registered with its results
    marked ``none``, which shows the proposal "not observed" and steers it off the scenario
    criterion the result needs (#3042)."""
    import yaml

    doc = yaml.safe_load(_PLAYED)

    parsed = parse_goal_set(doc)

    assert [
        (r.id, r.surface.kind, r.surface.ref, r.surface.reason) for r in parsed.expected_results
    ] == [
        ("ER-lobby-hint", "scenario", "the HUD in a play session", None),
        ("ER-session-clock", "scenario", "the HUD in a play session", None),
    ]
    assert [(b.id, b.serves) for b in parsed.backlog] == [
        ("B-1", ("ER-lobby-hint",)),
        ("B-2", ("ER-session-clock",)),
    ]
    assert parsed.to_document() == {"api_version": API_VERSION, **doc, "candidates": []}


@pytest.mark.parametrize(
    ("surface", "field", "says"),
    [
        ({"kind": "scenario"}, "expected_results[0].surface.ref", "required"),
        (
            {"kind": "scenario", "ref": "the HUD", "reason": "seen only in play"},
            "expected_results[0].surface.reason",
            "only a result with no surface gives a reason",
        ),
        (
            {"kind": "play_session", "ref": "the HUD"},
            "expected_results[0].surface.kind",
            "'package_interface', 'scenario', 'none'), not 'play_session'",
        ),
    ],
    ids=["no ref", "a reason beside a ref", "a kind of its own"],
)
def test_a_scenario_surface_is_held_to_the_rules_of_every_observed_surface(surface, field, says):
    """Bugs caught: the new kind accepted with nothing named there, or read as ``none`` and
    given a reason; and a kind outside the list accepted, or refused without the list."""
    import yaml

    doc = yaml.safe_load(_PLAYED)
    doc["expected_results"][0]["surface"] = surface

    with pytest.raises(GoalSetInvalid) as refused:
        parse_goal_set(doc)

    assert refused.value.field == field
    assert says in str(refused.value)
