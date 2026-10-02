"""The evaluator trees, verifier bundles and test identity (SIP-0109 §7.4, §8.1; #1806).

Test identity runs on real stored suites: the first 2.0 regression roll (cyc_1b363177c5b8)'s
views.test.jsx as qa emitted it (v1), as the qa repair edited it (v2), and as qa re-authored it
(v3), and that roll's backend suite. The overlays run on trees shaped as the React stack lays them
out, with the stack's own test surface.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from squadops.campaigns.evaluator_trees import (
    BundleIncomplete,
    FileTree,
    TestChange,
    TestSurface,
    baseline_evaluator_overlay,
    candidate_verifier_overlay,
    classify_tests,
    freeze_bundle,
    test_inventory,
)

_SUITES = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns" / "suites"
_VIEWS = "frontend/src/__tests__/views.test.jsx"
SURFACE = TestSurface.for_stack("fullstack_fastapi_react")


def _suite(name: str) -> dict:
    return test_inventory(_VIEWS, (_SUITES / name).read_text())


# --- test identity, on real suites ---------------------------------------------------------------


def test_the_qa_repair_modified_exactly_the_two_tests_it_edited():
    """The roll's record: the repair edited views.test.jsx at lines 3, 139 and 168 — an import
    and the join and leave tests. Bug caught: an import edit read as modifying every test, or a
    body change missed."""
    changes = classify_tests(
        _suite("views.test.v1-emitted.jsx"), _suite("views.test.v2-repaired.jsx")
    )

    assert Counter(changes.values()) == {TestChange.UNCHANGED: 7, TestChange.MODIFIED: 2}
    assert sorted(t.name for t, c in changes.items() if c is TestChange.MODIFIED) == [
        "RunDetailView > submits join form and surfaces duplicate-participant rejection via apiFetch call",
        "RunDetailView > submits leave form and calls apiFetch leave endpoint",
    ]


def test_a_reauthored_suite_reads_as_new_and_removed_tests():
    changes = classify_tests(
        _suite("views.test.v2-repaired.jsx"), _suite("views.test.v3-reauthored.jsx")
    )
    assert Counter(changes.values()) == {
        TestChange.NEW: 10,
        TestChange.REMOVED: 8,
        TestChange.MODIFIED: 1,
    }


def test_a_renamed_test_is_a_rename_not_a_removal_and_an_addition():
    """§7.4: same body, new id. Bug caught: a rename read as one test retired and one added,
    which would ask the supervisor to rule on a retirement that never happened."""
    source = (_SUITES / "views.test.v2-repaired.jsx").read_text()
    renamed = source.replace(
        "it('shows detail-error anchor when run is not found'",
        "it('shows the not-found anchor for an unknown run'",
    )
    changes = classify_tests(test_inventory(_VIEWS, source), test_inventory(_VIEWS, renamed))

    assert Counter(changes.values()) == {TestChange.UNCHANGED: 8, TestChange.RENAMED: 1}
    [renamed_id] = [t for t, c in changes.items() if c is TestChange.RENAMED]
    assert renamed_id.name == "RunDetailView > shows the not-found anchor for an unknown run"


def test_a_quoted_call_inside_a_test_is_not_a_test():
    source = "describe('A', () => {\n  it('x', () => { expect(\"it('y', z)\").toBe(1) })\n})\n"
    assert [t.name for t in test_inventory("a.test.js", source)] == ["A > x"]


def test_python_tests_are_named_as_pytest_names_them():
    """Bug caught: class-held tests named without their class, colliding with a module-level
    test of the same name."""
    source = (_SUITES / "test_runs.py.txt").read_text() + (
        "\n\nclass TestCapacity:\n    def test_join_run(self):\n        assert True\n"
    )
    names = {t.name for t in test_inventory("backend/tests/test_runs.py", source)}
    assert len(names) == 10
    assert {"test_join_run", "TestCapacity::test_join_run"} <= names


# --- the overlays --------------------------------------------------------------------------------

ACCEPTED = FileTree.of(
    {
        "backend/routes.py": "accepted routes",
        "frontend/src/views/RunDetailView.jsx": "accepted view",
        "frontend/src/__tests__/views.test.jsx": "accepted suite",
        "frontend/src/test-setup.js": "setup v1",
        "conftest.py": "anchor v1",
    }
)
CANDIDATE = FileTree.of(
    {
        "backend/routes.py": "candidate routes",
        "frontend/src/views/RunDetailView.jsx": "candidate view",
        "frontend/src/__tests__/views.test.jsx": "candidate suite",
        "frontend/src/__tests__/criteria/C2.test.jsx": "import { full } from '../helpers/runs'\nC2",
        "frontend/src/__tests__/helpers/runs.js": "export const full = 1",
        "frontend/src/test-setup.js": "setup v2",
        "conftest.py": "anchor v1",
    }
)


def test_the_baseline_overlay_holds_no_candidate_product_code():
    """§7.4 by construction. Bug caught: a candidate product file leaking into the overlay, so a
    new test 'fails on the baseline' against code the baseline never had."""
    overlay = baseline_evaluator_overlay(ACCEPTED, CANDIDATE, SURFACE).tree.as_dict()

    assert overlay["backend/routes.py"] == b"accepted routes"
    assert overlay["frontend/src/views/RunDetailView.jsx"] == b"accepted view"
    assert overlay["frontend/src/__tests__/views.test.jsx"] == b"candidate suite"
    assert overlay["frontend/src/test-setup.js"] == b"setup v2"
    assert "frontend/src/__tests__/criteria/C2.test.jsx" in overlay


def test_the_verifier_overlay_holds_no_candidate_test_file():
    """§7.4 by construction. Bug caught: the candidate's edited copy of a frozen test running in
    place of the frozen one, so an increment silently rewrites what it is judged by."""
    bundle = freeze_bundle(
        "C2",
        ACCEPTED_WITH_C2,
        "frontend/src/__tests__/criteria/C2.test.jsx",
        SURFACE,
        ("vitest", "run"),
    )
    overlay = candidate_verifier_overlay(CANDIDATE, bundle, SURFACE).tree.as_dict()

    assert overlay["backend/routes.py"] == b"candidate routes"
    assert (
        overlay["frontend/src/__tests__/criteria/C2.test.jsx"]
        == b"frozen C2\nimport { full } from '../helpers/runs'"
    )
    assert "frontend/src/__tests__/views.test.jsx" not in overlay
    assert overlay["frontend/src/test-setup.js"] == b"setup v1"


ACCEPTED_WITH_C2 = FileTree.of(
    {
        **ACCEPTED.as_dict(),
        "frontend/src/__tests__/criteria/C2.test.jsx": "frozen C2\nimport { full } from '../helpers/runs'",
        "frontend/src/__tests__/helpers/runs.js": "export const full = 1",
        "frontend/src/__tests__/criteria/C3.test.jsx": "import { view } from '../helpers/views'\nC3",
        "frontend/src/__tests__/helpers/views.js": "export const view = 1",
    }
)


def test_a_bundle_holds_its_test_its_imports_and_the_test_config_and_nothing_else():
    bundle = freeze_bundle(
        "C2",
        ACCEPTED_WITH_C2,
        "frontend/src/__tests__/criteria/C2.test.jsx",
        SURFACE,
        ("vitest", "run"),
    )
    assert set(bundle.files.paths()) == {
        "frontend/src/__tests__/criteria/C2.test.jsx",
        "frontend/src/__tests__/helpers/runs.js",
        "frontend/src/test-setup.js",
        "conftest.py",
    }


def test_adding_a_criterion_with_its_own_fixture_moves_no_other_bundle():
    """§8.1 and criterion 12e. Bug caught: bundles sharing a fixture by reference, so a later
    criterion's fixture change re-addresses — and silently re-defines — an earlier one."""
    before = freeze_bundle(
        "C2",
        ACCEPTED_WITH_C2,
        "frontend/src/__tests__/criteria/C2.test.jsx",
        SURFACE,
        ("vitest", "run"),
    )
    later = FileTree.of(
        {
            **ACCEPTED_WITH_C2.as_dict(),
            "frontend/src/__tests__/helpers/views.js": "export const view = 2",
            "frontend/src/__tests__/criteria/C4.test.jsx": "import { view } from '../helpers/views'\nC4",
        }
    )
    after = freeze_bundle(
        "C2", later, "frontend/src/__tests__/criteria/C2.test.jsx", SURFACE, ("vitest", "run")
    )
    c3_before = freeze_bundle(
        "C3", ACCEPTED_WITH_C2, "frontend/src/__tests__/criteria/C3.test.jsx", SURFACE, ("vitest",)
    )
    c3_after = freeze_bundle(
        "C3", later, "frontend/src/__tests__/criteria/C3.test.jsx", SURFACE, ("vitest",)
    )

    assert after.address == before.address
    assert c3_after.address != c3_before.address  # C3 does read the changed fixture


