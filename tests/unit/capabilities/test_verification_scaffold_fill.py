"""The Gate 3 corpus — fill-merge round-trip determinism, containment, the negative set.

Runs against the real reference emission, so every containment claim is proven on the
bytes a run would actually carry. The exit criteria this file owns (plan P3): merge
round-trip determinism; garbage fill degrades one slot while every other file is
byte-untouched; oversized/duplicate/misaddressed fills rejected; slot containment proven
(the merged spine equals the scaffold's, verified on every merge).
"""

from __future__ import annotations

import pytest

from squadops.capabilities.verification_scaffold import ScaffoldValidationError
from squadops.capabilities.verification_scaffold_emission import emit_verification_scaffold
from squadops.capabilities.verification_scaffold_fill import (
    DISPOSITION_FILLED,
    DISPOSITION_MISSING,
    DISPOSITION_NOT_APPLICABLE,
    DISPOSITION_REJECTED,
    MAX_FILL_LINES,
    Fill,
    fill_findings,
    merge_fills,
    parse_fill_emission,
    strip_fill_blocks,
)
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

_CREATE_SLOT = "slot-vc-probe-api-runs"
_LIST_SLOT = "slot-vs-get-api-runs"


@pytest.fixture(scope="module")
def emission():
    return emit_verification_scaffold(manifest_for_stack("nextjs_ts"))


def _merge(emission, text: str):
    return merge_fills(list(emission.files), emission.manifest, parse_fill_emission(text))


class TestParseFillEmission:
    def test_fill_blocks_parse_with_bodies_verbatim(self):
        text = (
            "Here are my fills.\n\n"
            "```fill:slot-vc-probe-api-runs\n"
            "    expect(body.id).toBeTruthy()\n"
            "    expect(all('runs')).toHaveLength(1)\n"
            "```\n\n"
            "```fill:slot-vs-get-api-runs\n"
            "not_applicable: the declared status fully covers an empty listing\n"
            "```\n\n"
            "```typescript:__tests__/extra.test.ts\n"
            "// an additive file — NOT this protocol's business\n"
            "```\n"
        )
        parsed = parse_fill_emission(text)
        assert len(parsed.fills) == 2
        fill = parsed.fills[0]
        assert fill.slot_id == _CREATE_SLOT
        assert (
            fill.body == "    expect(body.id).toBeTruthy()\n    expect(all('runs')).toHaveLength(1)"
        )
        na = parsed.fills[1]
        assert na.is_not_applicable
        assert na.not_applicable_reason == "the declared status fully covers an empty listing"
        assert parsed.duplicates == ()

    def test_duplicate_slot_fills_are_flagged(self):
        text = (
            "```fill:slot-vc-probe-api-runs\nexpect(1).toBe(1)\n```\n"
            "```fill:slot-vc-probe-api-runs\nexpect(2).toBe(2)\n```\n"
        )
        assert parse_fill_emission(text).duplicates == (_CREATE_SLOT,)

    def test_an_emission_with_no_fill_blocks_parses_empty(self):
        parsed = parse_fill_emission("no fences at all, just prose")
        assert parsed.fills == () and parsed.duplicates == ()

    def test_a_language_prefixed_fence_is_a_fill_and_is_recorded_as_drift(self):
        """#987: ```typescript:fill:slot-… is the form an author actually writes.

        Under the exact-form pattern it matched nothing here, survived
        ``strip_fill_blocks``, and the file extractor read it as a file named
        ``fill:slot-…``. A pre-V7 shakedown lost all six of its fills that way with
        no finding raised — the emission looked like it had simply said nothing.
        """
        text = (
            "```typescript:fill:slot-vc-probe-api-runs\n"
            "    expect(body.id).toBeTruthy()\n"
            "```\n"
            "```fill:slot-vs-get-api-runs\n"
            "    expect(body).toEqual([])\n"
            "```\n"
        )
        parsed = parse_fill_emission(text)

        assert [f.slot_id for f in parsed.fills] == [_CREATE_SLOT, _LIST_SLOT]
        assert parsed.fills[0].body == "    expect(body.id).toBeTruthy()"
        # Accepted, but not silently: the unprefixed sibling is absent from the record.
        assert parsed.language_prefixed == (_CREATE_SLOT,)

    def test_a_prefixed_fence_cannot_leak_into_the_file_extractor(self):
        """The other half of #987 — stripping must remove the prefixed form too, or
        the same block is both a fill and a bogus additive file named ``fill:slot-…``."""
        text = (
            "```typescript:fill:slot-vc-probe-api-runs\n"
            "    expect(body.id).toBeTruthy()\n"
            "```\n"
            "```typescript:__tests__/extra.test.ts\n"
            "// a genuine additive file\n"
            "```\n"
        )
        stripped = strip_fill_blocks(text)

        assert "fill:slot-" not in stripped
        assert "__tests__/extra.test.ts" in stripped

    def test_a_prefix_that_is_not_a_language_token_is_not_a_fill(self):
        """The prefix is optional, not arbitrary: a fence whose info string merely
        ends in ``fill:slot-…`` is a path-addressed file and stays the extractor's."""
        text = "```ts:src/fill:slot-vc-probe-api-runs\nconst x = 1\n```\n"
        assert parse_fill_emission(text).fills == ()
        assert strip_fill_blocks(text) == text


