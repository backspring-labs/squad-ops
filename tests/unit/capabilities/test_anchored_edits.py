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


# --- SIP-0107 step 5: structural blocks ------------------------------------------------------


class TestStructuralBlocks:
    _ROUTES_PY = (
        "import os\n"
        "from fastapi import APIRouter\n"
        "\n"
        "router = APIRouter()\n"
        "\n"
        '@router.post("/runs", status_code=201)\n'
        "def post_runs(payload):\n"
        '    raise NotImplementedError("scaffold")\n'
    )

    def _apply(self, response, base):
        from squadops.capabilities.anchored_edits import apply_anchored_edits

        return apply_anchored_edits(
            parse_anchored_edits(response),
            base,
            writable=list(base),
            producer="development.correction_repair",
            task_id="t",
        )

    def test_structural_and_anchored_blocks_apply_in_one_transaction(self):
        """Bug caught: the structural blocks parsed into edits the transaction never resolves,
        or one kind applied while the other was dropped."""
        from squadops.capabilities.anchored_edits import StructuralEdit
        from squadops.cycles.revision_transaction import RevisionOperation

        response = (
            "```edit:backend/routes.py\n"
            "<<<<<<< REMOVE import:os\n"
            ">>>>>>> END\n"
            "<<<<<<< REPLACE function:post_runs#body\n"
            "    return {'id': 1, **payload}\n"
            ">>>>>>> END\n"
            "<<<<<<< SEARCH\n"
            "router = APIRouter()\n"
            "=======\n"
            "router = APIRouter()  # no prefix\n"
            ">>>>>>> REPLACE\n"
            "```\n"
        )
        parse = parse_anchored_edits(response)

        assert parse.malformed == ()
        assert parse.edits[0] == StructuralEdit(
            "backend/routes.py", RevisionOperation.REMOVE_ENTITY, "import:os", ""
        )
        application = self._apply(response, {"backend/routes.py": self._ROUTES_PY})
        assert application.accepted, application.refusal_lines()
        assert application.outcome.changed_files()["backend/routes.py"] == (
            "from fastapi import APIRouter\n"
            "\n"
            "router = APIRouter()  # no prefix\n"
            "\n"
            '@router.post("/runs", status_code=201)\n'
            "def post_runs(payload):\n"
            "    return {'id': 1, **payload}\n"
        )
        assert [e["operation"] for e in application.record()["edits"]] == [
            "remove_entity",
            "replace_entity",
            "replace_anchor",
        ]

    def test_insert_before_and_after_land_on_their_side_of_the_entity(self):
        """Bug caught: the two insertion verbs mapped to each other's operation — every inserted
        import or function would land on the wrong side of the entity the model named."""
        response = (
            "```edit:backend/routes.py\n"
            "<<<<<<< INSERT BEFORE import:fastapi\n"
            "import re\n"
            ">>>>>>> END\n"
            "<<<<<<< INSERT AFTER import:fastapi\n"
            "import json\n"
            ">>>>>>> END\n"
            "```\n"
        )

        application = self._apply(response, {"backend/routes.py": self._ROUTES_PY})

        assert application.accepted, application.refusal_lines()
        assert application.outcome.changed_files()["backend/routes.py"].startswith(
            "import os\nimport re\nfrom fastapi import APIRouter\nimport json\n\nrouter"
        )

    @pytest.mark.parametrize(
        ("block", "reason"),
        [
            ("<<<<<<< MOVE import:os\n>>>>>>> END\n", "unknown_block"),
            ("<<<<<<< REPLACE\nx = 1\n>>>>>>> END\n", "unknown_block"),
            ("<<<<<<< REPLACE function:f\nx = 1\n```\n", "missing_end_marker"),
            ("<<<<<<< REMOVE import:os\nimport os\n>>>>>>> END\n", "remove_with_content"),
            ("<<<<<<< INSERT AFTER import:os\n\n>>>>>>> END\n", "empty_insert"),
        ],
        ids=["no move", "no selector", "no end", "remove with lines", "empty insert"],
    )
    def test_a_malformed_structural_block_is_named(self, block, reason):
        parse = parse_anchored_edits(f"```edit:backend/routes.py\n{block}```\n")

        assert [m.reason for m in parse.malformed] == [reason]
        assert parse.edits == ()

    def test_a_react_component_body_is_replaced_on_the_real_scaffold_view(self):
        """The JSX resolver through the grammar and the transaction, on the file 1.7.5 React
        roll 3 re-emitted whole. Bug caught: the component's export, signature or the lines
        around its body changed by a body replacement."""
        from squadops.capabilities.scaffold import expand
        from tests.unit.capabilities._stack_fixtures import manifest_for_stack

        view = "frontend/src/views/RunsListView.jsx"
        files = {
            f["name"]: f["content"] for f in expand(manifest_for_stack("fullstack_fastapi_react"))
        }
        body = '  return <ul data-testid="runs-list">{runs?.length ?? 0}</ul>\n'
        response = (
            f"```edit:{view}\n<<<<<<< REPLACE function:RunsListView#body\n{body}>>>>>>> END\n```\n"
        )

        application = self._apply(response, {view: files[view]})

        assert application.accepted, application.refusal_lines()
        candidate = application.outcome.changed_files()[view]
        assert "export default function RunsListView() {\n" + body + "}\n" in candidate
        assert application.outcome.preservation.holds

    @pytest.mark.parametrize(
        ("base_body", "block", "accepted"),
        [
            (
                "    return 1\n",
                "<<<<<<< REPLACE function:g#body\n    return (\n>>>>>>> END\n",
                False,
            ),
            (
                "    return (\n",
                "<<<<<<< SEARCH\n    return 2\n=======\n    return (3\n>>>>>>> REPLACE\n",
                True,
            ),
        ],
        ids=["base parses: a breaking edit is refused", "base already broken: judged later"],
    )
    def test_a_candidate_that_stops_parsing_is_refused_unless_the_base_never_parsed(
        self, base_body, block, accepted
    ):
        """§18 for a repair. Bug caught: an edit that breaks a parsing file handed to
        verification — or a repair of an already-broken file (anchored: an unparseable file
        has no structural reading) refused for still being broken, when the syntax error may be
        the failure it was sent to fix."""
        base = {"backend/util.py": f"def f():\n{base_body}\n\ndef g():\n    return 2\n"}

        application = self._apply(f"```edit:backend/util.py\n{block}```\n", base)

        assert application.accepted is accepted, application.refusal_lines()
        if not accepted:
            assert any("invalid_syntax" in line for line in application.refusal_lines())


