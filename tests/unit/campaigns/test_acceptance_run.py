"""An increment's acceptance, executed on the real test runner (SIP-0109 §8; #1707).

The accepted app answers every join with 200; the candidate refuses a join to a full run. The
criteria are real pytest files run by ``run_generated_tests`` — each alone, on each overlay —
so what the runner reports is what is judged.
"""

from __future__ import annotations

import pytest

from squadops.campaigns.acceptance import DiscriminationReason, Held, IncrementVerdict
from squadops.campaigns.acceptance_run import FrozenCriterion, NewCriterion, evaluate_increment
from squadops.campaigns.evaluator_trees import FileTree, TestSurface, freeze_bundle
from squadops.capabilities.handlers.test_runner import run_generated_tests

SURFACE = TestSurface(("criteria/",), ())
INVOCATION = ("pytest", "-q")

_F1 = (
    "from app import join\n\ndef test_an_open_run_accepts_a_join():\n    assert join(2, 0) == 200\n"
)
#: Pins the accepted behaviour the candidate changes: a frozen criterion the increment breaks.
_F2 = "from app import join\n\ndef test_a_full_run_still_accepts():\n    assert join(2, 2) == 200\n"
_C2 = (
    "from app import join\n\ndef test_a_full_run_refuses_a_join():\n    assert join(2, 2) == 409\n"
)
_C9 = "from capacity import limit\n\ndef test_the_limit_is_two():\n    assert limit() == 2\n"

ACCEPTED = FileTree.of(
    {
        "app.py": "def join(capacity, joined):\n    return 200\n",
        "criteria/test_F1.py": _F1,
        "criteria/test_F2.py": _F2,
    }
)
CANDIDATE = FileTree.of(
    {
        "app.py": "def join(capacity, joined):\n    return 409 if joined >= capacity else 200\n",
        "capacity.py": "def limit():\n    return 2\n",
        "criteria/test_F1.py": _F1,
        "criteria/test_C2.py": _C2,
        "criteria/test_C9.py": _C9,
    }
)


def _frozen(cid: str, path: str):
    return FrozenCriterion(cid, path, freeze_bundle(cid, ACCEPTED, path, SURFACE, INVOCATION))


async def _evaluate(new, frozen, routes=None, rendered=None, retired=(), candidate=None):
    return await evaluate_increment(
        increment_id="inc_1",
        accepted=ACCEPTED,
        candidate=candidate or CANDIDATE,
        surface=SURFACE,
        new=new,
        frozen=frozen,
        declared_routes=routes or {},
        rendered=rendered or {},
        run=run_generated_tests,
        invocation=INVOCATION,
        retired=retired,
    )


async def test_an_increment_whose_new_criterion_discriminates_and_frozen_one_holds_is_accepted():
    """§8.1, §8.2 through the runner. Bugs caught: the new test run against the candidate's
    product on both sides (it would never fail on the baseline), or the frozen criterion run
    with the candidate's own tests beside it."""
    result = await _evaluate(
        [NewCriterion("C2", "criteria/test_C2.py")],
        [_frozen("F1", "criteria/test_F1.py")],
    )

    assert result.acceptance.verdict is IncrementVerdict.ACCEPTED
    assert result.discriminations[0].discriminating == ("test_a_full_run_refuses_a_join",)
    assert result.frozen[0].held is Held.HELD
    assert result.frozen[0].candidate_identity == CANDIDATE.identity
    assert set(result.new_bundles) == {"C2"}


async def test_setup_only_failures_a_broken_frozen_criterion_and_a_missing_bundle_reject():
    """§8.1–§8.2 together. Bugs caught: a criterion whose baseline failure is a missing module
    counted as discrimination, a frozen criterion the increment breaks counted as held, or a
    vanished bundle read as a pass."""
    result = await _evaluate(
        [NewCriterion("C2", "criteria/test_C2.py"), NewCriterion("C9", "criteria/test_C9.py")],
        [
            _frozen("F1", "criteria/test_F1.py"),
            _frozen("F2", "criteria/test_F2.py"),
            FrozenCriterion("F3", "criteria/test_F3.py", None),
        ],
    )

    assert result.acceptance.verdict is IncrementVerdict.REJECTED
    assert [(d.criterion_id, d.reason) for d in result.discriminations] == [
        ("C2", DiscriminationReason.DISCRIMINATES),
        ("C9", DiscriminationReason.ONLY_SETUP_FAILURES),
    ]
    assert [(r.criterion_id, r.held) for r in result.frozen] == [
        ("F1", Held.HELD),
        ("F2", Held.BROKEN),
        ("F3", Held.BLOCKED_UNVERIFIED),
    ]


@pytest.mark.parametrize(
    ("new", "routes", "rendered"),
    [
        # A new criterion whose test file the candidate never wrote.
        ([NewCriterion("C4", "criteria/test_C4.py")], {}, {}),
        # A declared route nobody rendered.
        ([], {"/runs": ("run-list",)}, {}),
    ],
    ids=["unwritten-criterion", "unrendered-route"],
)
async def test_what_could_not_be_read_blocks_and_never_accepts(new, routes, rendered):
    """SIP-0096: blocked_unverified never reads as accepted."""
    result = await _evaluate(new, [], routes, rendered)
    assert result.acceptance.verdict is IncrementVerdict.BLOCKED_UNVERIFIED


@pytest.mark.parametrize(
    ("retired", "edited", "held"),
    [
        ((), False, Held.HELD),
        # The candidate rewrote the frozen verifier, and nobody retired it: not accepted on it.
        ((), True, Held.BLOCKED_UNVERIFIED),
        # Retired: it is no longer frozen, and is not run at all.
        (("F1",), True, None),
    ],
    ids=["untouched", "rewritten-unretired", "retired"],
)
async def test_a_frozen_verifier_the_candidate_rewrote_blocks_unless_retired(retired, edited, held):
    """§8.1, SIP-0109 §19 items 7 and 12e. Bugs caught: an increment that edits an earlier
    criterion's test to agree with its own change accepted on the edit, or a retired criterion
    still run and failing an increment that ruled it out."""
    candidate = CANDIDATE
    if edited:
        files = dict(CANDIDATE.as_dict())
        files["criteria/test_F1.py"] = b"def test_an_open_run_accepts_a_join():\n    assert True\n"
        candidate = FileTree.of(files)

    result = await _evaluate(
        [], [_frozen("F1", "criteria/test_F1.py")], retired=retired, candidate=candidate
    )

    assert [r.held for r in result.frozen] == ([held] if held else [])
