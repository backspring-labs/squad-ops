"""The accepted-page inventory (SIP-0109 §24dq, #2783): the pages a repository-backed campaign's
accepted increments added, with the test ids each page carried when acceptance held it.

A product's change request carries no manifest delta (§24bv point 5), so these records are the
only place an added page's anchor is known after its increment is accepted. The wiring through
the promotion and the next launch is ``test_campaign_branch``'s; the rails', the proposer's and
acceptance's readings are each in their own module's tests.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from squadops.campaigns.models import ControlLogEntry, ControlOperation, ControlOutcome
from squadops.campaigns.product_routes import AcceptedPagesUnreadable, page_inventory, pages_held
from squadops.campaigns.progress import accepted_pages


def _promotion(seq: int, pages=(), outcome=ControlOutcome.APPLIED, binding=None) -> ControlLogEntry:
    """A repository-backed increment's promotion, its binding as ``_promote_onto_branch`` writes
    it: ``pages`` is its ``accepted_pages``, written on every one since §24dr item 4, and ``None``
    is a row written before §24dq, which carries none."""
    if binding is None:
        binding = {
            "cycle_id": f"cyc_{seq}",
            "identity": f"tree-{seq}",
            "commit": f"{seq:040x}",
            **({"accepted_pages": list(pages)} if pages is not None else {}),
        }
    return ControlLogEntry(
        entry_id=f"ctl_{seq}",
        campaign_id="cmp_t",
        seq=seq,
        operation=ControlOperation.PROMOTE,
        actor="squadops",
        actor_role="completion",
        reason="r",
        target=f"cyc_{seq}",
        idempotency_key=f"promote:{seq}",
        request_hash="h",
        binding=binding,
        outcome=outcome,
        refusal=None,
        prior_state="building",
        next_state="building",
        committed_at=datetime(2026, 11, 8, 12, seq, tzinfo=UTC),
    )


def _page(route: str, anchor: str, *others: str) -> dict:
    return {"route": route, "anchor": anchor, "testids": [anchor, *others]}


def test_the_inventory_is_every_page_the_applied_promotions_added():
    """Bugs caught: only the latest promotion's pages read, so a page two increments back is
    forgotten and its anchor reusable again; a refused promotion's page counted, though its tree
    was never accepted; or a later increment that added no page erasing the earlier ones."""
    log = [
        _promotion(1, [_page("/totals", "totals-view", "totals-row")]),
        _promotion(2, [_page("/export", "export-view")], outcome=ControlOutcome.REFUSED),
        _promotion(3),
        _promotion(4, [_page("/archive", "archive-view")]),
    ]

    assert accepted_pages(log) == (
        _page("/archive", "archive-view"),
        _page("/totals", "totals-view", "totals-row"),
    )


#: A calibration's promotion, as the calibration record's writes it: it adds no page.
_CALIBRATION = {"commit": "a" * 40, "identity": "tree-0", "calibration_record_id": "calrec_t"}


def test_a_promotion_written_before_the_inventory_refuses_the_read_naming_its_row():
    """SIP-0109 §24dr item 5: a Campaign that accepted an increment under the code before §24dq,
    resumed under this one. Its row records no pages, though the increment may have added some.
    Bug caught: the row read as having added none, so the next proposal may reuse that page's
    anchor, and a page never built holds where the fallback renders it: #2783 again, for every
    Campaign that straddles the deploy. A calibration's row (no page) and a refused row (no tree
    accepted) are never refused for it."""
    calibrated = [_promotion(0, binding=_CALIBRATION), _promotion(1, None, ControlOutcome.REFUSED)]
    assert accepted_pages([*calibrated, _promotion(2)]) == ()

    with pytest.raises(AcceptedPagesUnreadable) as refused:
        accepted_pages([*calibrated, _promotion(2), _promotion(3, None)])

    assert str(refused.value).startswith(
        "the accepted-page inventory can't be read: campaign cmp_t's promotion of cyc_3 "
        "(control-log row 3, ctl_3) was written before SIP-0109 §24dq"
    )
    assert "abort the Campaign and contribute its accepted increments" in str(refused.value)


def test_a_record_the_fold_cant_read_refuses_it_naming_its_row():
    """§24dr item 6: the persisted inventory is read before the proposal launches. Bug caught: a
    record with no anchor skipped, or failing only inside the proposal's task, where a model's
    revision can't fix a control-log row."""
    log = [_promotion(1, [_page("/totals", "totals-view")]), _promotion(2, [{"route": "/x"}])]

    with pytest.raises(AcceptedPagesUnreadable, match=r"row 2, ctl_2\): .*names no route or no"):
        accepted_pages(log)


