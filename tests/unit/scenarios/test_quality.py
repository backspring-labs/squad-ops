"""Quality baselines: Lighthouse and axe per declared page (SIP-0113 §4.2; #2416)."""

from __future__ import annotations

import pytest

from squadops.scenarios.quality import (
    NotMeasured,
    PageMeasure,
    QualityReading,
    QualityStatus,
    evaluator_pages,
    measurable_pages,
)

_LIGHTHOUSE = {"performance": 0.93, "accessibility": 0.96, "best-practices": 0.78}
_AXE = {"critical": 0, "serious": 1, "moderate": 2, "minor": 0}
#: §10y's finer reading as -7's driver answers it (``page_reading.mjs``). Invented ids and counts.
_FINER = {
    "axe_nodes": {"critical": 0, "serious": 4, "moderate": 2, "minor": 0},
    "failing": {
        "accessibility": ["label", "color-contrast"],
        "best_practices": [],
        "environment": ["redirects-http", "is-on-https"],
        "axe": ["color-contrast", "label", "region"],
    },
    "errored": {"accessibility": [], "best_practices": [], "environment": []},
    "best_practices_app": 1,
    "best_practices_app_error": None,
}


def _page(**changes) -> dict:
    return {"path": "/", "lighthouse": _LIGHTHOUSE, "axe": _AXE, **_FINER, "error": None, **changes}


def test_the_evaluators_answer_is_read_page_by_page_in_the_order_asked():
    """Read live on the Spark (2026-10-18): the driver's keys are Lighthouse's own
    (``best-practices``). Bug caught: that category read as missing, a page that painted
    nothing scored as an empty document, or §10y's lists kept in the driver's order, so the same
    set reads as two."""
    answer = {
        "pages": [
            _page(),
            {"path": "/runs", "lighthouse": None, "axe": None, "error": "lighthouse: NO_FCP"},
        ]
    }

    first, second = evaluator_pages(answer, ["/", "/runs"])

    assert first == PageMeasure(
        "/",
        {"performance": 0.93, "accessibility": 0.96, "best_practices": 0.78},
        {"critical": 0, "serious": 1, "moderate": 2, "minor": 0},
        axe_nodes={"critical": 0, "serious": 4, "moderate": 2, "minor": 0},
        failing={
            "accessibility": ("color-contrast", "label"),
            "best_practices": (),
            "environment": ("is-on-https", "redirects-http"),
            "axe": ("color-contrast", "label", "region"),
        },
        errored={"accessibility": (), "best_practices": (), "environment": ()},
        best_practices_app=1,
    )
    assert second == PageMeasure("/runs", error="lighthouse: NO_FCP")
    assert not second.finer


def test_a_null_category_reads_as_a_null_list_and_its_errored_audits_apart():
    """§10y: an errored audit nulls its category, and the list with it. Bug caught: the null list
    read as an empty one, so every id failing before reads as resolved."""
    answer = {
        "pages": [
            _page(
                lighthouse={**_LIGHTHOUSE, "accessibility": None},
                failing={**_FINER["failing"], "accessibility": None},
                errored={**_FINER["errored"], "accessibility": ["aria-roles"]},
            )
        ]
    }

    [page] = evaluator_pages(answer, ["/"])

    assert page.failing is not None and page.failing["accessibility"] is None
    assert page.errored == {
        "accessibility": ("aria-roles",),
        "best_practices": (),
        "environment": (),
    }


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        ({"pages": [{"path": "/runs/new"}]}, "other pages"),
        ({"pages": []}, "other pages"),
        ({"result": "ok"}, "other pages"),
        (
            {"pages": [{"path": "/", "lighthouse": _LIGHTHOUSE, "axe": _AXE, "error": "x"}]},
            "scored and in error",
        ),
        ({"pages": [{"path": "/", "lighthouse": None, "axe": _AXE}]}, "neither scored"),
    ],
    ids=["another-page", "no-page", "no-pages-key", "scored-and-failed", "half-scored"],
)
def test_an_answer_that_doesnt_say_what_each_page_got_is_refused(answer, message):
    """Bug caught: a page the evaluator skipped read as measured, or a page both scored and in
    error counted toward a baseline."""
    with pytest.raises(ValueError, match=message):
        evaluator_pages(answer, ["/"])


_NO_FINER = {k: v for k, v in _page().items() if k not in _FINER}


