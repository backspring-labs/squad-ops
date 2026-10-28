"""The rails on a repository-backed Project (SIP-0109 §24bv point 5, and §24cj's scope ruling).

Entered at ``validate_proposal``, the one function the proposal task's handler calls, with the
product context the run composes: the shared fixture's Tally as its derived profile was recorded,
its tree as the fixture holds it. The documents are invented changes to Tally.
"""

from __future__ import annotations

import dataclasses

import pytest
import yaml

from squadops.campaigns.change_request import (
    IncrementBasis,
    PlacedCriterionFile,
    ProductContext,
    ProposalContext,
    RefusalKind,
    load_stored_change_request,
    stored_change_request,
    validate_proposal,
)
from squadops.campaigns.criterion_placement import runner_placements
from squadops.projects.derived_profile import parse_profile
from tests.fixtures.shared_contract.repository import product_files, recorded

_PROFILE = parse_profile(recorded("derived_profile", "valid"))
#: Tally's surfaces as the proposal's handler reads them (``product_context``).
_PRODUCT = ProductContext(
    surfaces=(
        ("http_base", "http://127.0.0.1:18407/"),
        ("command", "python3 -m tally"),
        ("package", "tally"),
    ),
    placements=runner_placements(_PROFILE.runners, _PROFILE.gaps, product_files()),
    test_files=_PROFILE.test_files,
)


def _context(scope=("tally/**",), product=_PRODUCT, prior=()) -> ProposalContext:
    return ProposalContext(
        proposal_id="prop_tally0001",
        version=1,
        baseline_tree="f" * 64,
        baseline_manifest="",
        expected_stack="",
        allowed_scope=scope,
        prior_criteria=prior,
        product=product,
    )


def _request(**overrides) -> dict:
    authored = {
        "kind": "feature",
        "prd_delta": [{"id": "report-totals", "op": "add", "text": "The report ends in a total."}],
        "footprint": ["tally/report.py"],
        "criteria": [
            {
                "id": "R1",
                "statement": "The report's last line is the total of its amounts",
                "surface_kind": "package",
                "surface": "tally.report",
                "observable": "render([3, 4])'s last line is 'total 7'",
            }
        ],
        "must_not_break": [],
    }
    authored.update(overrides)
    return authored


def test_an_accepted_product_request_carries_its_basis_footprint_and_placed_criterion_file():
    """The accepted shape. Bugs caught: the placed criterion file left out of the footprint, so
    the build may not write the test the evaluation runs; the placement not stored, so every reader
    after the proposal places it again (or can't, with no stack); the basis not stored, so the
    request reads back as a sample application's and its authored footprint is dropped."""
    verdict = validate_proposal(_request(), _context())

    assert verdict.accepted, verdict.refusals
    request = verdict.change_request
    assert request.basis is IncrementBasis.CAMPAIGN_BRANCH
    assert request.footprint == ("tally/report.py", "checks/check_criterion_R1.py")
    assert request.criterion_files == (PlacedCriterionFile("R1", "checks/check_criterion_R1.py"),)
    assert load_stored_change_request(stored_change_request(request)) == request


def test_the_ruling_binds_the_authored_footprint():
    """§9.2 on a product, where the footprint is authored. Bug caught: the footprint left out of
    the hash as a derived field, so a stored request whose footprint was widened after the ruling
    loads as the request that was ruled on."""
    request = validate_proposal(_request(), _context()).change_request
    data = yaml.safe_load(stored_change_request(request))
    data["footprint"] = ["tally/**", "checks/check_criterion_R1.py"]

    with pytest.raises(ValueError, match="does not match its hash"):
        load_stored_change_request(yaml.safe_dump(data))


@pytest.mark.parametrize(
    ("overrides", "kind", "detail"),
    [
        (
            {"manifest_delta": [{"op": "remove", "target": "entity", "key": "Run"}]},
            RefusalKind.MANIFEST_DELTA_ON_PRODUCT,
            "no interface manifest",
        ),
        ({"footprint": []}, RefusalKind.NOTHING_TO_BUILD, "names no file"),
        ({"footprint": ["tally/report.py", "tools/build.py"]}, RefusalKind.OUT_OF_SCOPE, "tools"),
        (
            {"footprint": ["/etc/passwd"]},
            RefusalKind.MALFORMED,
            "leaves the product's repository",
        ),
    ],
    ids=["a manifest delta", "no footprint", "out of scope", "an absolute path"],
)
def test_a_product_request_breaking_a_rail_is_refused_by_name(overrides, kind, detail):
    """Bug caught: a product request with a manifest delta, nothing to build, a footprint outside
    the objective's scope, or a path outside the product, reaching the gate."""
    verdict = validate_proposal(_request(**overrides), _context())

    assert not verdict.accepted
    assert [r.kind for r in verdict.refusals if r.kind is kind], verdict.refusals
    assert any(detail in r.detail for r in verdict.refusals if r.kind is kind)