class TestFillFindings:
    @pytest.mark.parametrize(
        ("body", "fragment"),
        [
            ("// [scaffold-slot:end slot-x]\nexpect(1).toBe(1)", "marker vocabulary"),
            ("import { x } from 'y'\nexpect(1).toBe(1)", "import"),
            ("const m = require('supertest')", "require()"),
            ("const r = await fetch('http://localhost:3000/api/runs')", "fetch()"),
            ("const x = new XMLHttpRequest()", "XMLHttpRequest"),
            ("const w = new WebSocket('ws://x')", "WebSocket"),
            ("\n".join("expect(1).toBe(1)" for _ in range(MAX_FILL_LINES + 1)), "oversized"),
            ("expect('" + "x" * 9000 + "').toBeTruthy()", "oversized"),
            ("", "empty fill body"),
            ("   \n  ", "empty fill body"),
        ],
    )
    def test_each_containment_rule_fires(self, body, fragment):
        findings = fill_findings(Fill(slot_id=_CREATE_SLOT, body=body))
        assert any(fragment in f for f in findings), findings

    def test_a_clean_fill_and_an_na_have_no_findings(self):
        assert fill_findings(Fill(slot_id=_CREATE_SLOT, body="expect(body.id).toBeTruthy()")) == []
        assert fill_findings(Fill(slot_id=_CREATE_SLOT, not_applicable_reason="covered")) == []


class TestMerge:
    def test_round_trip_determinism(self, emission):
        text = "```fill:slot-vc-probe-api-runs\n    expect(body.id).toBeTruthy()\n```\n"
        first = _merge(emission, text)
        second = _merge(emission, text)
        assert [(f.path, f.content) for f in first.files] == [
            (f.path, f.content) for f in second.files
        ]

    def test_a_valid_fill_replaces_the_seed_body_and_preserves_the_spine(self, emission):
        merged = _merge(
            emission, "```fill:slot-vc-probe-api-runs\n    expect(body.id).toBeTruthy()\n```\n"
        )
        record = {f.path: f for f in emission.manifest.files}
        by_path = {f.path: f for f in merged.files}
        target = "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"
        assert "    expect(body.id).toBeTruthy()" in by_path[target].content
        assert "void body" not in by_path[target].content  # the seed body is gone
        for path, merged_file in by_path.items():
            assert merged_file.spine_hash == record[path].spine_hash

    def test_every_declared_slot_gets_exactly_one_disposition(self, emission):
        merged = _merge(emission, "")
        assert sorted(d.slot_id for d in merged.dispositions) == sorted(
            emission.manifest.slot_ids()
        )

    def test_a_missing_fill_is_a_failing_state_never_silent(self, emission):
        """The plan's missing-slot rule, and its classification shape: the injected line
        is an expect().toBe mismatch, so the execution gate reads it as an assertion
        failure (fill layer), never a mechanical crash (generator)."""
        merged = _merge(emission, "")
        assert merged.disposition_counts() == {DISPOSITION_MISSING: len(emission.files)}
        target = next(f for f in merged.files if _CREATE_SLOT in f.content)
        assert "no fill and no disposition" in target.content
        assert f"expect('fill layer: {_CREATE_SLOT}:" in target.content

    def test_not_applicable_is_recorded_with_its_reason(self, emission):
        merged = _merge(
            emission,
            "```fill:slot-vs-get-api-runs\nnot_applicable: status covers an empty list\n```\n",
        )
        disposition = merged.by_slot()[_LIST_SLOT]
        assert disposition.disposition == DISPOSITION_NOT_APPLICABLE
        assert disposition.detail == "status covers an empty list"
        listing = next(f for f in merged.files if "vs-get-api-runs.scaffold" in f.path)
        assert "// not_applicable (qa): status covers an empty list" in listing.content

    def test_a_rejected_fill_degrades_its_slot_with_the_finding_named(self, emission):
        merged = _merge(
            emission,
            "```fill:slot-vc-probe-api-runs\nconst r = await fetch('http://x')\n```\n",
        )
        disposition = merged.by_slot()[_CREATE_SLOT]
        assert disposition.disposition == DISPOSITION_REJECTED
        assert "fetch()" in disposition.detail
        target = next(f for f in merged.files if "vc-probe-api-runs.scaffold" in f.path)
        assert "fill rejected" in target.content
        assert "fetch('http://x')" not in target.content  # the violating body never merges

    def test_duplicate_fills_reject_the_slot_not_a_winner(self, emission):
        merged = _merge(
            emission,
            "```fill:slot-vc-probe-api-runs\nexpect(1).toBe(1)\n```\n"
            "```fill:slot-vc-probe-api-runs\nexpect(2).toBe(2)\n```\n",
        )
        disposition = merged.by_slot()[_CREATE_SLOT]
        assert disposition.disposition == DISPOSITION_REJECTED
        assert "more than once" in disposition.detail
        target = next(f for f in merged.files if "vc-probe-api-runs.scaffold" in f.path)
        assert "expect(1).toBe(1)" not in target.content
        assert "expect(2).toBe(2)" not in target.content

    def test_a_misaddressed_fill_is_recorded_not_silently_dropped(self, emission):
        merged = _merge(emission, "```fill:slot-nonexistent-behavior\nexpect(1).toBe(1)\n```\n")
        assert [m.slot_id for m in merged.misaddressed] == ["slot-nonexistent-behavior"]
        assert all("expect(1).toBe(1)" not in f.content for f in merged.files)

    def test_garbage_fill_degrades_one_file_and_leaves_every_other_byte_identical(self, emission):
        """Gate 3's blast-radius claim: containment-clean garbage (broken TS) merges into
        its own slot's file; every other file is byte-identical to the no-fill merge, so
        the rest of the suite still collects (one behavior per file, P1)."""
        garbage = "```fill:slot-vc-probe-api-runs\n))) this is not TypeScript {{{\n```\n"
        merged = _merge(emission, garbage)
        baseline = _merge(emission, "")
        assert merged.by_slot()[_CREATE_SLOT].disposition == DISPOSITION_FILLED
        changed = [
            f.path
            for f, b in zip(merged.files, baseline.files, strict=True)
            if f.content != b.content
        ]
        assert changed == ["__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"]

    def test_merge_refuses_if_its_own_output_moves_the_spine(self, emission):
        """The containment guard itself: a record whose spine hash cannot be reproduced
        must refuse, not ship (a defect in the merge is still a defect)."""
        import dataclasses

        tampered_files = tuple(
            dataclasses.replace(f, spine_hash="0" * 64) for f in emission.manifest.files
        )
        tampered = dataclasses.replace(emission.manifest, files=tampered_files)
        with pytest.raises(ScaffoldValidationError, match="merge moved the spine"):
            merge_fills(list(emission.files), tampered, parse_fill_emission(""))