@pytest.mark.parametrize(
    ("page", "message"),
    [
        (_NO_FINER, "no axe_nodes, failing, errored, best_practices_app, which -7's"),
        ({**_page(), "best_practices_app": None, "axe_nodes": None}, "axe_nodes by"),
        (_page(failing={**_FINER["failing"], "axe": None}), "failing.axe is None"),
        (_page(failing={**_FINER["failing"], "best_practices": None}), "failing.best_practices"),
        (
            _page(
                lighthouse={**_LIGHTHOUSE, "best-practices": None},
                failing={**_FINER["failing"], "best_practices": None},
            ),
            "failing.environment",
        ),
        (_page(failing={k: v for k, v in _FINER["failing"].items() if k != "environment"}), "by"),
        (_page(errored={"accessibility": []}), "errored by"),
        (_page(failing={**_FINER["failing"], "axe": "region"}), "a list of ids"),
        (_page(best_practices_app_error="recomputed 0.5"), "beside a null category or error"),
        (
            {"path": "/", "lighthouse": None, "axe": None, "error": "x", "axe_nodes": {}},
            "a finer reading of a page in error",
        ),
    ],
    ids=[
        "a-scored-page-without-it",
        "nodes-null",
        "axe-list-null",
        "a-scored-categorys-list-null",
        "environment-listed-beside-a-null-category",
        "a-list-missing",
        "errored-lists-missing",
        "ids-not-a-list",
        "a-reading-beside-its-error",
        "a-page-in-error-with-it",
    ],
)
def test_a_page_whose_finer_reading_is_missing_or_contradicts_its_scores_is_refused(page, message):
    """§10y: ``evaluator_pages`` refuses a -7 page that lacks the finer reading rather than
    defaulting it. Bug caught: a missing key read as zero nodes or no failing id, so a page
    measured by an older driver reads as a clean one; or a list that its category's score
    contradicts compared as if it were read."""
    with pytest.raises(ValueError, match=message):
        evaluator_pages({"pages": [page]}, ["/"])


def test_only_the_routes_that_load_as_they_are_are_measured():
    """A route with a parameter can't be loaded without data the scenarios create. Bug caught:
    ``/runs/:run_id`` loaded literally, so its 404 reads as a page with an error on every tree,
    or a route declared twice measured twice."""
    routes = ["/", "/runs/new", "/runs/:run_id", "/runs/{run_id}/edit", "/runs/[id]", "*", "/"]

    assert measurable_pages(routes) == ("/", "/runs/new")
    assert measurable_pages([]) == ()


@pytest.mark.parametrize(
    "build",
    [
        lambda: QualityReading(QualityStatus.NOT_MEASURED),
        lambda: QualityReading(QualityStatus.MEASURED, reason=NotMeasured.START_FAILED),
        lambda: QualityReading(QualityStatus.NOT_APPLICABLE, pages=(PageMeasure("/", error="x"),)),
    ],
    ids=["not-measured-without-why", "measured-with-a-reason", "not-applicable-with-pages"],
)
def test_a_reading_says_why_only_when_it_wasnt_measured(build):
    """§4.2: not measured and not applicable are records that a measure didn't run, never
    evidence. Bug caught: a reading that carries pages while saying it didn't measure them, or a
    gap with no reason a reader can count."""
    with pytest.raises(ValueError):
        build()


def test_a_reading_survives_its_wire_and_store_form():
    """The runner answers over HTTP and the store keeps JSON. Bug caught: a reason, a page's
    error or the evaluator's tag lost on the way."""
    readings = [
        QualityReading(
            QualityStatus.MEASURED,
            pages=(PageMeasure("/", {"performance": 0.5}, {"critical": 1}),),
            evaluator="squadops-evaluator:x",
        ),
        QualityReading.not_measured(NotMeasured.UI_NOT_READY, "nothing answered"),
        QualityReading(QualityStatus.NOT_APPLICABLE),
        QualityReading(
            QualityStatus.MEASURED,
            pages=evaluator_pages({"pages": [_page()]}, ["/"]),
            evaluator="e",
        ),
    ]

    assert [QualityReading.from_dict(r.as_dict()) for r in readings] == readings


def test_a_page_measured_before_the_finer_reading_reads_as_not_having_it_and_keeps_its_form():
    """§10y: an earlier reading has none of the new keys. Bug caught: it read back with zero
    nodes or empty lists, or its stored form gained keys, so a package rebuilt from it changes
    identity."""
    stored = {
        "path": "/",
        "lighthouse": {"performance": 0.9, "accessibility": 1, "best_practices": 0.78},
        "axe": {"critical": 0, "serious": 0, "moderate": 1, "minor": 0},
        "error": None,
    }

    page = PageMeasure.from_dict(stored)

    assert (page.finer, page.axe_nodes, page.failing, page.best_practices_app) == (
        False,
        None,
        None,
        None,
    )
    assert page.as_dict() == stored
