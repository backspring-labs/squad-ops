"""SIP-0107 §38 step 5, first half — structural revision of Python source.

Each test names what it catches: an entity located by anything but the parser, a selector
that silently picks between two definitions, an insertion landing inside the replacement it
precedes, a candidate that no longer parses reaching verification, a byte outside the accepted
ranges changing, or scaffold-owned bytes needing restoration after a scoped revision.
"""

from __future__ import annotations

import pytest

from squadops.cycles.revision_transaction import (
    RefusalReason,
    Revision,
    RevisionOperation,
    RevisionTransaction,
    base_revision_id,
    preservation_proof,
    resolve_and_apply,
)
from squadops.cycles.structural_python import (
    python_entities,
    python_syntax_error,
    resolve_python_entity,
)
from squadops.cycles.write_authorization import WriteGrant

pytestmark = [pytest.mark.domain_orchestration]

_ROUTES = "backend/routes.py"
_SOURCE = (
    '"""Routes."""\n'
    "from fastapi import APIRouter\n"
    "from .models import Run\n"
    "\n"
    "router = APIRouter()\n"
    "\n"
    "\n"
    '@router.post("/runs", status_code=201)\n'
    "def create_run(payload):\n"
    '    """create run."""\n'
    "    run = Run(**payload.dict())  # keep this comment\n"
    "    return run\n"
    "\n"
    "\n"
    "class Store:\n"
    "    def add(self, x):\n"
    "        self.x = x\n"
    "\n"
    "    def one(self): return 1\n"
)


def _text(selector: str, source: str = _SOURCE) -> str:
    (span,) = resolve_python_entity(_ROUTES, source, selector)
    return source[span[0] : span[1]]


class TestAddressing:
    @pytest.mark.parametrize(
        ("selector", "expected"),
        [
            ("imports", "from fastapi import APIRouter\nfrom .models import Run\n"),
            ("import:.models", "from .models import Run\n"),
            (
                "function:create_run",
                '@router.post("/runs", status_code=201)\ndef create_run(payload):\n'
                '    """create run."""\n    run = Run(**payload.dict())  # keep this comment\n'
                "    return run\n",
            ),
            (
                "function:create_run#body",
                '    """create run."""\n    run = Run(**payload.dict())  # keep this comment\n'
                "    return run\n",
            ),
            ("method:Store.add#body", "        self.x = x\n"),
            ("method:Store.one", "    def one(self): return 1\n"),
        ],
    )
    def test_a_selector_names_the_whole_lines_of_its_entity(self, selector, expected):
        """Bug caught: a range that drops the decorator, splits a line or loses the trailing
        newline — a replacement would then corrupt the lines around it."""
        assert _text(selector) == expected

    def test_what_the_parser_cannot_address_resolves_to_nothing(self):
        """Fail-closed (§43.2): an inline body has no own lines; an unparseable file has no
        entities; a redefinition names two, which the transaction must refuse to pick."""
        assert resolve_python_entity(_ROUTES, _SOURCE, "method:Store.one#body") == []
        assert resolve_python_entity(_ROUTES, "def f(:\n", "function:f") is None
        redefined = "def f():\n    return 1\n\n\ndef f():\n    return 2\n"
        assert len(resolve_python_entity(_ROUTES, redefined, "function:f")) == 2
        assert python_entities("def f(:\n") is None


def _apply(*revisions: Revision, base=None, validate=True, resolver=resolve_python_entity):
    base = base or {_ROUTES: _SOURCE, "frontend/App.jsx": "export default 1\n"}
    return resolve_and_apply(
        base,
        RevisionTransaction(
            base_revision_id=base_revision_id(base),
            grant=WriteGrant(
                producer="development.correction_repair",
                stage="structural_repair",
                writable=frozenset(base),
            ),
            task_id="t",
            revisions=revisions,
        ),
        lambda _p, _c, _r: None,
        resolve_entity=resolver,
        validate_syntax=python_syntax_error if validate else None,
    )


def _rev(op: RevisionOperation, entity: str, replacement: str = "") -> Revision:
    return Revision(artifact_path=_ROUTES, operation=op, entity=entity, replacement=replacement)


