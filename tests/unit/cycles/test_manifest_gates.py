"""The winnability gate: can this manifest be won? (#781, M3)

Bug classes guarded:

- a gate that rejects the **known-good** manifest — worse than no gate, because it
  blocks the one design proven to work;
- a proof that fires on the wrong manifest, so a rejection points at the wrong fix;
- #772's shape — a collection POST with no ``success_status`` — reaching a cycle, where
  the derived contract asserts 201 against a scaffold emitting 200 and the probe fails
  on correct code (this cost a roll at pf-39 before the field existed);
- short-circuiting, which would make an author fix one defect per revision and exhaust
  ``manifest_max_attempts`` on a manifest that had several.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadops.cycles.manifest_gates import (
    PROOF_CONTRACT_DERIVES,
    PROOF_ERROR_SHAPE,
    PROOF_EXPANDS,
    PROOF_PARSES,
    PROOF_STATUS_DECLARED,
    PROOF_TESTID_COVERAGE,
    assess_winnability,
)

_REFERENCE = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


def _reference_dict() -> dict:
    return yaml.safe_load(_REFERENCE.read_text(encoding="utf-8"))


def _as_yaml(data: dict) -> str:
    return yaml.dump(data, sort_keys=False)


def _proofs(findings) -> set[str]:
    return {f.proof for f in findings}


def test_the_reference_manifest_is_winnable():
    """A gate that rejects the design the 1.4 evidence was measured against is wrong
    about the rule, not about the manifest."""
    assert assess_winnability(_REFERENCE.read_text(encoding="utf-8")) == ()


def test_unparseable_manifest_reports_only_the_parse_failure():
    """Nothing downstream can run without a parsed manifest, so piling on findings
    derived from a half-read document would misdirect the fix."""
    findings = assess_winnability("this: [is not: valid\n  yaml at all")

    assert _proofs(findings) == {PROOF_PARSES}


def test_collection_post_without_success_status_is_unwinnable():
    """#772's designed-failure probe.

    The deriver expects ``success_status or 201`` for a collection POST while the
    scaffold omits ``status_code=`` when undeclared, so FastAPI returns 200 — the
    contract asserts 201 against a correct implementation.
    """
    data = _reference_dict()
    for ep in data["api"]["endpoints"]:
        if ep["method"] == "POST" and "{" not in ep["path"]:
            ep.pop("success_status", None)

    findings = assess_winnability(_as_yaml(data))

    assert PROOF_STATUS_DECLARED in _proofs(findings)
    detail = next(f.detail for f in findings if f.proof == PROOF_STATUS_DECLARED)
    assert "201" in detail and "200" in detail  # names both sides of the disagreement
    assert "success_status" in detail  # names the fix


def test_v4_class_foreign_root_error_shape_is_unwinnable():
    """#795 (V4 roll 1): `error_contract.shape: '{"detail": "string"}'` declared
    FastAPI's default while the frozen envelope is error-rooted — a dev reading the
    authored contract writes handling against a key no response carries, and every
    gate passed because nothing compared them."""
    data = _reference_dict()
    data["api"]["error_contract"]["shape"] = '{"detail": "string"}'
    findings = assess_winnability(_as_yaml(data))
    assert PROOF_ERROR_SHAPE in _proofs(findings)
    detail = next(f.detail for f in findings if f.proof == PROOF_ERROR_SHAPE)
    assert "detail" in detail and "error" in detail


def test_vague_but_true_error_shape_passes():
    """Banked green manifests declare `{"error": "..."}` — under-specified, not
    wrong. A rule that rejects the artifacts the evidence was measured against is
    the wrong rule."""
    data = _reference_dict()
    data["api"]["error_contract"]["shape"] = '{"error": "..."}'
    assert PROOF_ERROR_SHAPE not in _proofs(assess_winnability(_as_yaml(data)))


def test_absent_error_shape_passes():
    """The field is optional; silence defers to the blueprint's envelope."""
    data = _reference_dict()
    data["api"]["error_contract"].pop("shape", None)
    assert PROOF_ERROR_SHAPE not in _proofs(assess_winnability(_as_yaml(data)))


