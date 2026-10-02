"""``qa.evaluate_increment``: an increment's acceptance through its handler (SIP-0109 §8).

The accepted app answers every join with 200; the candidate refuses a join to a full run. The
criterion's own test is a real pytest file, run by the real runner on both trees, so what the
runner reports is what is judged. (``run_suite`` is pointed at the pytest runner: the stack's
own framework also runs vitest, which needs Node.)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from squadops.capabilities.handlers.cycle.evaluate_increment import QAEvaluateIncrementHandler

_C1 = "backend/tests/criteria/test_C1.py"
_C1_TEST = (
    "from app import join\n\ndef test_a_full_run_refuses_a_join():\n    assert join(2, 2) == 409\n"
)
ACCEPTED = {"app.py": "def join(capacity, joined):\n    return 200\n"}
CANDIDATE = {
    "app.py": "def join(capacity, joined):\n    return 409 if joined >= capacity else 200\n",
    _C1: _C1_TEST,
}


@pytest.fixture(autouse=True)
def _pytest_runner(monkeypatch):
    from squadops.capabilities.handlers import test_runner

    async def run_suite(framework, source_files, test_files, timeout_seconds=60):
        return await test_runner.run_generated_tests(
            source_files, test_files, timeout_seconds=timeout_seconds
        )

    monkeypatch.setattr(test_runner, "run_suite", run_suite)


def _inputs(**overrides) -> dict:
    return {
        "resolved_config": {"build_profile": "fullstack_fastapi_react"},
        "increment_id": "prop_cap",
        "accepted_tree_files": ACCEPTED,
        "acceptance_workspace_files": CANDIDATE,
        "increment_criterion_files": [{"criterion_id": "C1", "path": _C1}],
        "increment_declared_routes": {},
        **overrides,
    }


async def _evaluate(**overrides) -> tuple[object, dict | None]:
    result = await QAEvaluateIncrementHandler().handle(MagicMock(), _inputs(**overrides))
    artifacts = result.outputs.get("artifacts") or []
    return result, (json.loads(artifacts[0]["content"]) if artifacts else None)


async def test_a_criterion_that_fails_on_the_accepted_app_and_passes_on_the_candidate_is_met():
    """§8.2 through the handler. Bugs caught: the two trees swapped or the candidate used for
    both (the test never fails on the baseline), or the bundle a promotion freezes missing."""
    result, document = await _evaluate()

    assert result.success
    assert document["verdict"] == "accepted"
    [c1] = document["discriminations"]
    assert (c1["criterion_id"], c1["met"], c1["discriminating"]) == (
        "C1",
        True,
        ["test_a_full_run_refuses_a_join"],
    )
    assert document["new_bundles"]["C1"]["files"][_C1] == _C1_TEST
    assert result.outputs["artifacts"][0]["type"] == "increment_evaluation"


@pytest.fixture
def pages(monkeypatch):
    """What the candidate's pages render, in place of standing it up with a browser."""
    from squadops.capabilities.handlers import route_rendering

    rendered: dict = {}

    def render_routes(files, routes, seeds, **_):
        return {route: rendered.get(route) for route in routes}

    monkeypatch.setattr(route_rendering, "render_routes", render_routes)
    return rendered


@pytest.mark.parametrize(
    ("page", "verdict", "held"),
    [
        (frozenset({"run-detail-view", "capacity-status"}), "accepted", "held"),
        # A state-dependent anchor not shown: recorded, not judged (§24p).
        (frozenset({"run-detail-view"}), "accepted", "held"),
        # The page rendered something, but not the view the route declares.
        (frozenset({"capacity-status"}), "rejected", "broken"),
        (None, "blocked_unverified", "blocked_unverified"),
    ],
    ids=["rendered", "a-state-anchor-not-shown", "the-view-not-rendered", "never-rendered"],
)
async def test_each_declared_route_is_judged_by_what_its_page_rendered(pages, page, verdict, held):
    """§8.3, through the handler. Bugs caught: a page that never rendered passed by omission, or
    one that rendered something other than its view read as rendered."""
    pages["/runs/:run_id"] = page

    _, document = await _evaluate(
        increment_declared_routes={"/runs/:run_id": ["run-detail-view", "capacity-status"]}
    )

    assert document["verdict"] == verdict
    assert document["routes"][0]["held"] == held


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"accepted_tree_files": {}}, "no the accepted tree"),
        ({"acceptance_workspace_files": {}}, "no the candidate tree"),
        ({"increment_id": ""}, "no the increment's id"),
    ],
    ids=["no-accepted-tree", "no-candidate", "no-increment-id"],
)
async def test_nothing_is_judged_without_both_trees(overrides, error):
    """Bug caught: an evaluation against an empty baseline, which reads every new test as
    discriminating and accepts an increment that proved nothing."""
    result, document = await _evaluate(**overrides)

    assert (result.success, document) == (False, None)
    assert error in result.error


