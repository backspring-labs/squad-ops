"""SIP-0107 step 4 (#1213) — the anchored-edit emission grammar.

Each test names what it catches: an edit block guessed into an edit it did not state, a
malformed block silently dropped, an edit fence swallowing the files emitted after it, or an
edit block left where the whole-file extractor would take it for a file.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.anchored_edits import (
    MALFORMED_EMPTY_SEARCH,
    MALFORMED_MISSING_DIVIDER,
    MALFORMED_MISSING_REPLACE,
    MALFORMED_NO_BLOCKS,
    MALFORMED_TEXT_OUTSIDE_BLOCK,
    MALFORMED_UNCLOSED_FENCE,
    MALFORMED_UNSAFE_PATH,
    AnchoredEdit,
    parse_anchored_edits,
    revisions_for,
    strip_edit_blocks,
)
from squadops.capabilities.handlers.fenced_parser import extract_fenced_files
from squadops.cycles.revision_transaction import (
    RevisionTransaction,
    base_revision_id,
    resolve_and_apply,
)
from squadops.cycles.write_authorization import WriteGrant

pytestmark = [pytest.mark.domain_capabilities]

_ROUTES = (
    "from fastapi import APIRouter\n"
    "router = APIRouter()\n"
    "\n"
    '@router.post("/runs")\n'
    "def create(payload):\n"
    "    return Run(**payload.dict())\n"
)

_RESPONSE = (
    "The handler must drop unset fields.\n"
    "\n"
    "```edit:./backend/routes.py\n"
    "<<<<<<< SEARCH\n"
    "    return Run(**payload.dict())\n"
    "=======\n"
    "    return Run(**payload.dict(exclude_none=True))\n"
    ">>>>>>> REPLACE\n"
    "\n"
    "<<<<<<< SEARCH\n"
    "from fastapi import APIRouter\n"
    "=======\n"
    "from fastapi import APIRouter, HTTPException\n"
    ">>>>>>> REPLACE\n"
    "```\n"
    "\n"
    "```markdown:docs/notes.md\n"
    "# Notes\n"
    "```\n"
)


def test_a_well_formed_response_parses_to_its_exact_edits_and_applies_them():
    """Entry: the grammar through to the transaction. Bug caught: an edit's text trimmed,
    re-indented or joined differently from how it was emitted — an anchor that then misses."""
    parse = parse_anchored_edits(_RESPONSE)

    assert parse.malformed == ()
    assert parse.edits == (
        AnchoredEdit(
            path="backend/routes.py",
            anchor="    return Run(**payload.dict())\n",
            replacement="    return Run(**payload.dict(exclude_none=True))\n",
        ),
        AnchoredEdit(
            path="backend/routes.py",
            anchor="from fastapi import APIRouter\n",
            replacement="from fastapi import APIRouter, HTTPException\n",
        ),
    )
    base = {"backend/routes.py": _ROUTES}
    outcome = resolve_and_apply(
        base,
        RevisionTransaction(
            base_revision_id=base_revision_id(base),
            grant=WriteGrant(
                producer="development.correction_repair",
                stage="dev_fill",
                writable=frozenset({"backend/routes.py"}),
            ),
            task_id="t",
            revisions=revisions_for(parse),
        ),
        lambda path, content, region: None,
    )
    assert outcome.changed_files() == {
        "backend/routes.py": _ROUTES.replace(
            "from fastapi import APIRouter\n", "from fastapi import APIRouter, HTTPException\n"
        ).replace("payload.dict())", "payload.dict(exclude_none=True))")
    }


def test_a_replacement_may_contain_fence_lines_and_delete_its_anchor():
    """Bug caught: a bare fence line inside REPLACE read as the edit fence's close, truncating
    a markdown replacement and leaking the rest as prose."""
    response = (
        "```edit:README.md\n"
        "<<<<<<< SEARCH\n"
        "Run it.\n"
        "=======\n"
        "Run it:\n"
        "```\n"
        "make up\n"
        "```\n"
        ">>>>>>> REPLACE\n"
        "<<<<<<< SEARCH\n"
        "Obsolete line.\n"
        "=======\n"
        ">>>>>>> REPLACE\n"
        "```\n"
    )

    (fenced, deleted) = parse_anchored_edits(response).edits

    assert fenced.replacement == "Run it:\n```\nmake up\n```\n"
    assert (deleted.anchor, deleted.replacement) == ("Obsolete line.\n", "")


@pytest.mark.parametrize(
    ("body", "reasons"),
    [
        ("<<<<<<< SEARCH\nx = 1\n```\n", [MALFORMED_MISSING_DIVIDER]),
        ("<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n```\n", [MALFORMED_MISSING_REPLACE]),
        ("<<<<<<< SEARCH\n\n=======\nx = 2\n>>>>>>> REPLACE\n```\n", [MALFORMED_EMPTY_SEARCH]),
        (
            "Here it is:\n<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE\n```\n",
            [MALFORMED_TEXT_OUTSIDE_BLOCK],
        ),
        ("```\n", [MALFORMED_NO_BLOCKS]),
        ("<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE\n", [MALFORMED_UNCLOSED_FENCE]),
    ],
    ids=["no divider", "no end marker", "empty search", "prose inside", "no blocks", "unclosed"],
)
def test_a_malformed_edit_fence_is_named_with_its_reason_never_dropped(body, reasons):
    parse = parse_anchored_edits(f"```edit:backend/routes.py\n{body}")

    assert [m.reason for m in parse.malformed] == reasons
    assert all(m.path == "backend/routes.py" for m in parse.malformed)
    assert parse.found


@pytest.mark.parametrize("path", ["/etc/passwd", "../outside.py"])
def test_an_unsafe_path_yields_no_edit(path):
    """Bug caught: an edit aimed outside the workspace carried into a transaction."""
    parse = parse_anchored_edits(
        f"```edit:{path}\n<<<<<<< SEARCH\nx\n=======\ny\n>>>>>>> REPLACE\n```\n"
    )
    assert parse.edits == ()
    assert [m.reason for m in parse.malformed] == [MALFORMED_UNSAFE_PATH]


def test_stripping_edit_fences_leaves_whole_files_for_the_extractor_and_no_edit_as_a_file():
    """Bug caught: ``edit:backend/routes.py`` matching the strict ``lang:path`` header and
    being stored as a file whose content is the SEARCH/REPLACE markers — or a malformed block
    swallowing the file emitted after it."""
    malformed_then_file = (
        "```edit:backend/routes.py\n<<<<<<< SEARCH\nx = 1\n```\n"
        "\n"
        "```python:backend/new.py\nY = 2\n```\n"
    )

    for response, files in (
        (_RESPONSE, ["docs/notes.md"]),
        (malformed_then_file, ["backend/new.py"]),
    ):
        assert [f["filename"] for f in extract_fenced_files(strip_edit_blocks(response))] == files
    # The hazard the strip exists for: unstripped, the edit fence reads as a file.
    assert "./backend/routes.py" in [f["filename"] for f in extract_fenced_files(_RESPONSE)]


class TestApplication:
    _BASE = {"backend/routes.py": _ROUTES, "backend/models.py": "class Run:\n    pass\n"}

    def _apply(self, response, *, writable=("backend/routes.py",), whole=()):
        from squadops.capabilities.anchored_edits import apply_anchored_edits

        return apply_anchored_edits(
            parse_anchored_edits(response),
            self._BASE,
            writable=writable,
            producer="development.correction_repair",
            task_id="t",
            whole_file_paths=whole,
        )

    def test_an_accepted_application_records_where_each_edit_landed(self):
        application = self._apply(_RESPONSE)

        record = application.record()
        assert record["accepted"] is True
        assert record["refusals"] == []
        assert [e["path"] for e in record["edits"]] == ["backend/routes.py", "backend/routes.py"]
        assert record["candidate_revision_id"] == application.outcome.candidate_revision_id

    @pytest.mark.parametrize(
        ("response", "writable", "whole", "line"),
        [
            (
                "```edit:backend/routes.py\n<<<<<<< SEARCH\n    return 1\n=======\n    return 2\n"
                ">>>>>>> REPLACE\n```\n",
                ("backend/routes.py",),
                (),
                "`backend/routes.py`: anchor_not_found — ",
            ),
            (
                "```edit:backend/models.py\n<<<<<<< SEARCH\n    pass\n=======\n    id: str\n"
                ">>>>>>> REPLACE\n```\n",
                ("backend/routes.py",),
                (),
                "`backend/models.py`: out_of_grant — ",
            ),
            (
                _RESPONSE,
                ("backend/routes.py",),
                ("backend/routes.py",),
                "`backend/routes.py`: edited and re-emitted whole",
            ),
            (
                "```edit:backend/routes.py\n<<<<<<< SEARCH\nx\n```\n",
                ("backend/routes.py",),
                (),
                "`backend/routes.py`: missing_divider — ",
            ),
        ],
        ids=["anchor not found", "outside the grant", "edited and re-emitted", "malformed"],
    )
    def test_a_refused_application_names_the_file_and_the_typed_reason(
        self, response, writable, whole, line
    ):
        """Bug caught: a retry told only that its edits failed — the model cannot correct an
        anchor it is not told was missing, in a file it is not told the name of."""
        application = self._apply(response, writable=writable, whole=whole)

        assert application.accepted is False
        assert any(r.startswith(line) for r in application.refusal_lines()), (
            application.refusal_lines()
        )
        assert application.record()["edits"] == []