def test_a_bundle_that_cannot_run_is_never_frozen():
    """§8.1: a missing bundle is blocked_unverified, never a pass — so a bundle missing its own
    test, or a file its test imports, is refused at freeze time. Bug caught: the helper skipped
    and the bundle frozen anyway, failing only when a later increment runs it."""
    broken = FileTree.of(
        {"frontend/src/__tests__/criteria/C9.test.jsx": "import { x } from './nowhere'\nC9"}
    )
    with pytest.raises(BundleIncomplete, match=r"imports \./nowhere"):
        freeze_bundle("C9", broken, "frontend/src/__tests__/criteria/C9.test.jsx", SURFACE, ())
    with pytest.raises(BundleIncomplete, match="C8.test.jsx is not in the tree"):
        freeze_bundle("C8", broken, "frontend/src/__tests__/criteria/C8.test.jsx", SURFACE, ())


def test_an_overlay_identity_moves_with_the_tests_and_the_accepted_tree_is_unchanged():
    first = baseline_evaluator_overlay(ACCEPTED, CANDIDATE, SURFACE)
    edited = FileTree.of({**CANDIDATE.as_dict(), "frontend/src/__tests__/views.test.jsx": "edited"})
    second = baseline_evaluator_overlay(ACCEPTED, edited, SURFACE)
    same_tests_new_product = FileTree.of({**CANDIDATE.as_dict(), "backend/routes.py": "other"})

    assert first.identity != second.identity
    assert (
        baseline_evaluator_overlay(ACCEPTED, same_tests_new_product, SURFACE).identity
        == first.identity
    )
    assert ACCEPTED.get("backend/routes.py") == b"accepted routes"