@pytest.mark.parametrize(
    ("path", "content", "selectors"),
    [
        (
            "backend/a.py",
            "import os\n\ndef f():\n    return 1\n",
            ("imports", "import:os", "function:f", "function:f#body"),
        ),
        (
            "frontend/a.jsx",
            "export const A = () => {\n  return 1\n}\n",
            ("const:A", "const:A#body"),
        ),
        ("app/page.tsx", "export default function P() {}\n", ("function:P",)),
        ("README.md", "# hi\n", None),
        ("backend/b.py", "def f(:\n", None),
    ],
    ids=["python", "jsx", "tsx", "no grammar", "unparseable"],
)
def test_the_dispatcher_routes_each_file_to_its_resolver(path, content, selectors):
    """Bug caught: a file routed to no grammar or the wrong one, or the prompt listing entities the
    transaction's resolver would not find."""
    from squadops.cycles.structural_resolution import entity_selectors, resolve_entity

    assert entity_selectors(path, content) == selectors
    if selectors:
        assert resolve_entity(path, content, selectors[-1])
    else:
        assert resolve_entity(path, content, "function:f") is None


@pytest.mark.parametrize(
    ("outputs", "form", "whole", "new"),
    [
        ({"artifacts": [{"name": "a.py", "type": "source"}]}, "whole_file", ["a.py"], []),
        (
            {
                "anchored_edits": {"accepted": True, "edits": [{"path": "a.py"}], "refusals": []},
                "artifacts": [
                    {"name": "a.py", "type": "source"},
                    {"name": "b.py", "type": "source"},
                ],
            },
            "edits_and_whole_file",
            ["b.py"],
            [],
        ),
        ({"artifacts": [{"name": "slot-x", "type": "fill"}]}, "fill", [], []),
        ({"artifacts": [{"name": "c.py", "type": "source"}]}, "new_files_only", [], ["c.py"]),
        ({"artifacts": [{"name": "prose.md", "emission_fallback": True}]}, "none", [], []),
    ],
    ids=["whole file", "edit one, rewrite another", "fill", "a new file", "prose fallback"],
)
def test_the_revision_form_separates_a_whole_file_fallback_from_what_is_not_one(
    outputs, form, whole, new
):
    """SIP-0107 §46a counts unauthorized whole-file fallbacks per cell. Bug caught: a file the
    repair CREATES counted as a fallback, an edited file counted as re-emitted because its
    applied content rides as an artifact, or a prose fallback counted as a file."""
    from squadops.capabilities.anchored_edits import revision_form_reading

    reading = revision_form_reading({"a.py": 2, "b.py": 1}, outputs)

    assert (reading["form"], reading["whole_file_offered"], reading["new_files"]) == (
        form,
        whole,
        new,
    )