class TestPhantomTableFindings:
    """#1087: a fill asserting on a table the frozen store does not export is rejected at
    the fill gate with the real tables named — not discovered at retest as an empty
    array that reads like a handler that never saved."""

    def test_a_phantom_table_reference_is_rejected_and_the_real_tables_are_named(self):
        findings = fill_findings(
            Fill(slot_id=_CREATE_SLOT, body="expect(all(TABLES.Participant)).toHaveLength(1)"),
            store_tables=["RunEvent"],
        )
        assert len(findings) == 1
        assert "`TABLES.Participant`" in findings[0]
        assert "`TABLES.RunEvent`" in findings[0]
        assert "#1087" in findings[0]

    def test_an_exported_table_passes_and_the_rule_is_off_without_a_table_set(self):
        body = "expect(all(TABLES.RunEvent)).toHaveLength(1)"
        assert fill_findings(Fill(slot_id=_CREATE_SLOT, body=body), store_tables=["RunEvent"]) == []
        # A stack whose store is not table-keyed threads no set: the rule must not fire
        # on vocabulary it has no facts about.
        phantom = "expect(all(TABLES.Participant)).toHaveLength(1)"
        assert fill_findings(Fill(slot_id=_CREATE_SLOT, body=phantom)) == []

    def test_the_merge_degrades_the_slot_with_the_phantom_table_named(self, emission):
        text = f"```fill:{_CREATE_SLOT}\nexpect(all(TABLES.Participant)).toHaveLength(1)\n```\n"
        record = merge_fills(
            list(emission.files),
            emission.manifest,
            parse_fill_emission(text),
            store_tables=["RunEvent"],
        )
        disposition = record.by_slot()[_CREATE_SLOT]
        assert disposition.disposition == "rejected"
        assert "`TABLES.Participant`" in disposition.detail
        merged = next(f.content for f in record.files if _CREATE_SLOT in f.content)
        assert "fill rejected" in merged
        assert "expect(all(TABLES.Participant))" not in merged


