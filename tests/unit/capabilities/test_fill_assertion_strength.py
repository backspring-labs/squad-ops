"""What the fills assert, not just that slots were filled (#980).

Bug this guards: a `qa.test` retry can make a failing suite pass by retreating to weaker
assertions, and the record could not tell that from being right first time.

The pre-V7 shakedown (`cyc_308be9dfc299`) finished `accepted` with 14 of 14 criteria after
exactly that. Attempt 1 emitted 4,896 completion tokens of fills asserting response values
**and store effects**. Attempt 3 emitted 711 tokens asserting `body.id`, `body.title` and
`body.datetime`, touching the store nowhere. Both were recorded identically as "8 of 8 fills,
first attempt" — the record counted slots, never what the slots say. The dropped half is
exactly what catches a handler that does not persist.

This measures; it does not gate. An author may legitimately have nothing to say about the
store for some behaviour. What it makes impossible is a measurement window whose closing claim
describes assertion strength it never recorded.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.verification_scaffold_fill import (
    measure_assertion_strength,
    parse_fill_emission,
)

pytestmark = [pytest.mark.domain_capabilities]

#: The two real shapes from the shakedown, condensed.
_RICH = """```fill:slot-a
expect(body.id).toBeTruthy()
expect(all(TABLES.Run)).toHaveLength(1)
```
```fill:slot-b
expect(all(TABLES.Run)[0].title).toBe('sample')
```"""

_RETREAT = """```fill:slot-a
expect(body.id).toBeDefined()
```
```fill:slot-b
expect(body.title).toBe('sample')
```"""


def _measure(text: str) -> dict:
    return measure_assertion_strength(parse_fill_emission(text))


class TestTheRetreatIsVisible:
    def test_the_two_shakedown_attempts_are_distinguishable(self):
        """The whole point. Both filled every slot; only one asserted on state."""
        rich, retreat = _measure(_RICH), _measure(_RETREAT)
        assert rich["filled_slots"] == retreat["filled_slots"] == 2
        assert rich["any_fill_touches_the_store"] is True
        assert retreat["any_fill_touches_the_store"] is False

    def test_the_slots_that_assert_on_state_are_named(self):
        """A count would say "2 of 2 touch the store"; the names say WHICH, so a partial
        retreat — three rich fills and five response-only — is legible too."""
        assert _measure(_RICH)["store_slots"] == ["slot-a", "slot-b"]

    def test_a_partial_retreat_is_visible(self):
        mixed = _RICH.split("```fill:slot-b")[0] + _RETREAT.split("```fill:slot-a")[1]
        m = _measure(mixed)
        assert m["store_slots"] == ["slot-a"]
        assert m["any_fill_touches_the_store"] is True, "one rich fill is still some coverage"

    def test_body_size_corroborates(self):
        """The 7x drop between the real attempts was in data already logged and read by
        nobody. Cheap, and it moves with the thing that matters."""
        assert _measure(_RICH)["body_chars"] > _measure(_RETREAT)["body_chars"]


class TestWhatCountsAsTouchingTheStore:
    @pytest.mark.parametrize(
        "body",
        [
            "expect(all(TABLES.Run)).toHaveLength(1)",
            "expect(find(TABLES.Run, body.id)).toBeDefined()",
            "insert(TABLES.Run, { id: 'x' })",
            "expect(TABLES.Run).toBe('run')",
        ],
    )
    def test_each_store_symbol_registers(self, body):
        m = _measure(f"```fill:slot-a\n{body}\n```")
        assert m["any_fill_touches_the_store"], f"{body!r} asserts on the store"

    @pytest.mark.parametrize(
        "body",
        [
            "expect(body.id).toBeTruthy()",
            "expect(body.participants).toEqual([])",
            # the words appear but not as a call or member access — prose, not a read
            "// we could check all of the store here later",
        ],
    )
    def test_response_only_fills_do_not_register(self, body):
        m = _measure(f"```fill:slot-a\n{body}\n```")
        assert not m["any_fill_touches_the_store"], f"{body!r} does not assert on the store"


class TestEdges:
    def test_a_not_applicable_slot_is_counted_separately_not_as_weak(self):
        """An explicit NA is a declared judgment, not a retreat, and conflating the two would
        punish the honest disposition the protocol asks for."""
        m = _measure("```fill:slot-a\nnot_applicable: no store effect for a read\n```")
        assert m["filled_slots"] == 0
        assert m["not_applicable_slots"] == 1
        assert m["any_fill_touches_the_store"] is False

    def test_an_empty_emission_measures_zero_rather_than_raising(self):
        m = _measure("no fences here at all")
        assert m == {
            "filled_slots": 0,
            "not_applicable_slots": 0,
            "body_chars": 0,
            "store_slots": [],
            "store_symbols_used": [],
            "any_fill_touches_the_store": False,
        }
