"""Gate 4 — the adversarial corpus: the LLM cannot mechanically rewrite the scaffold.

Every case drives the REAL enforcement chokepoint (``enforce_frozen_ownership``) with a
REAL bound record built from the reference manifest — the same objects a run binds. The
hash-sufficiency claim (SIP §4.3) is demonstrated here: every mutation class the plan
names is caught by the slot-elided canonicalization + structure parse + slot-set check +
body containment. AST-level verification remains the named escalation if a mutation this
corpus misses ever appears — evidence first, not an undefined future.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from squadops.capabilities.verification_scaffold_emission import emit_verification_scaffold
from squadops.cycles.bound_scaffold_record import BoundScaffoldRecord, build_bound_record
from squadops.cycles.scaffold_enforcement import (
    enforce_frozen_ownership,
    shell_emission_instruction,
)
from squadops.cycles.task_outcome import (
    CONTRACT_COMPLIANCE_ACTIONS,
    ContractComplianceViolation,
)
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_contracts]

_CREATE_SHELL = "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"


@pytest.fixture(scope="module")
def manifest():
    return manifest_for_stack("nextjs_ts")


@pytest.fixture(scope="module")
def record(manifest):
    return build_bound_record(manifest, run_id="run_x", attempt_id="run_x", created_at="")


@pytest.fixture(scope="module")
def shells(manifest):
    emission = emit_verification_scaffold(manifest)
    return {f["name"]: f["content"] for f in emission.files}


def _envelope(task_type: str = "qa.test"):
    return SimpleNamespace(task_id="task-1", task_type=task_type)


def _enforce(record, *artifacts, task_type: str = "qa.test"):
    return enforce_frozen_ownership(list(artifacts), record, _envelope(task_type))


def _art(name: str, content: str) -> dict:
    return {"name": name, "content": content, "type": "test"}


class TestBoundRecordCarriesTheScaffold:
    def test_the_record_binds_shell_spines_and_round_trips(self, record):
        assert record.verification_scaffold is not None
        assert len(record.verification_scaffold.files) == 8
        loaded = BoundScaffoldRecord.from_dict(record.to_dict())
        assert loaded.verification_scaffold == record.verification_scaffold

    def test_a_pre_p4_record_deserializes_with_region_enforcement_off(self, record):
        d = record.to_dict()
        del d["verification_scaffold"]
        assert BoundScaffoldRecord.from_dict(d).verification_scaffold is None

    def test_shells_are_not_whole_file_frozen(self, record):
        """Shells are region-frozen, not file-frozen — a legal body edit must not be
        eaten by the whole-file lane."""
        assert _CREATE_SHELL not in record.frozen_paths()


class TestAdversarialProducerEndToEnd:
    """The plan's single strongest check: one fixture attempts, in turn, every
    adversarial move — and each lands in its expected failure class deterministically."""

    @pytest.mark.parametrize(
        ("label", "mutate", "expected_code", "fragment"),
        [
            (
                "changing an import",
                lambda t: t.replace("'@/lib/store'", "'@/lib/other'"),
                ContractComplianceViolation.SCAFFOLD_REGION_VIOLATION,
                "frozen spine mutated",
            ),
            (
                "changing the invocation strategy",
                lambda t: t.replace(
                    "await (routeApiRuns.POST as Handler)(",
                    "await fetch('http://localhost:3000/api/runs', (",
                ),
                ContractComplianceViolation.SCAFFOLD_REGION_VIOLATION,
                "frozen spine mutated",
            ),
            (
                "modifying a status assertion",
                lambda t: t.replace("expect(res.status).toBe(201)", "expect(res.status).toBe(200)"),
                ContractComplianceViolation.SCAFFOLD_REGION_VIOLATION,
                "frozen spine mutated",
            ),
            (
                "moving a slot boundary above the assertion",
                lambda t: t.replace(
                    "    expect(res.status).toBe(201)\n"
                    "    const body: any = await res.json().catch(() => ({}))\n"
                    "    // [scaffold-slot:begin slot-vc-probe-api-runs]",
                    "    // [scaffold-slot:begin slot-vc-probe-api-runs]\n"
                    "    expect(res.status).toBe(201)\n"
                    "    const body: any = await res.json().catch(() => ({}))",
                ),
                ContractComplianceViolation.SCAFFOLD_REGION_VIOLATION,
                "frozen spine mutated",
            ),
            (
                "pointing the slot body at a live server",
                lambda t: t.replace(
                    "    void body",
                    "    const live = await fetch('http://localhost:3000/api/runs')",
                ),
                ContractComplianceViolation.PROHIBITED_FILL_EMISSION,
                "fetch()",
            ),
            (
                "smuggling an import into the slot body",
                lambda t: t.replace("    void body", "    import request from 'supertest'"),
                ContractComplianceViolation.PROHIBITED_FILL_EMISSION,
                "import",
            ),
        ],
    )
    def test_each_shell_attack_lands_in_its_class(
        self, record, shells, label, mutate, expected_code, fragment
    ):
        content = mutate(shells[_CREATE_SHELL])
        assert content != shells[_CREATE_SHELL], label
        enforced, evidence = _enforce(record, _art(_CREATE_SHELL, content))
        assert enforced == [], label  # dropped; the prior valid version stays current
        assert len(evidence) == 1
        assert evidence[0].violation_code == expected_code, label
        assert fragment in evidence[0].detail, (label, evidence[0].detail)
        assert evidence[0].disposition == "dropped"

    def test_adding_a_dependency_hits_the_whole_file_frozen_lane(self, record):
        """package.json is file-frozen (SIP-0100) — the dependency attack never reaches
        region rules."""
        enforced, evidence = _enforce(record, _art("package.json", '{"dependencies": {}}'))
        assert enforced == []
        assert evidence[0].violation_code == ContractComplianceViolation.FROZEN_PATH_EMISSION

    def test_rewriting_another_test_file_hits_the_frozen_lane(self, record):
        enforced, evidence = _enforce(record, _art("__tests__/harness.test.ts", "// rewritten"))
        assert enforced == []
        assert evidence[0].violation_code == ContractComplianceViolation.FROZEN_PATH_EMISSION

    def test_a_legal_body_edit_passes_any_role(self, record, shells):
        """The one legal shape — body edits inside intact markers — passes for qa AND for
        a dev-locus repair (content-based, role-independent: §4.3's 'any role, any locus'
        cuts both ways)."""
        content = shells[_CREATE_SHELL].replace("    void body", "    expect(body.id).toBeTruthy()")
        for task_type in ("qa.test", "development.develop"):
            enforced, evidence = _enforce(record, _art(_CREATE_SHELL, content), task_type=task_type)
            assert [a["name"] for a in enforced] == [_CREATE_SHELL], task_type
            assert evidence == [], task_type

    def test_an_additive_test_file_still_passes(self, record):
        enforced, evidence = _enforce(record, _art("__tests__/extra.test.ts", "// additive"))
        assert [a["name"] for a in enforced] == ["__tests__/extra.test.ts"]
        assert evidence == []


class TestSlotBoundaryManipulation:
    """SIP §4.3's second protected class, each manipulation explicit."""

    @pytest.mark.parametrize(
        ("label", "mutate", "fragment"),
        [
            (
                "deleting a marker pair (region removed)",
                lambda t: t.replace(
                    "// [scaffold-slot:begin slot-vc-probe-api-runs]\n", ""
                ).replace("// [scaffold-slot:end slot-vc-probe-api-runs]\n", ""),
                "slot set changed",
            ),
            (
                "deleting only the end marker",
                lambda t: t.replace("    // [scaffold-slot:end slot-vc-probe-api-runs]\n", ""),
                "slot structure malformed",
            ),
            (
                "duplicating the slot",
                lambda t: t.replace(
                    "    // [scaffold-slot:end slot-vc-probe-api-runs]",
                    "    // [scaffold-slot:end slot-vc-probe-api-runs]\n"
                    "    // [scaffold-slot:begin slot-vc-probe-api-runs]\n"
                    "    // [scaffold-slot:end slot-vc-probe-api-runs]",
                ),
                "slot structure malformed",
            ),
            (
                "nesting a forged slot",
                lambda t: t.replace(
                    "    void body",
                    "    // [scaffold-slot:begin slot-forged]\n"
                    "    // [scaffold-slot:end slot-forged]",
                ),
                "slot structure malformed",
            ),
            (
                "renaming a slot id",
                lambda t: t.replace("slot-vc-probe-api-runs]", "slot-vc-probe-api-runz]"),
                "slot set changed",
            ),
            (
                "injecting a statement adjacent to the slot",
                lambda t: t.replace(
                    "    // [scaffold-slot:end slot-vc-probe-api-runs]\n",
                    "    // [scaffold-slot:end slot-vc-probe-api-runs]\n"
                    "    globalThis.leaked = true\n",
                ),
                "frozen spine mutated",
            ),
        ],
    )
    def test_each_manipulation_is_caught(self, record, shells, label, mutate, fragment):
        content = mutate(shells[_CREATE_SHELL])
        assert content != shells[_CREATE_SHELL], label
        enforced, evidence = _enforce(record, _art(_CREATE_SHELL, content))
        assert enforced == [], label
        assert (
            evidence[0].violation_code == ContractComplianceViolation.SCAFFOLD_REGION_VIOLATION
        ), label
        assert fragment in evidence[0].detail, (label, evidence[0].detail)