def test_the_products_own_tests_are_the_scopes_and_the_placed_criterion_file_is_not():
    """§24cj, the supervisor's ruling under the owner's delegation: on a product, only the criterion
    test files the framework places are the framework's. Bugs caught: the product's own test edits
    let through a scope of its source alone (the scope stops governing them); or the placed
    criterion file read against the scope, so a scope of ``tally/**`` admits no criterion at all."""
    own_test = _request(footprint=["tally/report.py", "checks/check_report.py"])

    refused = validate_proposal(own_test, _context())
    placed_only = validate_proposal(_request(), _context(scope=("tally/report.py",)))
    widened = validate_proposal(own_test, _context(scope=("tally/**", "checks/check_report.py")))

    [out] = [r for r in refused.refusals if r.kind is RefusalKind.OUT_OF_SCOPE]
    assert "checks/check_report.py" in out.detail and "tally/report.py" not in out.detail
    assert placed_only.accepted, placed_only.refusals
    assert widened.accepted, widened.refusals


@pytest.mark.parametrize(
    ("criterion", "detail"),
    [
        ({"surface_kind": "command", "surface": "tally-cli export"}, "no command 'tally-cli"),
        ({"surface_kind": "package", "surface": "tallyx"}, "no package 'tallyx'"),
        ({"surface_kind": "client_route", "surface": "/report"}, "no UI base"),
        ({"surface_kind": "endpoint", "surface": "/report"}, "no endpoint"),
    ],
    ids=["an undeclared command", "another package", "a page with no UI", "an endpoint unwritten"],
)
def test_a_criterion_on_a_surface_the_profile_doesnt_name_is_refused(criterion, detail):
    """§24bv point 5: a criterion asserts at a surface the derived profile names. Bugs caught: a
    criterion on a command or package Tally doesn't declare, or on a page with no UI base,
    admitted, so its test asserts where no caller reaches."""
    authored = _request()
    authored["criteria"][0].update(criterion)

    verdict = validate_proposal(authored, _context())

    [refusal] = [r for r in verdict.refusals if r.kind is RefusalKind.UNKNOWN_SURFACE]
    assert detail in refusal.detail


@pytest.mark.parametrize(
    "surface",
    [("command", "python3 -m tally report"), ("endpoint", "GET /report"), ("package", "tally")],
)
def test_a_criterion_on_a_declared_surface_or_under_one_is_accepted(surface):
    """Bug caught: a subcommand of a declared command, an endpoint under the HTTP base, or the
    package itself refused as unknown."""
    authored = _request()
    authored["criteria"][0].update(surface_kind=surface[0], surface=surface[1])

    assert validate_proposal(authored, _context()).accepted


def test_a_criterion_whose_paths_leave_the_footprint_or_no_runner_tests_is_refused():
    """Bugs caught: a criterion exercising a file the build may not touch, or one no runner can
    host, accepted and frozen with no test file the product's checks run."""
    stray, untested = _request(), _request(footprint=["tally/report.py", "tools/build.py"])
    stray["criteria"][0]["paths"] = ["tally/ledger.py"]
    untested["criteria"][0]["paths"] = ["tools/build.py"]

    stray_verdict = validate_proposal(stray, _context())
    untested_verdict = validate_proposal(untested, _context(scope=("tally/**", "tools/**")))

    assert [r.kind for r in stray_verdict.refusals] == [RefusalKind.SURFACE_OUTSIDE_FOOTPRINT]
    assert [r.kind for r in untested_verdict.refusals] == [RefusalKind.UNPLACEABLE_CRITERION]
    assert "no runner's tests cover tools/build.py" in untested_verdict.refusals[0].detail


def test_a_sample_applications_request_still_refuses_a_footprint_and_criterion_paths():
    """The manifest rails are unchanged. Bug caught: the product's authored fields admitted on a
    sample application, whose footprint the stack's scaffold map derives."""
    sample = dataclasses.replace(_context(), product=None, baseline_manifest="api: {}\n")

    footprint = validate_proposal({**_request(), "manifest_delta": []}, sample)
    criterion = _request()
    del criterion["footprint"]
    criterion["criteria"][0]["paths"] = ["tally/report.py"]

    assert [r.kind for r in footprint.refusals] == [RefusalKind.AUTHORED_DERIVED_FIELD]
    assert "paths are named only on a repository-backed Project" in (
        validate_proposal(criterion, sample).refusals[0].detail
    )


# --- the outside review of #2771 (§24cj): unique placements, and a placement bound and checked --


def _two(first: str, second: str) -> dict:
    authored = _request()
    authored["criteria"].append({**authored["criteria"][0], "id": second})
    authored["criteria"][0]["id"] = first
    return authored


