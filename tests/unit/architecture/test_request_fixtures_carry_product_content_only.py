"""A cycle request must not name a document the framework owns (#1427).

The group_run PRD's own §0 carries the rule — "this PRD carries **product content
only**: features, behaviors, scope, and priorities … never by adding endpoint tables,
data models, file lists, or test mechanics back into this document" — and SIP-0098
§6.7 moved four sections out to their owning artifacts, leaving *moved* tombstones.

`qa_handoff` survived that sweep, in seven places, because unlike the endpoints and
the data model it had nowhere to move TO: it was a framework-required file that no
artifact owned and nothing read. When #1312 retired it from every checking surface,
nothing connected that to the request still demanding it. The drift stayed invisible
until a live roll on the pack showed the builder still emitting it — and the same
roll's Next.js half emitted `QA_HANDOFF.md`, which under the retired contract would
have failed the case-sensitive basename match and rejected an otherwise clean build.

§0's rule was prose, and prose does not hold: what a test enforces stays true.

The banned set is **derived, never listed here** — every module-level ``*_DOCUMENT``
constant in ``squadops.capabilities.assembly_notes``, the module that owns the build's
documents. A hand-copied list in a test is the same drift one layer down.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from squadops.capabilities import assembly_notes

_REPO = Path(__file__).resolve().parents[3]
_FIXTURES = sorted(_REPO.glob("examples/*/prd*.md"))


def _framework_documents() -> dict[str, str]:
    """``{constant name: filename}`` for every build document the framework owns."""
    return {
        name: value
        for name, value in vars(assembly_notes).items()
        if name.endswith("_DOCUMENT") and isinstance(value, str) and value
    }


def offenders(text: str) -> list[str]:
    """The framework document names a request fixture mentions.

    Matches the **stem** as well as the filename: the seven group_run references
    said ``qa_handoff``, not ``qa_handoff.md``, so a check keyed on the filename
    alone would have passed every one of them.
    """
    found: list[str] = []
    for filename in _framework_documents().values():
        stem = Path(filename).stem
        if re.search(rf"\b{re.escape(stem)}\b", text):
            found.append(filename)
    return sorted(found)


def test_the_derived_banned_set_is_not_empty_and_names_the_documents_it_should():
    """A derivation that silently returns nothing makes every check below vacuous —
    rename the constants and the guard would pass by asking nothing."""
    documents = _framework_documents()
    assert set(documents.values()) >= {"assembly_notes.md", "qa_handoff.md"}, documents


def test_there_are_request_fixtures_to_check():
    """The glob is the guard's reach; an empty one passes everything."""
    assert len(_FIXTURES) >= 5, [p.name for p in _FIXTURES]


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: str(p.relative_to(_REPO)))
def test_no_request_fixture_names_a_framework_document(fixture: Path):
    named = offenders(fixture.read_text())
    assert not named, (
        f"{fixture.relative_to(_REPO)} names framework-owned document(s) {named}. "
        "A request carries product content only — what the build must produce for the "
        "framework is the framework's to declare, and a request that names it drifts "
        "silently when the framework changes (#1427)."
    )


@pytest.mark.parametrize(
    "text, expected",
    [
        ("- [ ] Build includes a clear `qa_handoff` artifact", ["qa_handoff.md"]),
        ("9. `qa_handoff`", ["qa_handoff.md"]),
        ("Require qa_handoff.md before cycle close", ["qa_handoff.md"]),
        ("the builder writes assembly_notes.md", ["assembly_notes.md"]),
        ("both: qa_handoff and assembly_notes", ["assembly_notes.md", "qa_handoff.md"]),
    ],
)
def test_the_detector_catches_the_forms_the_prd_actually_used(text, expected):
    """Bug caught: a detector keyed on the filename. Every real reference but one
    was the bare stem, so a filename-only check would have reported the PRD clean."""
    assert offenders(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "the run detail view shows participants",
        "a handoff between the frontend and backend teams",
        "notes on assembly are out of scope",
        "qa_handoff_v2_notes",
    ],
)
def test_the_detector_does_not_fire_on_product_prose(text):
    """The other half of the evidence: a guard that flags everything gets disabled.
    `qa_handoff_v2_notes` is the boundary case — a longer identifier is not a mention."""
    assert offenders(text) == []