class TestElementKindFindings:
    """#1094: a fill asserting an element kind the frozen floor contradicts is rejected at
    the fill gate, keyed on the DECLARED kind — never on the assertion's shape alone.

    The banked vocabulary from the 1.6.3 set is the fixture: rolls 3 and 7 (green) wrote
    `toContain('sample')` under `list[string]` and were right; roll 5 wrote the identical
    line under `list[Participant]` and rejected a correct repair with it.
    """

    OBJECT = {"participants": {"kind": "object", "required_fields": ["name", "joined_at"]}}
    PRIMITIVE = {"participants": {"kind": "primitive", "typeof": "string"}}

    @pytest.mark.parametrize(
        ("body", "kinds", "flagged"),
        [
            # roll 5's line under roll 5's manifest — the instance
            ("expect(body.participants).toContain('sample')", "OBJECT", True),
            ("expect(body.participants).not.toContain('sample')", "OBJECT", True),
            ("expect(all(TABLES.Run)[0].participants).toContain('sample')", "OBJECT", True),
            ("expect(body.participants).toEqual(['sample'])", "OBJECT", True),
            ("expect(body.participants).toContainEqual({ name: 'sample' })", "PRIMITIVE", True),
            ("expect(body.participants[0].name).toBe('sample')", "PRIMITIVE", True),
            # the same lines under the kind they agree with — rolls 3/7 and the greens
            ("expect(body.participants).toContain('sample')", "PRIMITIVE", False),
            ("expect(body.participants[0].name).toBe('sample')", "OBJECT", False),
            ("expect(body.participants[0].joined_at).toBeTruthy()", "OBJECT", False),
            ("expect(body.participants).toContainEqual({ name: 'sample' })", "OBJECT", False),
            # kind-neutral assertions never fire, under either declaration
            ("expect(body.participants).toHaveLength(1)", "OBJECT", False),
            ("expect(body.participants).toEqual([])", "OBJECT", False),
            ("expect(body.participants).toEqual([])", "PRIMITIVE", False),
            ("expect(body.participants).toContain(expected)", "OBJECT", False),
            # a field the floor does not pin is not this rule's business
            ("expect(body.tags).toContain('x')", "OBJECT", False),
        ],
    )
    def test_only_a_contradiction_of_the_declared_kind_is_a_finding(self, body, kinds, flagged):
        from squadops.capabilities.verification_scaffold_fill import element_kind_findings

        findings = element_kind_findings(body, getattr(self, kinds))
        assert bool(findings) is flagged, (body, kinds, findings)
        if flagged:
            assert "#1094" in findings[0] and "`participants`" in findings[0]

    def test_the_finding_names_the_declared_kind_and_the_fix(self):
        from squadops.capabilities.verification_scaffold_fill import element_kind_findings

        [finding] = element_kind_findings(
            "expect(body.participants).toContain('sample')", self.OBJECT
        )
        assert "`name`" in finding and "`joined_at`" in finding
        assert "participants[i].<field>" in finding

    def test_the_merge_degrades_the_slot_under_its_own_kinds(self, emission):
        """Roll 5, end to end at the seam: the join slot's fill contradicts the join
        behavior's floor; the slot is rejected with the declared kind named, and a slot
        with no pinned collection is untouched by the same assertion."""
        join = "slot-vc-probe-api-runs-join"
        text = f"```fill:{join}\nexpect(body.participants).toContain('sample')\n```\n"
        record = merge_fills(
            list(emission.files),
            emission.manifest,
            parse_fill_emission(text),
            slot_element_kinds={join: self.OBJECT},
        )
        disposition = record.by_slot()[join]
        assert disposition.disposition == "rejected"
        assert "#1094" in disposition.detail
        # the same fill on a slot the kinds map does not cover is a valid fill
        record = merge_fills(
            list(emission.files),
            emission.manifest,
            parse_fill_emission(text),
            slot_element_kinds={"slot-vc-probe-api-runs": self.OBJECT},
        )
        assert record.by_slot()[join].disposition == "filled"

    def test_the_kinds_are_derived_per_slot_from_the_shells_own_behaviors(self):
        """The gate reads the fact the floor asserts — one derivation. Every behavior with a
        success floor on the reference pins `participants` as objects; rejections carry
        no floor and no kinds."""
        from squadops.capabilities.verification_scaffold_emission import slot_element_kinds

        kinds = slot_element_kinds(manifest_for_stack("nextjs_ts"))
        assert kinds["slot-vc-probe-api-runs-join"]["participants"]["kind"] == "object"
        assert "name" in kinds["slot-vc-probe-api-runs-join"]["participants"]["required_fields"]
        assert "slot-vc-probe-api-runs-rejects-blank" not in kinds
        assert "slot-vc-probe-api-runs-join-duplicate" not in kinds
        # stack #1 emits no scaffold: nothing to contradict, nothing threaded
        assert slot_element_kinds(manifest_for_stack("fullstack_fastapi_react")) == {}
