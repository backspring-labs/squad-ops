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


async def test_a_declared_route_nobody_rendered_blocks_the_increment():
    """§8.3: rendering is not read yet (#1796). Bug caught: an unrendered page passed by
    omission, so an increment is promoted without anyone seeing it render."""
    _, document = await _evaluate(increment_declared_routes={"/runs/:run_id": ["capacity-status"]})

    assert document["verdict"] == "blocked_unverified"
    assert document["routes"] == [
        {"path": "/runs/:run_id", "held": "blocked_unverified", "missing": []}
    ]


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
