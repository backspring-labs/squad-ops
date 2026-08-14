"""The scaffold contract's own guarantees (SIP-0104 P1 commit 1).

Everything here defends the canonicalization the whole SIP rests on: fills must never move
the spine hash, every structural mutation must, and malformed slot structure must fail
loudly rather than hash around. The generator (commit 2) and region enforcement (P4) both
consume these exact functions, so a bug here is a bug in both.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.verification_scaffold import (
    SCAFFOLD_MANIFEST_VERSION,
    BehaviorSlot,
    ScaffoldSpineError,
    ScaffoldValidationError,
    VerificationScaffoldFile,
    VerificationScaffoldManifest,
    build_scaffold_file,
    elide_slot_bodies,
    expanded_tree_hash,
    parse_slot_regions,
    slot_begin_marker,
    slot_end_marker,
    spine_hash,
)

_SHELL = """// header line
import { reset } from '@/lib/store'

it('behavior one', async () => {
  expect(res.status).toBe(201)
  // [scaffold-slot:begin slot-vc-probe-api-runs]
  // FILL: domain assertions.
  // [scaffold-slot:end slot-vc-probe-api-runs]
})

it('behavior two', async () => {
  // [scaffold-slot:begin slot-vs-get-api-runs]
  // [scaffold-slot:end slot-vs-get-api-runs]
})
"""


class TestParseSlotRegions:
    def test_regions_carry_exact_marker_line_numbers(self):
        """Off-by-one bounds would make P4 enforcement elide the wrong lines."""
        regions = parse_slot_regions(_SHELL)
        assert [(r.slot_id, r.begin_line, r.end_line) for r in regions] == [
            ("slot-vc-probe-api-runs", 6, 8),
            ("slot-vs-get-api-runs", 12, 13),
        ]

    def test_indented_markers_parse(self):
        text = "  // [scaffold-slot:begin slot-a1]\n  // [scaffold-slot:end slot-a1]\n"
        regions = parse_slot_regions(text)
        assert [(r.slot_id, r.begin_line, r.end_line) for r in regions] == [("slot-a1", 1, 2)]

    @pytest.mark.parametrize(
        ("text", "fragment"),
        [
            # Unclosed at EOF: the slot would silently swallow the rest of the file.
            ("// [scaffold-slot:begin slot-a1]\nbody\n", "never closed"),
            # End with no open region.
            ("// [scaffold-slot:end slot-a1]\n", "no open slot"),
            # Nesting: an inner region would let a fill smuggle a second mutable zone.
            (
                "// [scaffold-slot:begin slot-a1]\n"
                "// [scaffold-slot:begin slot-b2]\n"
                "// [scaffold-slot:end slot-b2]\n"
                "// [scaffold-slot:end slot-a1]\n",
                "cannot nest",
            ),
            # Mismatched end id.
            (
                "// [scaffold-slot:begin slot-a1]\n// [scaffold-slot:end slot-b2]\n",
                "does not match open slot",
            ),
            # Duplicate id in one file: slot addressing (P3) would be ambiguous.
            (
                "// [scaffold-slot:begin slot-a1]\n// [scaffold-slot:end slot-a1]\n"
                "// [scaffold-slot:begin slot-a1]\n// [scaffold-slot:end slot-a1]\n",
                "duplicate slot id",
            ),
            # Near-miss marker: a typo must fail, not become frozen spine text.
            ("// [scaffold-slot:begin BadId]\n", "not a well-formed"),
            ("// [scaffold-slot:beginning slot-a1]\n", "not a well-formed"),
        ],
    )
    def test_malformed_structure_raises_with_the_defect_named(self, text, fragment):
        with pytest.raises(ScaffoldSpineError, match=fragment):
            parse_slot_regions(text)


class TestSpineCanonicalization:
    def test_editing_a_slot_body_never_moves_the_spine_hash(self):
        """THE invariant: an authored fill must not read as a spine mutation."""
        filled = _SHELL.replace(
            "  // FILL: domain assertions.\n",
            "  expect(body.id).toBeTruthy()\n  expect(all('runs')).toHaveLength(1)\n",
        )
        assert filled != _SHELL
        assert spine_hash(filled) == spine_hash(_SHELL)

    def test_elision_keeps_markers_and_drops_bodies(self):
        spine = elide_slot_bodies(_SHELL)
        assert "// [scaffold-slot:begin slot-vc-probe-api-runs]" in spine
        assert "// [scaffold-slot:end slot-vc-probe-api-runs]" in spine
        assert "// FILL: domain assertions." not in spine
        assert "expect(res.status).toBe(201)" in spine

    @pytest.mark.parametrize(
        ("mutate", "label"),
        [
            # Each of these is a P4 adversarial class; the canonicalization must see all.
            (lambda t: t.replace("@/lib/store", "@/lib/other"), "import edit"),
            (lambda t: t.replace("toBe(201)", "toBe(200)"), "status assertion edit"),
            (
                lambda t: t.replace(
                    "// [scaffold-slot:end slot-vc-probe-api-runs]\n})",
                    "// [scaffold-slot:end slot-vc-probe-api-runs]\n  fetch('http://x')\n})",
                ),
                "statement injected adjacent to a slot",
            ),
            (
                lambda t: t.replace(
                    "  expect(res.status).toBe(201)\n"
                    "  // [scaffold-slot:begin slot-vc-probe-api-runs]\n",
                    "  // [scaffold-slot:begin slot-vc-probe-api-runs]\n"
                    "  expect(res.status).toBe(201)\n",
                ),
                "region enlarged upward (assertion swallowed into the slot body)",
            ),
        ],
    )
    def test_every_structural_mutation_moves_the_spine_hash(self, mutate, label):
        mutated = mutate(_SHELL)
        assert mutated != _SHELL, label
        assert spine_hash(mutated) != spine_hash(_SHELL), label

    def test_crlf_rewrite_is_a_spine_mutation(self):
        assert spine_hash(_SHELL.replace("\n", "\r\n")) != spine_hash(_SHELL)


class TestMarkerBuilders:
    def test_builders_round_trip_through_the_parser(self):
        text = f"{slot_begin_marker('slot-x9')}\nbody\n{slot_end_marker('slot-x9')}\n"
        assert [r.slot_id for r in parse_slot_regions(text)] == ["slot-x9"]

    @pytest.mark.parametrize("bad", ["", "x", "slot-", "slot-A", "vc-probe-x", "slot-a_b"])
    def test_invalid_slot_ids_are_rejected(self, bad):
        with pytest.raises(ValueError, match="invalid slot id"):
            slot_begin_marker(bad)


def _slot(slot_id: str, probe_id: str = "") -> BehaviorSlot:
    return BehaviorSlot(slot_id=slot_id, behavior="b", probe_id=probe_id)


class TestBuildScaffoldFile:
    def test_region_bounds_are_recomputed_from_content(self):
        f = build_scaffold_file(
            "__tests__/scaffold/x.scaffold.test.ts",
            _SHELL,
            (_slot("slot-vc-probe-api-runs", "vc-probe-api-runs"), _slot("slot-vs-get-api-runs")),
        )
        bounds = {s.slot_id: (s.begin_line, s.end_line) for s in f.slots}
        assert bounds == {
            "slot-vc-probe-api-runs": (6, 8),
            "slot-vs-get-api-runs": (12, 13),
        }

    def test_slot_table_and_content_disagreement_is_a_validation_error(self):
        """The generator declaring a slot its own emission lacks is a generator defect."""
        with pytest.raises(ScaffoldValidationError, match="disagree"):
            build_scaffold_file("x.ts", _SHELL, (_slot("slot-vc-probe-api-runs"),))


def _manifest(files: tuple[VerificationScaffoldFile, ...]) -> VerificationScaffoldManifest:
    return VerificationScaffoldManifest(
        scaffold_manifest_version=SCAFFOLD_MANIFEST_VERSION,
        generator_version=1,
        stack="nextjs_ts",
        interface_manifest_hash="m" * 64,
        criteria_pack="nextjs_ts",
        expanded_tree_hash="t" * 64,
        files=files,
    )


def _file(path: str, slot_id: str, spine: str = "s1") -> VerificationScaffoldFile:
    return VerificationScaffoldFile(
        path=path, content_hash="c" * 64, spine_hash=spine, slots=(_slot(slot_id),)
    )


class TestManifest:
    def test_aggregates_are_file_order_independent(self):
        """The hash names a set of files; emission-order refactors must not move it."""
        a, b = _file("a.ts", "slot-a1"), _file("b.ts", "slot-b2", spine="s2")
        assert _manifest((a, b)).aggregate_spine_hash() == _manifest((b, a)).aggregate_spine_hash()
        assert _manifest((a, b)).scaffold_hash() == _manifest((b, a)).scaffold_hash()

    def test_lint_names_cross_file_duplicates_and_empty_files(self):
        m = _manifest(
            (
                _file("a.ts", "slot-a1"),
                _file("b.ts", "slot-a1"),
                VerificationScaffoldFile(path="c.ts", content_hash="c" * 64, spine_hash="s"),
            )
        )
        findings = m.lint()
        assert any("duplicate slot id 'slot-a1'" in f for f in findings)
        assert any("c.ts: scaffold file with no behavior slots" in f for f in findings)

    def test_lint_flags_an_unknown_schema_version(self):
        m = VerificationScaffoldManifest(
            scaffold_manifest_version=99,
            generator_version=1,
            stack="nextjs_ts",
            interface_manifest_hash="m" * 64,
            criteria_pack="nextjs_ts",
            expanded_tree_hash="t" * 64,
        )
        assert any("99" in f for f in m.lint())

    def test_round_trip_preserves_identity(self):
        m = _manifest((_file("a.ts", "slot-a1"),))
        assert VerificationScaffoldManifest.from_dict(m.to_dict()) == m

    def test_a_tampered_stored_aggregate_refuses_to_load(self):
        """A hand-edited record must not launder itself into an enforcement authority."""
        d = _manifest((_file("a.ts", "slot-a1"),)).to_dict()
        d["aggregate_spine_hash"] = "0" * 64
        with pytest.raises(ScaffoldValidationError, match="mutated"):
            VerificationScaffoldManifest.from_dict(d)

    def test_find_slot_returns_owning_file(self):
        m = _manifest((_file("a.ts", "slot-a1"), _file("b.ts", "slot-b2", spine="s2")))
        found = m.find_slot("slot-b2")
        assert found is not None and found[0].path == "b.ts"
        assert m.find_slot("slot-missing") is None


class TestExpandedTreeHash:
    def test_order_independent_and_content_sensitive(self):
        files = [{"name": "a.ts", "content": "x"}, {"name": "b.ts", "content": "y"}]
        assert expanded_tree_hash(files) == expanded_tree_hash(list(reversed(files)))
        changed = [{"name": "a.ts", "content": "x2"}, {"name": "b.ts", "content": "y"}]
        assert expanded_tree_hash(changed) != expanded_tree_hash(files)