class TestAttribution:
    def test_a_spine_mutation_reports_spine_vs_spine(self, record, shells):
        content = shells[_CREATE_SHELL].replace("'@/lib/store'", "'@/lib/other'")
        _, evidence = _enforce(record, _art(_CREATE_SHELL, content))
        e = evidence[0]
        assert e.expected_sha256 != e.attempted_sha256  # the spine itself moved

    def test_a_containment_violation_shows_the_spine_intact(self, record, shells):
        """The attribution property: a prohibited fill did NOT move the spine — the hash
        pair proves which layer the defect lives in."""
        content = shells[_CREATE_SHELL].replace(
            "    void body", "    const r = await fetch('http://x')"
        )
        _, evidence = _enforce(record, _art(_CREATE_SHELL, content))
        e = evidence[0]
        assert e.expected_sha256 == e.attempted_sha256  # spine identical; body was the sin

    def test_sibling_artifacts_survive_a_shell_drop(self, record, shells):
        content = shells[_CREATE_SHELL].replace("toBe(201)", "toBe(200)")
        enforced, evidence = _enforce(
            record,
            _art(_CREATE_SHELL, content),
            _art("__tests__/extra.test.ts", "// additive"),
        )
        assert [a["name"] for a in enforced] == ["__tests__/extra.test.ts"]
        assert evidence[0].siblings_retained == 1