def test_child_post_without_success_status_is_fine():
    """Deliberately narrow: child actions default to 200 on BOTH sides and agree.

    Requiring the field everywhere would reject the reference manifest, which declares
    it on 1 of 5 endpoints.
    """
    data = _reference_dict()
    for ep in data["api"]["endpoints"]:
        if "{" in ep["path"]:
            ep.pop("success_status", None)

    assert PROOF_STATUS_DECLARED not in _proofs(assess_winnability(_as_yaml(data)))


def test_get_without_success_status_is_fine():
    """GETs derive no status probe, so there is nothing to disagree about."""
    data = _reference_dict()
    for ep in data["api"]["endpoints"]:
        if ep["method"] == "GET":
            ep.pop("success_status", None)

    assert PROOF_STATUS_DECLARED not in _proofs(assess_winnability(_as_yaml(data)))


def test_route_without_testids_is_unwinnable():
    """A view with no declared anchor leaves qa guessing at markup the dev may change."""
    data = _reference_dict()
    data["frontend"]["routes"][0].pop("testids", None)
    dropped = data["frontend"]["routes"][0]["path"]

    findings = assess_winnability(_as_yaml(data))

    assert PROOF_TESTID_COVERAGE in _proofs(findings)
    assert dropped in next(f.detail for f in findings if f.proof == PROOF_TESTID_COVERAGE)


def test_manifest_with_no_endpoints_or_routes_has_nothing_to_implement():
    """Every file frozen means the cycle would 'succeed' having produced nothing."""
    data = _reference_dict()
    data["api"]["endpoints"] = []
    data["frontend"]["routes"] = []

    findings = assess_winnability(_as_yaml(data))

    assert findings  # rejected on some proof
    assert PROOF_EXPANDS in _proofs(findings) or "lint" in _proofs(findings)


def test_all_proofs_run_so_one_revision_can_fix_everything():
    """No short-circuit: an author who sees one defect per attempt burns the revision
    budget on a manifest that had two."""
    data = _reference_dict()
    for ep in data["api"]["endpoints"]:
        if ep["method"] == "POST" and "{" not in ep["path"]:
            ep.pop("success_status", None)
    data["frontend"]["routes"][0].pop("testids", None)

    proofs = _proofs(assess_winnability(_as_yaml(data)))

    assert {PROOF_STATUS_DECLARED, PROOF_TESTID_COVERAGE} <= proofs


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(lambda d: d["api"].__setitem__("endpoints", []), id="no-endpoints"),
        pytest.param(lambda d: d.__setitem__("stack", "not_a_real_stack"), id="unknown-stack"),
    ],
)
def test_structurally_doomed_manifests_are_rejected(mutation):
    """The classes the SIP-0099 linter already names, reached through this gate."""
    data = _reference_dict()
    mutation(data)

    assert assess_winnability(_as_yaml(data)) != ()


# ---------------------------------------------------------------------------
# M2 — the schema gate: provenance and the decisions[] record (#783)
#
# Bug classes guarded: adding `decisions` to the model moving the manifest's
# structural hash, which would invalidate the contract bound to it and break every
# bind-mode cycle; a choice recorded with no citation back to the PRD, which is
# indistinguishable from an invention; an `unresolved` marker that defers a design
# question without saying which one; and a decision leaking into the derived contract,
# where it could become something a check depends on.
# ---------------------------------------------------------------------------

from squadops.capabilities.scaffold import InterfaceManifest  # noqa: E402
from squadops.cycles.manifest_gates import (  # noqa: E402
    PROOF_DECISION_RECORD,
    PROOF_SOURCE_PRD,
    assess_schema,
)

# The manifest hash contract v9 is bound to (`skeleton.interface_manifest_hash`).
_BOUND_MANIFEST_HASH = "bb472e267e53d5ad29406663b4340de45613dd68fa091fe7f2d06a99b7267530"


def test_reference_manifest_passes_the_schema_gate():
    assert assess_schema(_REFERENCE.read_text(encoding="utf-8")) == ()


def test_decisions_do_not_move_the_structural_hash():
    """The constraint that governs this whole item.

    `_canonical()` is "every field the expander reads, and nothing else" — provenance is
    excluded so a provenance-only edit cannot invalidate the contract bound to the hash.
    Decisions are judgment, not structure. If they entered the projection, contract v9's
    binding would break and every bind-mode cycle with it.
    """
    manifest = InterfaceManifest.from_yaml(_REFERENCE.read_text(encoding="utf-8"))

    assert manifest.decisions  # the field is populated, not silently empty
    assert manifest.content_hash() == _BOUND_MANIFEST_HASH


