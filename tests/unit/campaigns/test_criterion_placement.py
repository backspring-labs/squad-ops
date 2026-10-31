"""Where a criterion's own test goes on a repository-backed Project (SIP-0109 §24bv point 5).

The runners are contract 8's (``squadops.projects.derived_profile``): the shared fixture's Tally as
recorded, and invented products for the shapes Tally doesn't have (a pytest backend beside a
vitest frontend, a runner that can't take one file).
"""

from __future__ import annotations

import pytest

from squadops.campaigns.criterion_placement import (
    Unplaceable,
    place_criterion,
    runner_placements,
)
from squadops.projects.derived_profile import DISCLOSED, Gap, Runner, parse_profile
from tests.fixtures.shared_contract.repository import product_files, recorded


def _runner(runner, covers, roots, pattern, *, single=("{path}",), checks=("tests",)) -> Runner:
    return Runner(
        runner=runner,
        checks=checks,
        covers=covers,
        roots=roots,
        file_pattern=pattern,
        suite_argv=("run",),
        single_file_argv=single,
        test_ids=None,
        support_files=(),
    )


_PYTEST = _runner("pytest", ("api/**",), ("tests",), "test_*.py", checks=("backend",))
_VITEST = _runner("vitest", ("web/**",), ("web",), "*.test.*", checks=("frontend",))
#: The invented product's tree at its head: its own tests, which give vitest its extension.
_TREE = (
    "api/routes.py",
    "tests/test_routes.py",
    "web/src/App.jsx",
    "web/src/__tests__/app.test.jsx",
    "web/src/__tests__/list.test.jsx",
    "web/src/__tests__/legacy.test.js",
)


def test_tallys_recorded_profile_places_a_criterion_under_its_unittest_runner():
    """The shared fixture's recording, as the proposal is given it. Bug caught: a criterion of a
    Tally change placed outside ``checks/`` or under a name its ``check_*.py`` pattern doesn't
    take, so the product's own unittest discovery never runs it."""
    profile = parse_profile(recorded("derived_profile", "valid"))
    placements = runner_placements(profile.runners, profile.gaps, product_files())

    assert [(p.runner, p.template, p.refused) for p in placements] == [
        ("unittest", "checks/check_criterion_{criterion}.py", None)
    ]
    assert place_criterion("T-1", ("tally/report.py",), placements) == (
        "checks/check_criterion_T_1.py"
    )


@pytest.mark.parametrize(
    ("paths", "placed"),
    [
        (("api/routes.py",), "tests/test_criterion_C1.py"),
        (("api/**",), "tests/test_criterion_C1.py"),
        # The extension is the one most of the runner's own tests take.
        (("web/src/App.jsx",), "web/criterion_C1.test.jsx"),
    ],
    ids=["a backend file", "a backend glob", "a frontend file"],
)
def test_a_criterion_is_placed_under_the_runner_that_tests_its_paths(paths, placed):
    """Bugs caught: a frontend criterion placed under the backend's runner (its tests never run);
    a vitest file given an extension the product's tests don't use; a glob path read as covering
    nothing."""
    placements = runner_placements((_PYTEST, _VITEST), (), _TREE)

    assert place_criterion("C1", paths, placements) == placed


def test_the_first_runner_that_can_host_one_takes_it_when_an_earlier_one_cannot():
    """Two runners over one path, the first unscopable (H.7's ``runner_not_scopable``). Bug caught:
    the criterion refused because the first runner can't take one file, while the second can."""
    whole_only = _runner("pytest", ("api/**",), ("tests",), "test_*.py", single=None)
    unscopable_by_gap = _runner("jest", ("api/**",), ("spec",), "*.spec.js", checks=("j",))
    gap = Gap("runner_not_scopable", DISCLOSED, "j", ("api/**",), "two files named alike", "rename")
    placements = runner_placements((whole_only, unscopable_by_gap, _PYTEST), (gap,), _TREE)

    assert [p.template is None for p in placements] == [True, True, False]
    assert place_criterion("C1", ("api/routes.py",), placements) == "tests/test_criterion_C1.py"


@pytest.mark.parametrize(
    ("runners", "tree", "paths", "why"),
    [
        ((_PYTEST,), _TREE, ("web/src/App.jsx",), "no runner's tests cover web/src/App.jsx"),
        ((), _TREE, ("api/routes.py",), "the product declares no runner"),
        (
            (_runner("pytest", ("api/**",), ("tests",), "test_*.py", single=None),),
            _TREE,
            ("api/routes.py",),
            "can't be run on one file",
        ),
        # A vitest pattern leaves the extension open, and the runner holds no test to read it from.
        ((_VITEST,), ("web/src/App.jsx",), ("web/src/App.jsx",), "holds no test file"),
        (
            (_runner("pytest", ("api/**",), ("tests",), "test_[a-z]*.py"),),
            _TREE,
            ("api/routes.py",),
            "names no single file",
        ),
        # The file the framework would place is the product's own: never overwritten.
        ((_PYTEST,), (*_TREE, "tests/test_criterion_C1.py"), ("api/routes.py",), "already"),
        ((_PYTEST,), _TREE, (), "exercises no product path"),
    ],
    ids=[
        "no runner covers it",
        "no runner at all",
        "the only runner can't take one file",
        "no extension to read",
        "a pattern naming no single file",
        "a product file in the way",
        "no paths",
    ],
)
def test_a_criterion_no_runner_can_host_is_refused_naming_why(runners, tree, paths, why):
    """Bug caught: a criterion placed by guess (a path no runner discovers, a file overwriting the
    product's own, an extension invented), instead of refused for the proposer to revise."""
    placements = runner_placements(runners, (), tree)

    with pytest.raises(Unplaceable, match=why):
        place_criterion("C1", paths, placements)


def test_a_placement_reads_back_as_it_was_handed_to_the_proposal():
    """The placements cross from the runtime to the agent's container as data. Bug caught: a field
    lost in the crossing, so the rails place under a template the runtime never read, or let a
    product file be overwritten."""
    from squadops.campaigns.criterion_placement import RunnerPlacement

    placements = runner_placements((_PYTEST, _VITEST), (), (*_TREE, "tests/test_criterion_X.py"))

    assert tuple(RunnerPlacement.from_dict(p.as_dict()) for p in placements) == placements
    assert placements[0].taken == ("tests/test_criterion_X.py",)