# §8.1: a criterion an earlier increment froze, run by its stored bundle on the candidate.
_F1 = "backend/tests/criteria/test_F1.py"
_F1_TEST = (
    "from app import join\n\ndef test_an_open_run_accepts_a_join():\n    assert join(2, 0) == 200\n"
)


def _frozen_inputs(address_of=None) -> dict:
    from squadops.campaigns.evaluator_trees import FileTree, VerifierBundle

    bundle = {"files": {_F1: _F1_TEST}, "invocation": ["both"]}
    address = VerifierBundle("F1", FileTree.of(bundle["files"]), ("both",)).address
    return {
        "increment_frozen_criteria": [
            {"criterion_id": "F1", "test_path": _F1, "bundle_address": address_of or address}
        ],
        "frozen_bundles": {"F1": bundle},
    }


async def test_a_frozen_criterion_runs_by_its_bundle_and_holds():
    """§8.1. Bug caught: the criteria earlier increments froze never run again, so an increment
    that broke one would be accepted."""
    _, document = await _evaluate(**_frozen_inputs())

    assert document["verdict"] == "accepted"
    assert [(f["criterion_id"], f["held"]) for f in document["frozen"]] == [("F1", "held")]


async def test_a_bundle_that_no_longer_hashes_to_its_address_is_never_run():
    """§8.1, SIP-0096. Bug caught: a stored bundle edited after it was frozen — a verifier nobody
    ruled on — run and credited as the criterion held."""
    _, document = await _evaluate(**_frozen_inputs(address_of="0" * 64))

    assert document["verdict"] == "blocked_unverified"
    assert [(f["criterion_id"], f["held"]) for f in document["frozen"]] == [
        ("F1", "blocked_unverified")
    ]


# §8.1: "the old bundle is retired and the new one frozen" — a verifier the change replaces.
_F1_REPLACED = (
    "from app import join\n\ndef test_a_full_run_is_refused():\n    assert join(2, 2) == 409\n"
)
_F1_STALE = (
    "from app import join\n\ndef test_a_full_run_still_joins():\n    assert join(2, 2) == 200\n"
)


@pytest.mark.parametrize(
    ("candidate_f1", "verdict", "held"),
    [
        (_F1_REPLACED, "accepted", "held"),
        # The replacement fails on the candidate: frozen as it is, it would fail every later one.
        (_F1_STALE, "rejected", "broken"),
        # The candidate never wrote the replacement: nothing to freeze, and nothing passed.
        (None, "blocked_unverified", "blocked_unverified"),
    ],
    ids=["replaced", "replacement-fails", "replacement-missing"],
)
async def test_a_replaced_verifier_is_frozen_anew_from_the_candidate(candidate_f1, verdict, held):
    """§8.1, §24r's not-built, through the handler's real ``handle()``. Bugs caught: a replaced
    criterion left unfrozen, so the behaviour it guards is guarded by nothing after this
    increment; the old bundle still run against the change that ruled it out; or a replacement
    that fails on the candidate frozen anyway."""
    from squadops.campaigns.evaluator_trees import FileTree, VerifierBundle

    candidate = {k: v for k, v in CANDIDATE.items() if k != _F1}
    if candidate_f1 is not None:
        candidate[_F1] = candidate_f1
    _, document = await _evaluate(
        **_frozen_inputs(),
        acceptance_workspace_files=candidate,
        increment_retired_criteria=["F1"],
        increment_replaced_criteria=[{"criterion_id": "F1", "path": _F1}],
    )

    assert document["verdict"] == verdict
    [f1] = [f for f in document["frozen"] if f["criterion_id"] == "F1"]
    old = VerifierBundle("F1", FileTree.of({_F1: _F1_TEST}), ("both",)).address
    assert f1["held"] == held and f1["bundle_address"] != old
    assert document["replaced"] == ["F1"]
    if candidate_f1 is not None:
        assert document["new_bundles"]["F1"]["files"][_F1] == candidate_f1
        assert document["new_bundles"]["F1"]["test_path"] == _F1
    else:
        assert "F1" not in document["new_bundles"]
