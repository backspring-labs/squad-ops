"""Generator correctness — deterministic output, authoritative derivation (SIP-0104 P1).

P1 owns generation correctness (plan Gate 1): deterministic output, derivation that refuses
to guess, manifest production. The standing byte-equivalence pin against the committed
reference fixture lives in ``test_verification_scaffold_reference.py``; this file owns the
behavior-level and refusal cases.
"""

from __future__ import annotations

import pytest
import yaml

from squadops.capabilities import verification_scaffold_emission as emission_module
from squadops.capabilities.scaffold import InterfaceManifest, expand, verification_scaffold_for
from squadops.capabilities.verification_scaffold import (
    ScaffoldDerivationError,
    ScaffoldValidationError,
    expanded_tree_hash,
)
from squadops.capabilities.verification_scaffold_emission import (
    GENERATOR_VERSION,
    VerificationScaffoldEmission,
    emit_verification_scaffold,
    validate_emission,
)
from tests.unit.capabilities._stack_fixtures import manifest_dict_for_stack, manifest_for_stack


@pytest.fixture(scope="module")
def nextjs_manifest():
    return manifest_for_stack("nextjs_ts")


@pytest.fixture(scope="module")
def emission(nextjs_manifest):
    return emit_verification_scaffold(nextjs_manifest)


def _variant_manifest(mutate) -> InterfaceManifest:
    raw = manifest_dict_for_stack("nextjs_ts")
    mutate(raw)
    return InterfaceManifest.from_yaml(yaml.safe_dump(raw, sort_keys=False))


class TestDeterminism:
    def test_two_emissions_are_byte_identical(self, nextjs_manifest, emission):
        """The SIP's core generation claim: same inputs + generator version ⇒ same bytes."""
        again = emit_verification_scaffold(nextjs_manifest)
        assert again.files == emission.files
        assert again.manifest_yaml == emission.manifest_yaml
        assert again.manifest == emission.manifest


class TestInventory:
    def test_reference_inventory_is_probes_plus_reads(self, emission):
        """The behavior inventory for the reference design: 5 probe twins + 3 read shells.

        A silently shrunken inventory (a classification bug dropping the duplicate twin,
        say) would pass every structural check while quietly removing required coverage.
        """
        assert [f["name"] for f in emission.files] == [
            "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts",
            "__tests__/scaffold/vc-probe-api-runs-rejects-blank.scaffold.test.ts",
            "__tests__/scaffold/vc-probe-api-runs-join.scaffold.test.ts",
            "__tests__/scaffold/vc-probe-api-runs-join-duplicate.scaffold.test.ts",
            "__tests__/scaffold/vc-probe-api-runs-leave.scaffold.test.ts",
            "__tests__/scaffold/vs-get-api-runs.scaffold.test.ts",
            "__tests__/scaffold/vs-get-api-runs-run-id.scaffold.test.ts",
            "__tests__/scaffold/vs-get-api-runs-run-id-not-found.scaffold.test.ts",
        ]

    def test_probe_twins_bind_their_probe_and_minted_shells_bind_none(self, emission):
        slots = {s.slot_id: s for f in emission.manifest.files for s in f.slots}
        twin = slots["slot-vc-probe-api-runs-join"]
        assert twin.probe_id == "vc-probe-api-runs-join"
        assert twin.criterion_ids == ("vc-probe-api-runs-join",)
        minted = slots["slot-vs-get-api-runs"]
        assert minted.probe_id == ""
        assert minted.criterion_ids == ()

    def test_chained_shells_replay_the_probe_sequence_prefix(self, emission):
        """The leave twin must join before leaving; the duplicate twin must join twice.

        This is the derivation of probe-runner sequence semantics into isolated tests —
        getting it wrong makes a correct app fail its own scaffold.
        """
        by_name = {f["name"]: f["content"] for f in emission.files}
        leave = by_name["__tests__/scaffold/vc-probe-api-runs-leave.scaffold.test.ts"]
        assert leave.count("routeApiRunsRunIdJoin.POST") == 1
        assert leave.count("routeApiRunsRunIdLeave.POST") == 1
        assert leave.index("routeApiRunsRunIdJoin.POST") < leave.index(
            "routeApiRunsRunIdLeave.POST"
        )
        duplicate = by_name["__tests__/scaffold/vc-probe-api-runs-join-duplicate.scaffold.test.ts"]
        assert duplicate.count("routeApiRunsRunIdJoin.POST") == 2

    def test_dynamic_invocations_carry_the_params_argument(self, emission):
        """The #877 tail this SIP exists to close: `{ params }` is frozen, never invented."""
        by_name = {f["name"]: f["content"] for f in emission.files}
        read = by_name["__tests__/scaffold/vs-get-api-runs-run-id.scaffold.test.ts"]
        assert "{ params: { run_id: created.id } }" in read
        listing = by_name["__tests__/scaffold/vs-get-api-runs.scaffold.test.ts"]
        assert "params" not in listing

    def test_unmapped_not_found_omits_the_shell_deterministically(self):
        """Demote, never guess (#874): no 404 mapping ⇒ no unknown-id shell, same run."""
        variant = _variant_manifest(
            lambda raw: raw["api"]["endpoints"][2].__setitem__("errors", [])
        )
        result = emit_verification_scaffold(variant)
        names = [f["name"] for f in result.files]
        assert "__tests__/scaffold/vs-get-api-runs-run-id.scaffold.test.ts" in names
        assert "__tests__/scaffold/vs-get-api-runs-run-id-not-found.scaffold.test.ts" not in names


