"""#1031: an error code answers with the status its name commits it to, or says why not.

What bugs would these catch?
- The 1.6.1 shakedown's: ``participant_not_found`` mapped to 400, and 404 never entered the
  author's frame. In the stored corpus (244 authored manifests) the same code answered 409, 422,
  400 and 424, and ``duplicate_participant`` answered 400.
- A departure the author warranted, refused anyway: the gate polices an unexamined departure,
  not taste.
- A warrant about something else accepted as one about the status (#1067's lesson: a decision
  naming the endpoint said nothing about its status).
- A name that commits to no convention checked against a guess.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadops.capabilities.error_status import error_convention
from squadops.cycles.manifest_gates import PROOF_ERROR_STATUS_WARRANTED, assess_winnability

_REFERENCE = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


@pytest.mark.parametrize(
    ("code", "statuses"),
    [
        ("participant_not_found", {404}),
        ("run_does_not_exist", {404}),
        ("already_joined", {409}),
        ("duplicate_participant", {409}),
        ("validation_error", {400, 422}),
        ("invalid_pace", {400, 422}),
        ("run_full", None),
        ("notfound", None),
    ],
)
def test_a_name_commits_to_a_convention_only_when_it_says_which(code, statuses):
    convention = error_convention(code)
    assert (convention.statuses if convention else None) == (
        frozenset(statuses) if statuses else None
    )


def _manifest(http: int, decisions: list[dict] | None = None) -> str:
    doc = yaml.safe_load(_REFERENCE.read_text())
    doc["api"]["error_contract"]["codes"]["participant_not_found"] = {"http": http}
    if decisions is not None:
        doc["decisions"] = [*doc.get("decisions", []), *decisions]
    return yaml.safe_dump(doc, sort_keys=False)


def _error_status(findings):
    return [f for f in findings if f.proof == PROOF_ERROR_STATUS_WARRANTED]


def test_the_shakedowns_400_is_reported_naming_the_convention():
    """Entered at ``assess_winnability``, the framing gate's caller. Advisory first (#820's
    discipline): reported to the author and counted apart, never a rejection, until its own
    evidence promotes it."""
    [finding] = _error_status(assess_winnability(_manifest(400)))

    assert "`participant_not_found` answers 400" in finding.detail
    assert "a lookup that found nothing, which answers 404" in finding.detail
    assert finding.advisory is True


@pytest.mark.parametrize(
    ("http", "decisions", "flagged"),
    [
        (404, None, False),
        (
            400,
            [
                {
                    "id": "pnf-400",
                    "choice": "participant_not_found returns 400",
                    "warrant": "PRD §5.4",
                }
            ],
            False,
        ),
        (
            400,
            [
                {
                    "id": "pnf",
                    "choice": "participant_not_found is raised by leave",
                    "warrant": "PRD §5.4",
                }
            ],
            True,
        ),
    ],
    ids=["the-convention", "a-warranted-departure", "a-warrant-about-something-else"],
)
def test_only_an_unexamined_departure_is_returned(http, decisions, flagged):
    assert bool(_error_status(assess_winnability(_manifest(http, decisions)))) is flagged


def test_the_reference_manifest_answers_every_code_by_its_convention():
    """The control: every roll of the reference scenario binds this manifest."""
    assert _error_status(assess_winnability(_REFERENCE.read_text())) == []