def test_revising_a_decision_never_invalidates_the_contract():
    """The consequence worth stating: an author may improve an explanation without
    re-deriving anything, because the design did not change."""
    data = _reference_dict()
    data["decisions"][0]["warrant"] = "§9.9 — a completely different citation"
    data["decisions"].append(
        {"id": "added-later", "choice": "something", "warrant": "§1.1 — anything"}
    )

    revised = InterfaceManifest.from_yaml(_as_yaml(data))

    assert revised.content_hash() == _BOUND_MANIFEST_HASH


def test_decisions_never_reach_the_derived_contract():
    """Lifecycle rule 3 holds *by construction*: since decisions are absent from the
    contract, no derived check can depend on an unresolved one. Pinned rather than
    re-checked — a detector for an impossible condition is the pattern this repo rejects.
    """
    from squadops.capabilities.scaffold_contract import emit_contract_yaml

    data = _reference_dict()
    data["decisions"].append(
        {"id": "open-question", "unresolved": True, "question": "should runs expire?"}
    )

    emitted = emit_contract_yaml(InterfaceManifest.from_yaml(_as_yaml(data)))

    assert "open-question" not in emitted
    assert "should runs expire" not in emitted


def test_unresolved_decision_round_trips_and_is_preserved():
    """Preserved, never consumed: approval does not silently drop the open question."""
    data = _reference_dict()
    data["decisions"].append(
        {"id": "pagination", "unresolved": True, "question": "page size for GET /runs?"}
    )

    manifest = InterfaceManifest.from_yaml(_as_yaml(data))

    (open_one,) = [d for d in manifest.decisions if d.unresolved]
    assert open_one.id == "pagination"
    assert open_one.question == "page size for GET /runs?"
    assert assess_schema(_as_yaml(data)) == ()


@pytest.mark.parametrize(
    ("entry", "expected_fragment"),
    [
        ({"id": "no-warrant", "choice": "did a thing"}, "warrant"),
        ({"id": "no-choice", "warrant": "§1.1"}, "choice"),
        ({"id": "silent-defer", "unresolved": True}, "question"),
        ({"choice": "x", "warrant": "§1.1"}, "id"),
    ],
)
def test_malformed_decision_records_are_rejected(entry, expected_fragment):
    data = _reference_dict()
    data["decisions"].append(entry)

    findings = assess_schema(_as_yaml(data))

    assert PROOF_DECISION_RECORD in _proofs(findings)
    assert any(expected_fragment in f.detail for f in findings)


def test_manifest_without_source_prd_is_rejected():
    """A design that does not say what it was designed from cannot be reviewed."""
    data = _reference_dict()
    data["source_prd"] = ""

    findings = assess_schema(_as_yaml(data))

    assert PROOF_SOURCE_PRD in _proofs(findings)


# --------------------------------------------------------------------------- #
# #849 — a contract that fails its own linter never reaches a run
# --------------------------------------------------------------------------- #


def test_a_structurally_invalid_contract_is_a_winnability_finding(monkeypatch):
    """`VerificationContract.lint()` existed throughout and had no production caller.

    Its only callers were `scripts/dev/contract_gate.py` and unit tests, both running
    against the reference FastAPI manifest — whose criterion ids cannot collide. So the
    guard was exercised solely by the one input incapable of failing it, and stack #2's
    contract reached a live run with nine criteria under four ids.

    The pack is monkeypatched to re-create the defect rather than reverting the emitter
    fix, so this stays a test of the GATE. Otherwise it would silently become a duplicate
    of the emitter's own uniqueness test and stop covering the wiring, which is the half
    that was actually missing.
    """
    from squadops.capabilities import scaffold_contract

    real = scaffold_contract.emit_contract_dict

    def colliding(manifest):
        contract = real(manifest)
        for sections in (contract.get("fill_files") or {}).values():
            for entry in sections.get("implementation") or []:
                entry["id"] = "vc-same"
        return contract

    monkeypatch.setattr(scaffold_contract, "emit_contract_dict", colliding)

    findings = assess_winnability(_REFERENCE.read_text(encoding="utf-8"))

    assert PROOF_CONTRACT_DERIVES in _proofs(findings)
    detail = next(f.detail for f in findings if f.proof == PROOF_CONTRACT_DERIVES)
    assert "duplicate criterion id" in detail
    assert "'vc-same'" in detail or "vc-same" in detail