class TestEnvelopePinning:
    """#913: behaviors whose contract pins an error code assert the envelope in the
    FROZEN spine — the response-field path stops being fill residue. Window rolls
    2/3 (and 13/17 before them) died on fills asserting `body.error_code` against
    the real `{error: {code}}`; the shell now owns that byte."""

    def test_rejection_and_duplicate_shells_pin_the_contract_code(self, emission):
        """The bug this catches: the code the contract pins never reaching the
        spine, leaving the field path to the fill's invention."""
        pinned = {}
        for f in emission.files:
            name = f["name"].rsplit("/", 1)[-1]
            if "rejects-blank" in name or "duplicate" in name:
                lines = [ln.strip() for ln in f["content"].splitlines() if "body.error?.code" in ln]
                pinned[name] = lines
        assert len(pinned) == 2
        for name, lines in pinned.items():
            assert len(lines) == 1, f"{name}: expected exactly one frozen envelope assertion"
            assert lines[0].startswith("expect(body.error?.code).toBe(")

    def test_the_assertion_is_spine_not_slot(self, emission):
        """Frozen means BEFORE the slot markers — an assertion inside the slot is
        fill residue again, deletable by the next re-author."""
        for f in emission.files:
            content = f["content"]
            if "body.error?.code" not in content:
                continue
            assert content.index("body.error?.code") < content.index("scaffold-slot:begin")

    def test_success_shells_pin_no_envelope(self, emission):
        """A success body has no error envelope — asserting one there would fail
        every correct app (the false-positive direction the gate must never take)."""
        for f in emission.files:
            name = f["name"].rsplit("/", 1)[-1]
            if "rejects-blank" in name or "duplicate" in name or "not-found" in name:
                continue
            assert "body.error" not in f["content"], name


class TestManifestRecord:
    def test_record_carries_the_attribution_facts(self, nextjs_manifest, emission):
        record = emission.manifest
        assert record.generator_version == GENERATOR_VERSION
        assert record.stack == "nextjs_ts"
        assert record.criteria_pack == "nextjs_ts"
        assert record.interface_manifest_hash == nextjs_manifest.content_hash()
        assert record.expanded_tree_hash == expanded_tree_hash(expand(nextjs_manifest))

    def test_manifest_yaml_round_trips_through_the_schema(self, emission):
        from squadops.capabilities.verification_scaffold import VerificationScaffoldManifest

        loaded = VerificationScaffoldManifest.from_dict(yaml.safe_load(emission.manifest_yaml))
        assert loaded == emission.manifest


class TestRefusals:
    def test_a_stack_that_has_not_opted_in_is_refused(self):
        assert verification_scaffold_for("fullstack_fastapi_react") == ""
        with pytest.raises(ScaffoldDerivationError, match="has not opted in"):
            emit_verification_scaffold(manifest_for_stack("fullstack_fastapi_react"))

    def test_declared_but_unregistered_emitter_is_refused(self, nextjs_manifest, monkeypatch):
        monkeypatch.delitem(emission_module._EMITTERS, "nextjs_ts")
        with pytest.raises(ScaffoldDerivationError, match="not registered"):
            emit_verification_scaffold(nextjs_manifest)

    def test_a_tree_missing_a_declared_route_file_is_refused(self, nextjs_manifest):
        """SIP §7: manifest-vs-tree disagreement is generator drift or workspace mutation,
        named — never a best-effort scaffold."""
        tree = [f for f in expand(nextjs_manifest) if f["name"] != "app/api/runs/route.ts"]
        with pytest.raises(ScaffoldDerivationError, match="has no file"):
            emit_verification_scaffold(nextjs_manifest, expanded=tree)

    def test_a_tree_whose_stub_lacks_the_handler_export_is_refused(self, nextjs_manifest):
        tree = [
            (
                {
                    "name": f["name"],
                    "content": f["content"].replace(
                        "export async function POST", "async function POST"
                    ),
                }
                if f["name"] == "app/api/runs/route.ts"
                else f
            )
            for f in expand(nextjs_manifest)
        ]
        with pytest.raises(ScaffoldDerivationError, match="does not export POST"):
            emit_verification_scaffold(nextjs_manifest, expanded=tree)

    def test_a_tree_missing_the_store_seam_is_refused(self, nextjs_manifest):
        tree = [f for f in expand(nextjs_manifest) if f["name"] != "lib/store.ts"]
        with pytest.raises(ScaffoldDerivationError, match="lib/store.ts"):
            emit_verification_scaffold(nextjs_manifest, expanded=tree)


class TestValidateEmission:
    def test_content_drift_from_the_record_is_a_validation_error(self, emission):
        """The gate must catch a generator whose output and record disagree — the
        consistent-inputs/broken-generator class P2 extends (plan Gate 2's decisive case)."""
        files = tuple(
            (
                {"name": f["name"], "content": f["content"].replace("toBe(201)", "toBe(200)")}
                if f["name"] == "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"
                else f
            )
            for f in emission.files
        )
        tampered = VerificationScaffoldEmission(
            files=files, manifest=emission.manifest, manifest_yaml=emission.manifest_yaml
        )
        with pytest.raises(ScaffoldValidationError, match="do not reproduce"):
            validate_emission(tampered)

    def test_a_missing_file_is_a_validation_error(self, emission):
        tampered = VerificationScaffoldEmission(
            files=emission.files[1:],
            manifest=emission.manifest,
            manifest_yaml=emission.manifest_yaml,
        )
        with pytest.raises(ScaffoldValidationError, match="disagree"):
            validate_emission(tampered)