class TestRepairPathSignal:
    def test_the_instruction_names_the_shell_and_the_defect(self, record, shells):
        content = shells[_CREATE_SHELL].replace("toBe(201)", "toBe(200)")
        _, evidence = _enforce(record, _art(_CREATE_SHELL, content))
        instruction = shell_emission_instruction(evidence[0])
        assert _CREATE_SHELL in instruction
        assert "frozen spine mutated" in instruction
        assert "slot" in instruction  # tells the repairer where the writable surface is

    def test_the_correction_runner_carries_the_signal_to_the_next_attempt(self, record, shells):
        """Restore-and-signal on the repair path (Gate 4 exit): a repair step's shell
        rewrite is dropped IN PLACE and the next attempt's carry receives the
        instruction — through the runner's own enforcement method."""
        from adapters.cycles.correction_runner import CorrectionRunner

        runner = CorrectionRunner.__new__(CorrectionRunner)
        runner._emit_scaffold_integrity_evidence = lambda *a, **k: None
        content = shells[_CREATE_SHELL].replace("toBe(201)", "toBe(200)")
        result = SimpleNamespace(outputs={"artifacts": [_art(_CREATE_SHELL, content)]})
        carry: list[str] = []

        runner._enforce_step_emissions(result, _envelope(), "run_x", record, carry)

        assert result.outputs["artifacts"] == []  # dropped in place — restoration by retention
        assert len(carry) == 1
        assert _CREATE_SHELL in carry[0] and "frozen and hash-verified" in carry[0]

    def test_both_new_codes_have_corrective_actions(self):
        assert (
            CONTRACT_COMPLIANCE_ACTIONS[ContractComplianceViolation.SCAFFOLD_REGION_VIOLATION]
            == "reject_and_edit_slot_bodies_only"
        )
        assert (
            CONTRACT_COMPLIANCE_ACTIONS[ContractComplianceViolation.PROHIBITED_FILL_EMISSION]
            == "reject_and_fix_fill_content"
        )