class TestStructuralTransaction:
    def test_a_body_replacement_changes_only_the_body_and_proves_it(self):
        """§10, §17. Bug caught: the decorator, the signature, the comment on a sibling line
        or anything past the function touched by a body-only repair."""
        new_body = "    return Run(**payload.dict(exclude_none=True))\n"

        outcome = _apply(
            _rev(RevisionOperation.REPLACE_ENTITY, "function:create_run#body", new_body)
        )

        assert outcome.accepted
        assert outcome.changed_files()[_ROUTES] == _SOURCE.replace(
            _text("function:create_run#body"), new_body
        )
        assert outcome.preservation.holds

    def test_the_import_order_repair_is_a_remove_and_an_insert_in_one_transaction(self):
        """§8.4: no ``move`` — the pair, both resolved against the same base (§13)."""
        outcome = _apply(
            _rev(RevisionOperation.REMOVE_ENTITY, "import:.models", "ignored text"),
            _rev(
                RevisionOperation.INSERT_BEFORE_ENTITY,
                "import:fastapi",
                "from .models import Run\n",
            ),
        )

        assert outcome.accepted
        assert outcome.changed_files()[_ROUTES].startswith(
            '"""Routes."""\nfrom .models import Run\nfrom fastapi import APIRouter\n\nrouter'
        )
        assert outcome.preservation.holds

    def test_an_insertion_before_an_entity_lands_ahead_of_that_entitys_replacement(self):
        """Bug caught: equal-offset edits applied in the wrong order — the insertion spliced
        inside, or overwritten by, the replacement it precedes."""
        outcome = _apply(
            _rev(RevisionOperation.INSERT_BEFORE_ENTITY, "method:Store.add", "    x = 0\n\n"),
            _rev(
                RevisionOperation.REPLACE_ENTITY,
                "method:Store.add",
                "    def add(self, x):\n        self.x = x + 1\n",
            ),
            _rev(
                RevisionOperation.INSERT_AFTER_ENTITY,
                "method:Store.add",
                "\n    def two(self):\n        return 2\n",
            ),
        )

        assert outcome.accepted
        assert (
            "class Store:\n    x = 0\n\n    def add(self, x):\n        self.x = x + 1\n"
            "\n    def two(self):\n        return 2\n\n    def one(self): return 1\n"
        ) in outcome.changed_files()[_ROUTES]
        assert outcome.preservation.holds

    @pytest.mark.parametrize(
        ("revisions", "base", "resolver", "reason"),
        [
            (
                (_rev(RevisionOperation.REPLACE_ENTITY, "function:delete_run", "x = 1\n"),),
                None,
                resolve_python_entity,
                RefusalReason.UNRESOLVED_ENTITY,
            ),
            (
                (_rev(RevisionOperation.REMOVE_ENTITY, "function:f"),),
                {_ROUTES: "def f():\n    return 1\n\n\ndef f():\n    return 2\n"},
                resolve_python_entity,
                RefusalReason.AMBIGUOUS_ENTITY,
            ),
            (
                (_rev(RevisionOperation.REMOVE_ENTITY, "function:f"),),
                {_ROUTES: "def f(:\n"},
                resolve_python_entity,
                RefusalReason.UNREADABLE_STRUCTURE,
            ),
            (
                (_rev(RevisionOperation.REMOVE_ENTITY, "function:create_run"),),
                None,
                None,
                RefusalReason.UNREADABLE_STRUCTURE,
            ),
            (
                (
                    _rev(RevisionOperation.INSERT_AFTER_ENTITY, "import:fastapi", "import os\n"),
                    _rev(RevisionOperation.INSERT_BEFORE_ENTITY, "import:.models", "import re\n"),
                ),
                None,
                resolve_python_entity,
                RefusalReason.OVERLAPPING_RANGES,
            ),
            (
                (
                    _rev(
                        RevisionOperation.REPLACE_ENTITY,
                        "function:create_run#body",
                        "    return (\n",
                    ),
                ),
                None,
                resolve_python_entity,
                RefusalReason.INVALID_SYNTAX,
            ),
        ],
        ids=[
            "absent",
            "redefined",
            "unparseable base",
            "no resolver",
            "same insertion point",
            "invalid candidate",
        ],
    )
    def test_every_unresolvable_or_invalid_revision_refuses_the_transaction(
        self, revisions, base, resolver, reason
    ):
        """§14, §18, §21. Bug caught: a guessed entity, an arbitrary order between two
        insertions at one point, or a candidate that does not parse handed to verification."""
        outcome = _apply(*revisions, base=base, resolver=resolver)

        assert not outcome.accepted
        assert outcome.candidate_files == {}
        assert [r.reason for r in outcome.refusals] == [reason]


class TestPreservationProof:
    @pytest.mark.parametrize(
        "tamper",
        [
            lambda c: {**c, _ROUTES: c[_ROUTES].replace("APIRouter()", "APIRouter(prefix='/api')")},
            lambda c: {**c, "frontend/App.jsx": "export default 2\n"},
            lambda c: {**c, _ROUTES: _SOURCE},
            lambda c: {**c, _ROUTES: c[_ROUTES] + "\n"},
        ],
        ids=[
            "an untouched line changed",
            "an unrecorded file changed",
            "the edit missing",
            "a trailing byte",
        ],
    )
    def test_a_candidate_that_is_not_the_base_plus_the_recorded_edits_breaks_the_proof(
        self, tamper
    ):
        """§17, §39.2. Bug caught: a candidate produced elsewhere — agent-side, or after a
        formatter — carrying a change no recorded edit explains, accepted because a positional
        comparison happened to line up."""
        outcome = _apply(
            _rev(RevisionOperation.REPLACE_ENTITY, "function:create_run#body", "    return None\n")
        )
        base = {_ROUTES: _SOURCE, "frontend/App.jsx": "export default 1\n"}

        assert preservation_proof(base, outcome.edits, outcome.candidate_files).holds
        assert not preservation_proof(base, outcome.edits, tamper(outcome.candidate_files)).holds


class TestOnAScaffoldedArtifact:
    def test_a_scoped_revision_of_a_fill_slot_needs_no_restoration_and_observes_nothing(self):
        """§39.3, on the real FastAPI+React scaffold's ``backend/routes.py``. Bug caught: a
        body repair that disturbs the scaffold-owned decorator, path, status code or signature —
        the drift ``fill_slot_integrity`` restores or reports after a whole-file rewrite."""
        from squadops.capabilities.scaffold import expand
        from squadops.cycles.fill_slot_integrity import (
            declared_route_signatures,
            restore_declared_status_codes,
            signature_divergences,
        )
        from tests.unit.capabilities._stack_fixtures import manifest_for_stack

        files = {
            f["name"]: f["content"] for f in expand(manifest_for_stack("fullstack_fastapi_react"))
        }
        seed = files[_ROUTES]
        body = "    run = run_event_store.create(payload)\n    return run\n"

        outcome = _apply(
            _rev(RevisionOperation.REPLACE_ENTITY, "function:post_runs#body", body),
            base={_ROUTES: seed},
        )

        candidate = outcome.changed_files()[_ROUTES]
        assert outcome.accepted and outcome.preservation.holds
        corrected, divergences = restore_declared_status_codes(seed, candidate)
        assert (corrected, divergences) == (candidate, [])
        assert signature_divergences(declared_route_signatures(seed), candidate) == []