@pytest.mark.parametrize(
    ("route", "page"),
    [
        (
            {"source": "accepted_page", "anchor": "t-view", "seen": ["t-new", "t-view"]},
            _page("/t", "t-view", "t-new"),
        ),
        (
            {"source": "approved_manifest", "anchor": "pin", "seen": ["pin", "t-new", "t-view"]},
            _page("/t", "t-view", "pin", "t-new"),
        ),
    ],
    ids=["an-accepted-page", "an-accepted-page-the-profile-pins"],
)
def test_a_page_of_the_inventory_that_held_is_recorded_again_under_its_accepted_root(route, page):
    """§24dr item 2: an accepted page acceptance held again is recorded with the ids it carries
    now, under the root it was accepted with, a route the profile pins too. Bugs caught: the
    record never refreshed, so an id a later increment gave it is free to reuse; or the root
    replaced by the pin's, so the page's accepted anchor is lost."""
    record = {"route": "/t", "held": "held", "accepted_root": "t-view", **route}

    assert pages_held({"renderings": {"routes": [record]}}) == [page]


@pytest.mark.parametrize(
    "route",
    [
        {"route": "/", "source": "approved_manifest", "held": "held", "anchor": "home-view"},
        {"route": "/x", "source": "change_request", "held": "broken", "anchor": "x-view"},
        {"route": "/y", "source": "change_request", "held": "blocked_unverified", "anchor": None},
        {"route": "/z", "source": "accepted_page", "held": "broken", "accepted_root": "z-view"},
    ],
    ids=["a-pinned-page", "a-page-not-held", "a-page-with-no-anchor", "an-accepted-page-not-held"],
)
def test_only_a_page_the_change_added_and_acceptance_held_is_recorded(route):
    """Bugs caught: a pinned page recorded as added, so a later request's criterion on it is
    refused for an anchor it never names; or a page acceptance didn't hold recorded with an
    anchor the accepted tree may not render."""
    assert pages_held({"renderings": {"routes": [{**route, "seen": ["x-view"]}]}}) == []
    assert pages_held({"verdict": "accepted"}) == []


@pytest.mark.parametrize(
    "records",
    [[{"route": "/totals"}], [{"anchor": "totals-view"}], ["/totals"]],
    ids=["no-anchor", "no-route", "not-a-record"],
)
def test_a_page_the_inventory_cant_read_is_refused_never_skipped(records):
    """The inventory is the only record of these pages' anchors. Bug caught: an unreadable
    record skipped, so the anchor it held is reusable and a page never built holds again."""
    with pytest.raises(ValueError, match="names no route or no anchor"):
        page_inventory(records)

    assert page_inventory(None) == {}
    assert page_inventory([_page("/t", "t-view", "t-row", "t-view")]) == {"/t": ("t-view", "t-row")}


def _rendered(route: str, source: str, anchor: str, *seen: str) -> dict:
    """What acceptance's renderer recorded of one held page (``product_routes.route_record``): a
    page of the inventory names the root it was accepted with."""
    root = {"accepted_root": anchor} if source == "accepted_page" else {}
    return {"renderings": {"routes": [
        {"route": route, "source": source, "held": "held", "anchor": anchor, "seen": list(seen), **root},
    ]}}  # fmt: skip


def test_an_id_a_later_increment_put_on_an_accepted_page_is_taken_for_the_next_proposal():
    """The outside review's item 2 (SIP-0109 §24dr), over three increments: the first adds
    ``/totals``; the second changes it, and its accepted page now carries ``totals-share`` too;
    the third proposes ``/summary`` naming ``totals-share``. Each promotion's record is written by
    the recorder from what acceptance held, folded as the launch folds it, and read by the rails
    as the proposal's handler reads the block. Bug caught: an accepted page's ids recorded only
    when it was added, so the id the second increment gave it is free for a page never built."""
    from squadops.campaigns.change_request import RefusalKind, validate_proposal
    from tests.unit.campaigns.test_product_change_request import (
        _WITH_PAGES,
        _context,
        _on_a_page,
        _request,
    )

    first = _rendered("/totals", "change_request", "totals-view", "totals-view")
    second = _rendered("/totals", "accepted_page", "totals-view", "totals-view", "totals-share")
    log = [_promotion(1, pages_held(first)), _promotion(2, pages_held(second))]
    product = dataclasses.replace(
        _WITH_PAGES,
        judged_routes=(),
        accepted_pages=tuple(page_inventory(list(accepted_pages(log))).items()),
    )

    verdict = validate_proposal(
        _request(criteria=[_on_a_page("/summary", "totals-share")]), _context(product=product)
    )

    assert accepted_pages(log) == ({"route": "/totals", "anchor": "totals-view", "testids": ["totals-view", "totals-share"]},)  # fmt: skip
    [refusal] = verdict.refusals
    assert refusal.kind is RefusalKind.ANCHOR_NOT_UNIQUE
    assert "and /totals already carries it" in refusal.detail