def test_the_rejection_says_why_a_duplicate_id_matters(monkeypatch):
    """ "Structurally invalid" is not actionable on its own.

    A duplicate id does not fail loudly — `criterion_index()` drops the losers and the plan
    still reads as fully bound. The message has to name that, or the next reader files it as
    cosmetic and waives it.
    """
    from squadops.capabilities import scaffold_contract

    real = scaffold_contract.emit_contract_dict

    def colliding(manifest):
        contract = real(manifest)
        for sections in (contract.get("fill_files") or {}).values():
            for entry in sections.get("implementation") or []:
                entry["id"] = "vc-same"
        return contract

    monkeypatch.setattr(scaffold_contract, "emit_contract_dict", colliding)

    detail = next(
        f.detail
        for f in assess_winnability(_REFERENCE.read_text(encoding="utf-8"))
        if f.proof == PROOF_CONTRACT_DERIVES
    )
    assert "silently" in detail and "unverified" in detail


def test_the_reference_contract_still_passes_the_new_lint_gate():
    """Polarity guard. A lint step wired into the winnability gate can reject manifests that
    were previously fine, and the reference pair is what every other pin rests on."""
    assert assess_winnability(_REFERENCE.read_text(encoding="utf-8")) == ()


class TestScaffoldReadinessProof:
    """SIP-0104 P2: PROOF_SCAFFOLD_READY converts a run-setup scaffold death into a free
    framing re-roll. Bug classes: the proof firing on an unopted stack (stack #1 would be
    rejected for lacking a scaffold it never declared), and an emission failure surfacing
    only at run setup after the framing gate read the manifest as winnable."""

    def test_the_nextjs_reference_manifest_is_winnable_with_its_scaffold(self):
        from tests.unit.capabilities._stack_fixtures import manifest_dict_for_stack

        content = yaml.safe_dump(manifest_dict_for_stack("nextjs_ts"), sort_keys=False)
        assert assess_winnability(content) == ()

    def test_stack_one_never_reaches_the_scaffold_proof(self):
        """The reference manifest (stack #1) already asserts zero findings above; this
        pins the reason — no verification_scaffold declaration means the proof skips,
        not that it passes by luck."""
        from squadops.capabilities.scaffold import verification_scaffold_for
        from squadops.cycles.manifest_gates import PROOF_SCAFFOLD_READY

        assert verification_scaffold_for("fullstack_fastapi_react") == ""
        findings = assess_winnability(_REFERENCE.read_text(encoding="utf-8"))
        assert PROOF_SCAFFOLD_READY not in _proofs(findings)

    def test_an_emission_refusal_is_a_winnability_finding(self, monkeypatch):
        from squadops.capabilities import verification_scaffold_emission as emission_module
        from squadops.capabilities.verification_scaffold import ScaffoldDerivationError
        from squadops.cycles.manifest_gates import PROOF_SCAFFOLD_READY
        from tests.unit.capabilities._stack_fixtures import manifest_dict_for_stack

        def _refuse(manifest, **kwargs):
            raise ScaffoldDerivationError("injected derivation refusal")

        monkeypatch.setattr(emission_module, "emit_verification_scaffold", _refuse)
        content = yaml.safe_dump(manifest_dict_for_stack("nextjs_ts"), sort_keys=False)
        findings = assess_winnability(content)
        assert PROOF_SCAFFOLD_READY in _proofs(findings)
        detail = next(f.detail for f in findings if f.proof == PROOF_SCAFFOLD_READY)
        assert "injected derivation refusal" in detail


