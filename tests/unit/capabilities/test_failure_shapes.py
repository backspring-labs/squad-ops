"""The failure-shape sorter (SIP-0110 §0.4, the 2.2 plan's D14): each runner's own messages,
sorted into observed signatures, never causes. Seeded and checked on the four rounds the 2.1 cut
recorded with ``failed_detail`` (SIP-0110 §5b, §5e)."""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.test_runner import (
    FAILURE_SHAPES,
    failure_shape_of,
    runner_of_case,
)

pytestmark = [pytest.mark.domain_capabilities]


@pytest.mark.parametrize(
    ("account", "expected"),
    [
        pytest.param(
            "frontend/src/__tests__/runViews.test.jsx:39 renders run titles: TypeError: "
            "__vi_import_5__.apiFetch.mockResolvedValue is not a function",
            ("vitest", "not_a_function"),
            id="2.1-cut-mock-misuse",
        ),
        pytest.param(
            "frontend/src/__tests__/runs.test.jsx: renders all form fields: Error: Unable to find "
            'an element by: [data-testid="create-run-error"]',
            ("vitest", "element_not_found"),
            id="2.1-cut-testid-not-found",
        ),
        pytest.param(
            "frontend/src/__tests__/RunDetailView.capacity.test.jsx: : Failed to resolve import "
            '"../../views/RunDetailView.jsx" from "src/__tests__/RunDetailView.capacity.test.jsx". '
            "Does the file exist?",
            ("vitest", "unresolved_import"),
            id="2.1-cut-unresolved-import",
        ),
        pytest.param(
            "frontend/src/__tests__/runs.test.jsx: submits valid data: AssertionError: expected "
            "\"spy\" to be called with arguments: [ '/runs', ObjectContaining{…} ]",
            ("vitest", "spy_called_with_other_arguments"),
            id="2.1-cut-spy-arguments",
        ),
        pytest.param(
            "backend/tests/test_runs.py::test_create_run: assert 422 == 201",
            ("pytest", "status_code_mismatch"),
            id="pytest-status",
        ),
        pytest.param(
            "app/__tests__/runs.test.ts: renders: ReferenceError: screen is not defined",
            ("vitest", "not_defined"),
            id="nextjs-reference",
        ),
    ],
)
def test_each_recorded_account_sorts_to_its_shape(account, expected):
    """Bug caught: a round's defect left unsorted, so its repeat in a later cycle is never seen
    and the build seams stay empty by construction (§5d's finding)."""
    assert failure_shape_of(account) == expected


@pytest.mark.parametrize(
    ("account", "expected"),
    [
        pytest.param("a message naming no file", (None, None), id="no-file"),
        pytest.param(
            "frontend/src/__tests__/x.test.jsx: AssertionError: expected 3 to be 4",
            ("vitest", None),
            id="no-row-matches",
        ),
        pytest.param("README.md: something", (None, None), id="not-a-suite"),
    ],
)
def test_an_account_the_table_cannot_place_is_left_unclassified(account, expected):
    """Bug caught: a guess recorded as a shape, which the repeat report would then count."""
    assert failure_shape_of(account) == expected


def test_a_shape_is_named_by_its_runner_and_never_by_an_attribution_class():
    """Bug caught: the sorter becoming a second failure taxonomy beside SIP-0108's registry,
    which SIP-0109 rules out for memory."""
    from squadops.cycles.failure_attribution import AttributionClass

    names = {s.name for shapes in FAILURE_SHAPES.values() for s in shapes}

    assert set(FAILURE_SHAPES) == {"vitest", "pytest"}
    assert not names & {a.value for a in AttributionClass}
    assert runner_of_case("backend/tests/test_x.py::t: boom") == "pytest"
