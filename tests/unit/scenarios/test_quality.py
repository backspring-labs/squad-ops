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


def test_the_evaluators_answer_is_read_page_by_page_in_the_order_asked():
    """Read live on the Spark (2026-10-18): the driver's keys are Lighthouse's own
    (``best-practices``). Bug caught: that category read as missing, or a page that painted
    nothing scored as an empty document."""
    answer = {
        "pages": [
            {"path": "/", "lighthouse": _LIGHTHOUSE, "axe": _AXE, "error": None},
            {"path": "/runs", "lighthouse": None, "axe": None, "error": "lighthouse: NO_FCP"},
        ]
    }

    first, second = evaluator_pages(answer, ["/", "/runs"])

    assert first == PageMeasure(
        "/",
        {"performance": 0.93, "accessibility": 0.96, "best_practices": 0.78},
        {"critical": 0, "serious": 1, "moderate": 2, "minor": 0},
    )
    assert (second.lighthouse, second.axe, second.error) == (None, None, "lighthouse: NO_FCP")


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
    ]

    assert [QualityReading.from_dict(r.as_dict()) for r in readings] == readings