class TestStatusOverrideWarrant:
    """#1067: a declared status contradicting the derived default needs a stated reason.

    The 200-vs-201 disagreement recurred five times in three weeks and took four fixes —
    #1013 (a gate comparing manifest to plan), #1042 (thread the status to the dev),
    #1049 (that gate's premise going stale), #1031 (queued: TEACH the convention). None
    asked why one integer needed four. The fact is authored in three places and derivable
    in one, and the schema let an author override the derivation with no warrant.
    """

    @staticmethod
    def _manifest(join_status: str = "", decisions: str = "") -> str:
        status = f", success_status: {join_status}" if join_status else ""
        block = decisions or "  - { id: d1, choice: c, warrant: w }"
        return f"""
version: 1
kind: interface_manifest
project_id: p
stack: nextjs_ts
source_prd: prd.md
entities:
  - name: Run
    fields:
      - {{ name: id, type: string, required: true }}
api:
  endpoints:
    - {{ method: POST, path: /api/runs, response: Run, success_status: 201 }}
    - {{ method: POST, path: "/api/runs/{{run_id}}/join", response: Run{status} }}
frontend:
  routes:
    - {{ path: /, view: V, testids: [a] }}
decisions:
{block}
"""

    def _findings(self, **kw):
        return [
            f
            for f in assess_winnability(self._manifest(**kw), "nextjs_ts")
            if f.proof == "status_warranted"
        ]

    def test_an_unwarranted_override_is_flagged(self):
        """Today's roll: the deriver said 200 for a child action, the plan author said
        200, and one unexplained manifest override said 201 — so the framing gate
        rejected the plan for agreeing with the rule."""
        findings = self._findings(join_status="201")
        assert len(findings) == 1
        assert "derives 200" in findings[0].detail
        assert "child-action" in findings[0].detail

    def test_silence_is_clean_and_is_the_point(self):
        """Say nothing and the rule decides. One value, nothing to disagree about — the
        whole reduction this issue is after."""
        assert self._findings() == []

    def test_a_declaration_agreeing_with_the_derivation_is_clean(self):
        """Restating the derived value is redundant, not wrong. Flagging it would push
        authors toward silence for the wrong reason and add noise."""
        assert self._findings(join_status="200") == []

    def test_a_warrant_naming_the_endpoint_and_the_status_passes(self):
        """The override is permitted — a child action that genuinely creates a
        sub-resource may return 201. It must be a recorded, challengeable judgment."""
        decisions = (
            "  - { id: join-creates, "
            'choice: "POST /api/runs/{run_id}/join returns 201; the join creates a '
            'participant sub-resource", warrant: "PRD 5.4 names the participant a '
            'created record" }'
        )
        assert self._findings(join_status="201", decisions=decisions) == []

    def test_a_decision_naming_the_endpoint_but_not_the_status_does_not_warrant_it(self):
        """The tightening that mattered, from a real false negative.

        `cyc_79eebcb82205` carried a decision reading "distinct POST paths
        /api/runs/{run_id}/join and /api/runs/{run_id}/leave rather than a shared
        endpoint with an action dispatch field" — a genuine judgment about ROUTING that
        says nothing about 201. A path-only rule accepted it and let the override
        through unexplained, which makes the warrant requirement decorative.
        """
        decisions = (
            "  - { id: join-leave-separate-endpoints, "
            'choice: "distinct POST paths /api/runs/{run_id}/join and '
            '/api/runs/{run_id}/leave rather than a shared endpoint", '
            'warrant: "single responsibility per handler" }'
        )
        findings = self._findings(join_status="201", decisions=decisions)
        assert len(findings) == 1
        assert "does not warrant the status" in findings[0].detail

    def test_a_warrant_for_a_DIFFERENT_endpoint_does_not_transfer(self):
        """Naming 201 somewhere in the decisions is not a warrant for this endpoint —
        the collection POST's own 201 is stated two lines up and must not launder it."""
        decisions = (
            '  - { id: create-201, choice: "POST /api/runs returns 201", warrant: "creation" }'
        )
        assert len(self._findings(join_status="201", decisions=decisions)) == 1

    def test_a_non_post_declaring_a_status_is_not_judged(self):
        """GETs derive no status probe, so there is nothing to contradict and nothing to
        warrant. Judging them would demand a `decisions[]` entry for a fact no surface
        enforces — the gate inventing work rather than preventing a disagreement."""
        manifest = self._manifest().replace(
            '- { method: POST, path: "/api/runs/{run_id}/join", response: Run }',
            '- { method: GET, path: "/api/runs/{run_id}", response: Run, success_status: 204 }',
        )
        assert [
            f for f in assess_winnability(manifest, "nextjs_ts") if f.proof == "status_warranted"
        ] == []

    def test_a_collection_post_declaring_201_is_clean(self):
        """The reference manifest declares it on the create endpoint, where it AGREES
        with the derivation. A rule that rejected the artifact the 1.4 evidence was
        measured against would be the wrong rule — the same guard `_status_findings`
        states in its own docstring."""
        assert self._findings() == []
