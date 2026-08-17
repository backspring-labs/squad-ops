"""The store's table names are derived and typed (#967).

Bug this guards: the store took a free `string`, so the application named its table one
thing and its test suite named another. The disagreement surfaced as an empty array at
assertion time — indistinguishable from a handler that never persisted. SIP-0104 window
roll 6 spent three correction rounds and its whole budget on it, all three failure analyses
blamed the application, and the application worked: it installed, built, booted and answered
all five contract probes over real HTTP.

The fix removes the choice rather than documenting it. A name the two sides disagree about
is a TypeScript error, and `next build` runs tsc with errors fatal, so it fails before the
suite runs. Proven against real tsc in the sandbox image, not only asserted here:

    probe_wrong.ts(2,22): error TS2345: Argument of type '"run_store"' is not
    assignable to parameter of type 'Table'.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.stack_nextjs_ts import (
    _harness_test_source,
    _store_source,
    _table_name,
)

pytestmark = [pytest.mark.domain_capabilities]


class _Field:
    def __init__(self, name):
        self.name, self.type, self.required = name, "str", True


class _Entity:
    def __init__(self, name):
        self.name, self.fields = name, (_Field("id"),)


class _Manifest:
    def __init__(self, *names):
        self.entities = tuple(_Entity(n) for n in names)


@pytest.mark.parametrize(
    "entity,table",
    [
        ("RunEvent", "run_event"),
        ("Run", "run"),
        ("Participant", "participant"),
        ("HTTPRequest", "h_t_t_p_request"),  # documents the edge rather than pretending
    ],
)
def test_the_derivation_is_pinned(entity, table):
    """Pinned because both authoring briefs render these values and `TABLES` exports them —
    a silent change to the rule would rename every app's tables at once."""
    assert _table_name(entity) == table


class TestTheUnionIsWhatEnforces:
    def test_every_entity_becomes_a_member(self):
        src = _store_source(_Manifest("Run", "Participant"))
        assert "Run: 'run'," in src
        assert "Participant: 'participant'," in src

    def test_the_accessors_take_the_union_not_a_string(self):
        """The whole mechanism. `table: string` accepts roll 6's wrong name silently."""
        src = _store_source(_Manifest("Run"))
        for fn in ("all(table: Table)", "insert(table: Table,", "find(table: Table,"):
            assert fn in src
        assert "table: string" not in src

    def test_the_type_is_derived_from_the_constant_not_restated(self):
        """`Table` restated as a literal union beside `TABLES` is two places to edit, and the
        next author updates one. Deriving it makes them incapable of disagreeing."""
        src = _store_source(_Manifest("Run"))
        assert "export type Table = (typeof TABLES)[keyof typeof TABLES]" in src

    def test_the_backing_record_is_keyed_by_the_union(self):
        assert "Partial<Record<Table, Record<string, unknown>[]>>" in _store_source(
            _Manifest("Run")
        )


class TestTheHarnessDoesNotNeedAnEscapeHatch:
    def test_it_addresses_a_real_table_through_the_constant(self):
        """It used `'__probe'`. Reserving a union member for it was the tempting fix and is
        the untyped escape hatch this change removes — a reserved name is still a legal
        string the application could pick."""
        src = _harness_test_source(_Manifest("Run", "Participant"))
        assert "TABLES.Run" in src
        assert "__probe" not in src

    def test_it_imports_the_constant_it_uses(self):
        assert "import { reset, insert, all, TABLES } from '@/lib/store'" in _harness_test_source(
            _Manifest("Run")
        )


class TestTheNoEntityCase:
    def test_a_manifest_with_no_entities_keeps_an_open_signature(self):
        """`never` would make the store unusable rather than safe, and with no entities there
        is nothing for two authors to disagree about."""
        src = _store_source(_Manifest())
        assert "export type Table = string" in src
        assert "TABLES" not in src

    def test_the_harness_falls_back_with_it(self):
        """Emitting `TABLES.<something>` against a store that exports no TABLES would not
        compile — the two fallbacks have to move together."""
        src = _harness_test_source(_Manifest())
        assert "TABLES" not in src
        assert "__probe" in src


def test_the_reason_is_recorded_where_an_author_reads_it():
    """The comment is the only place a reader of the emitted app learns why the type exists.
    Without it the next contributor relaxes it back to `string` to make something compile."""
    src = _store_source(_Manifest("Run"))
    assert "#967" in src
    assert "COMPILE error" in src