@pytest.mark.parametrize(
    ("ids", "prior", "kind", "named"),
    [
        (("T-1", "T_1"), (), RefusalKind.CRITERION_FILE_COLLISION, "criteria T-1, T_1 would share"),
        (("R1", "R1"), (), RefusalKind.DUPLICATE_CRITERION, "criterion R1 is named 2 times"),
        (("T-1", "R2"), ("T_1",), RefusalKind.CRITERION_FILE_COLLISION, "rename T-1"),
    ],
    ids=["two ids one file", "one id twice", "an id naming a frozen criterion's file"],
)
@pytest.mark.parametrize("basis", ["product", "sample application"])
def test_two_criteria_that_would_share_a_test_file_are_refused_by_name(
    ids, prior, kind, named, basis
):
    """The review's P1. ``T-1`` and ``T_1`` both name ``check_criterion_T_1.py``. Bugs caught: the
    second criterion's test overwriting the first's, one verifier bundle frozen for two criteria,
    and on a later increment a new criterion's file overwriting a frozen one's. Both bases name a
    file the same way (``scaffold.criterion_module_name``), so both refuse it."""
    context = _context(prior=prior)
    if basis == "sample application":
        context = dataclasses.replace(context, product=None, baseline_manifest="api: {}\n")
    authored = _two(*ids)
    if basis == "sample application":
        del authored["footprint"]

    verdict = validate_proposal(authored, context)

    assert not verdict.accepted
    [refusal] = [r for r in verdict.refusals if r.kind is kind]
    assert named in refusal.detail


def test_a_placement_that_puts_two_criteria_at_one_path_is_refused_whatever_placed_them():
    """Unique placed paths across the proposal, checked on the placements themselves, not only on
    the ids. Bug caught: a runner whose template names no criterion (a malformed placement handed
    to the rails as data) placing every criterion at one file, accepted."""
    from squadops.campaigns.criterion_placement import RunnerPlacement

    one_file = RunnerPlacement("unittest", ("report",), ("tally/**",), "checks/check_fixed.py")
    context = _context(product=dataclasses.replace(_PRODUCT, placements=(one_file,)))

    verdict = validate_proposal(_two("R1", "R2"), context)

    [refusal] = verdict.refusals
    assert refusal.kind is RefusalKind.CRITERION_FILE_COLLISION
    assert refusal.detail.startswith("criteria R1, R2 would all be placed at checks/check_fixed.py")


def _stored(**edit) -> str:
    """The accepted request's stored document, with ``edit`` applied to its data after the
    ruling, its hash left as the ruling bound it."""
    data = yaml.safe_load(
        stored_change_request(validate_proposal(_request(), _context()).change_request)
    )
    for key, value in edit.items():
        data[key] = value(data) if callable(value) else value
    return yaml.safe_dump(data, sort_keys=False)


@pytest.mark.parametrize(
    ("edit", "refused"),
    [
        # Moved, with its footprint entry moved to match: only the hash can tell.
        (
            {
                "criterion_files": [
                    {"criterion_id": "R1", "path": "checks/check_criterion_R1x.py"}
                ],
                "footprint": ["tally/report.py", "checks/check_criterion_R1x.py"],
            },
            "not named for it",
        ),
        (
            {
                "criterion_files": [{"criterion_id": "R1", "path": "tests/check_criterion_R1.py"}],
                "footprint": ["tally/report.py", "tests/check_criterion_R1.py"],
            },
            "does not match its hash",
        ),
        ({"criterion_files": []}, "its criteria are R1, and it places none"),
        (
            {
                "criterion_files": [{"criterion_id": "R1", "path": "checks/check_criterion_R1.py"}]
                * 2
            },
            "each criterion once",
        ),
        ({"footprint": ["tally/report.py"]}, "is not in the footprint"),
        (
            {"criterion_files": [{"criterion_id": "R9", "path": "checks/check_criterion_R9.py"}]},
            "it places R9",
        ),
    ],
    ids=[
        "renamed for no criterion",
        "moved under another root",
        "dropped",
        "placed twice",
        "left out of the footprint",
        "placed for another criterion",
    ],
)
def test_a_stored_placement_changed_after_the_ruling_is_refused_by_name(edit, refused):
    """The review's P2. The placement is derived, and every reader after the ruling reads it from
    the stored request. Bugs caught: a placement edited in the vault (the test moved, dropped,
    doubled, renamed, left out of what the build may write) read as the one ruled on, so the build
    writes, and the evaluation freezes, a file nobody approved."""
    with pytest.raises(ValueError, match=refused):
        load_stored_change_request(_stored(**edit))


def test_a_sample_applications_request_carrying_a_placement_is_refused():
    """The mirror: a sample application's stack places its criteria. Bug caught: a placement
    written into its stored request read by ``increment_criterion_files`` over the stack's."""
    from tests.unit.campaigns.test_change_request import _STORED_REQUESTS

    stored = _STORED_REQUESTS[0].read_text()  # a request stored by a live campaign, as stored
    load_stored_change_request(stored)
    data = yaml.safe_load(stored)
    data["criterion_files"] = [{"criterion_id": "T1", "path": "backend/tests/x.py"}]

    with pytest.raises(ValueError, match="a sample application's request places no criterion"):
        load_stored_change_request(yaml.safe_dump(data, sort_keys=False))
