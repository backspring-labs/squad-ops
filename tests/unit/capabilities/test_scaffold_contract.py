"""Tests for verification-contract emission (SIP-0098 phase 98.2).

The load-bearing test is the 98.1 ↔ 98.2 interlock: the contract the expander emits
must lint clean against the cycles-domain schema/linter — an emitter that produced a
malformed or class-confused contract would be caught here, not in a cycle. The rest
pin the derivation (frozen covers every non-fill file by real hash; each slot carries
its interface + implementation criteria; the skeleton is bound by manifest hash) and
determinism (same manifest → same contract → same frozen hash).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from squadops.capabilities.scaffold import InterfaceManifest, expand, fill_slot_paths
from squadops.capabilities.scaffold_contract import (
    _probe_sample_value,
    emit_contract_dict,
    emit_contract_yaml,
)
from squadops.cycles.verification_contract import VerificationContract

pytestmark = [pytest.mark.domain_capabilities]

_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


def _manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _raw() -> dict:
    return yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# The interlock: emitted contract must lint clean (98.1's linter)
# --------------------------------------------------------------------------- #


def test_emitted_group_run_contract_lints_clean():
    contract = VerificationContract.from_dict(emit_contract_dict(_manifest()))
    assert contract.lint() == []


def test_emitted_yaml_roundtrips_and_lints_clean():
    # the actual artifact path: YAML text -> loader -> lint
    text = emit_contract_yaml(_manifest())
    assert text.startswith("# Verification contract")
    contract = VerificationContract.from_yaml(text)
    assert contract.lint() == []


def test_contract_without_error_contract_omits_apierror_and_lints_clean():
    # the ApiError seam is emitted only when the manifest declares an error contract
    def apierror_ids(contract: dict) -> list[str]:
        return [
            c["id"]
            for c in contract["fill_files"]["backend/routes.py"]["interface"]
            if c["id"] == "vc-routes-apierror"
        ]

    assert apierror_ids(emit_contract_dict(_manifest())) == ["vc-routes-apierror"]

    raw = _raw()
    raw["api"].pop("error_contract", None)
    without_ec = emit_contract_dict(InterfaceManifest.from_dict(raw))
    assert apierror_ids(without_ec) == []
    assert VerificationContract.from_dict(without_ec).lint() == []


# --------------------------------------------------------------------------- #
# Derivation
# --------------------------------------------------------------------------- #


def test_skeleton_bound_by_interface_manifest_hash():
    manifest = _manifest()
    contract = emit_contract_dict(manifest)
    assert contract["skeleton"]["expander"] == manifest.stack
    assert contract["skeleton"]["interface_manifest_hash"] == manifest.content_hash()


def test_frozen_covers_every_non_fill_file_by_real_hash():
    manifest = _manifest()
    files = {f["name"]: f["content"] for f in expand(manifest)}
    fill = set(fill_slot_paths(manifest))

    contract = emit_contract_dict(manifest)
    frozen = {entry["path"]: entry["sha256"] for entry in contract["frozen"]}

    assert set(frozen) == set(files) - fill  # every non-fill file, nothing else
    assert "backend/routes.py" not in frozen  # a fill slot is never frozen
    # hashes are of the actual expanded content (drift in a frozen file is detectable)
    for path, digest in frozen.items():
        assert digest == _sha256(files[path])


def test_fill_slots_carry_interface_and_implementation_criteria():
    contract = emit_contract_dict(_manifest())
    routes = contract["fill_files"]["backend/routes.py"]

    endpoints = next(c for c in routes["interface"] if c["check"] == "endpoint_defined")
    assert endpoints["methods_paths"] == [
        "GET /runs",
        "POST /runs",
        "GET /runs/{run_id}",
        "POST /runs/{run_id}/join",
        "POST /runs/{run_id}/leave",
    ]
    assert any(c["id"] == "vc-routes-apierror" for c in routes["interface"])
    compiles = next(c for c in routes["implementation"] if c["check"] == "command_exit_zero")
    assert compiles["argv"] == ["python", "-m", "py_compile", "backend/routes.py"]
    assert compiles["requires"] == "python"

    # #648: views carry the real-bundler criterion — fay-4/fay-8 shipped views
    # with rollup bind-time errors no static check (or node --check) can see,
    # invisible until final verification. Anchored to the view so #641 binds
    # it onto the view's own task.
    detail = contract["fill_files"]["frontend/src/views/RunDetailView.jsx"]
    assert detail["interface"] == []
    assert detail["implementation"] == [
        {
            "check": "frontend_compiles",
            "id": "vc-view-compiles-run-detail-view",
            "file": "frontend/src/views/RunDetailView.jsx",
            "requires": "node",
        }
    ]


def test_behavioral_has_build_suite_and_self_contained_probe():
    contract = emit_contract_dict(_manifest())
    behavioral = contract["behavioral"]

    assert behavioral["build"][0]["check"] == "frontend_build"
    assert behavioral["suite"]["checks"][0]["check"] == "tests_pass"
    assert any("happy path" in exp for exp in behavioral["suite"]["coverage_expectations"])

    # #651 (v8): the create probe leads, and the path-param child actions the
    # 98.4 deferral promised are now emitted as a chained sequence behind it.
    probe_paths = {p["request"]["path"] for p in behavioral["probes"]}
    assert probe_paths == {"/runs", "/runs/{run_id}/join", "/runs/{run_id}/leave"}
    create = behavioral["probes"][0]
    assert create["request"]["method"] == "POST"
    body = create["request"]["json"]
    assert set(body) == {"title", "datetime", "location"}
    # #524: the datetime field gets an ISO value, not "x" — an app that validates
    # datetime (pf-12) must not 422 the probe. Non-date fields get a plain string.
    assert body["datetime"] == "2026-08-01T08:00:00"
    assert body["title"] == "sample"
    assert (
        create["expect"]["status"] == 201
    )  # creates return 201 (pf-3: contract contradicted the PRD)


def test_capabilities_derived_from_what_criteria_require():
    contract = emit_contract_dict(_manifest())
    assert contract["capabilities"] == ["python", "node"]


def test_emission_is_deterministic():
    a = emit_contract_dict(_manifest())
    b = emit_contract_dict(_manifest())
    assert a == b
    # and the frozen hash the yield baseline measures against is stable
    assert (
        VerificationContract.from_dict(a).content_hash()
        == VerificationContract.from_dict(b).content_hash()
    )


# --------------------------------------------------------------------------- #
# probe sample-value generator (#524) — bug caught: "x" for every field made an
# app that validates its inputs (e.g. a datetime field) 422 the probe, failing a
# correct app. pf-12: app passed its own suite yet failed the probe on 422/201.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("name", "type_", "expected"),
    [
        ("datetime", "string", "2026-08-01T08:00:00"),
        ("start_at", "string", "2026-08-01T08:00:00"),
        ("timestamp", "string", "2026-08-01T08:00:00"),
        ("email", "string", "sample@example.com"),
        ("callback_url", "string", "https://example.com"),
        ("count", "int", 1),
        ("ratio", "number", 1.0),
        ("active", "bool", True),
        ("tags", "list[str]", []),
        ("title", "string", "sample"),
    ],
)
def test_probe_sample_value_is_type_and_name_appropriate(name, type_, expected):
    assert _probe_sample_value(name, type_) == expected


def test_datetime_name_beats_string_type():
    # the manifest declares datetime as type 'string' (MVP); the name must still
    # win so the value is a real ISO datetime, not a bare string
    assert _probe_sample_value("datetime", "string") == "2026-08-01T08:00:00"


def test_unknown_field_defaults_to_plain_string():
    assert _probe_sample_value("location", "string") == "sample"
    assert _probe_sample_value("whatever", "") == "sample"


def test_behavior_expectation_lines_carry_the_pinned_statuses():
    # #629 / pf-54: the emitted contract must be able to state its own HTTP pins
    # as authoring-prompt lines — the create probe's 201 and the error-code map.
    contract = VerificationContract.from_dict(emit_contract_dict(_manifest()))
    lines = contract.behavior_expectation_lines()
    assert "POST /runs → HTTP 201" in lines
    assert "validation_error -> HTTP 422" in lines
    assert "duplicate_participant -> HTTP 409" in lines


class TestBlankInputProbe:
    """#593: pf-38 volunteered blank-field guards and pf-39 didn't — both went
    green, because nothing required OR tested blank rejection. Now the scaffold
    model owns the constraint and this probe pins it against the running app."""

    def test_create_endpoint_emits_a_blank_rejection_probe(self):
        contract = VerificationContract.from_dict(emit_contract_dict(_manifest()))
        blank = [p for p in contract.behavioral.probes if p.id.endswith("-rejects-blank")]
        assert len(blank) == 1
        probe = blank[0]
        assert probe.request["method"] == "POST"
        assert probe.request["path"] == "/runs"
        # Every required create field sent blank — the exact pf-39 gap
        # (its suite posted ABSENT fields, a different behavior).
        assert probe.request["json"] == {"title": "", "datetime": "", "location": ""}
        assert probe.expect == {"status": 422, "error_code": "validation_error"}
        assert probe.guards == "scaffold"

    def test_blank_probe_contract_lints_clean_and_roundtrips(self):
        contract = VerificationContract.from_dict(emit_contract_dict(_manifest()))
        assert contract.lint() == []
        rt = VerificationContract.from_dict(contract.to_dict())
        blank = [p for p in rt.behavioral.probes if p.guards == "scaffold"]
        assert len(blank) == 1

    def test_bad_guards_value_is_a_lint_error(self):
        raw = emit_contract_dict(_manifest())
        for probe in raw["behavioral"]["probes"]:
            if probe["id"].endswith("-rejects-blank"):
                probe["guards"] = "skeleton"  # not a valid class
        errors = VerificationContract.from_dict(raw).lint()
        assert any("guards must be" in e for e in errors)

    def test_no_error_contract_emits_no_blank_probe(self):
        # Without the error contract there is no frozen 422-envelope handler to
        # pin error_code against — the probe is conditional on the seam.
        raw = _raw()
        raw["api"].pop("error_contract", None)
        manifest = InterfaceManifest.from_dict(raw)
        contract = VerificationContract.from_dict(emit_contract_dict(manifest))
        assert not [p for p in contract.behavioral.probes if p.id.endswith("-rejects-blank")]

    def test_emitted_model_constrains_required_request_fields(self):
        from squadops.capabilities.scaffold import expand

        files = {f["name"]: f["content"] for f in expand(_manifest())}
        models = files["backend/models.py"]
        assert (
            "NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]"
            in models
        )
        assert "    title: NonBlankStr" in models
        # Optional fields stay unconstrained — blankness only matters where
        # presence is required.
        assert "    distance: str | None = None" in models


class TestChainedActionProbes:
    """#651 (v8, fay-3): v7 probed create + blank rejection only, so an app with
    a BROKEN JOIN scored functional. Child POST actions are now probed in a
    manifest-derived sequence: the create captures the created id into the
    child path parameter; a declared-conflict action gets an immediate
    duplicate probe pinning the 409 envelope."""

    def _probes(self):
        contract = VerificationContract.from_dict(emit_contract_dict(_manifest()))
        return {p.id: p for p in contract.behavioral.probes}, [
            p.id for p in contract.behavioral.probes
        ]

    def test_create_probe_captures_the_child_path_parameter(self):
        probes, _ = self._probes()
        assert probes["vc-probe-runs"].capture == {"run_id": "id"}

    def test_join_leave_and_duplicate_probes_emitted_in_sequence(self):
        probes, order = self._probes()
        # Order matters: capture before use; join before its duplicate; the
        # duplicate before leave removes the participant.
        assert order.index("vc-probe-runs") < order.index("vc-probe-runs-join")
        assert order.index("vc-probe-runs-join") < order.index("vc-probe-runs-join-duplicate")
        assert order.index("vc-probe-runs-join-duplicate") < order.index("vc-probe-runs-leave")

        join = probes["vc-probe-runs-join"]
        assert join.request["path"] == "/runs/{run_id}/join"
        assert join.request["json"] == {"name": "sample"}
        assert join.expect == {"status": 200}

        # The duplicate expectation is read from the manifest's error contract
        # (duplicate_participant: http 409), never guessed.
        dup = probes["vc-probe-runs-join-duplicate"]
        assert dup.request == join.request
        assert dup.expect == {"status": 409, "error_code": "duplicate_participant"}

        # leave declares no 409-class error -> happy path only, no duplicate.
        leave = probes["vc-probe-runs-leave"]
        assert leave.expect == {"status": 200}
        assert "vc-probe-runs-leave-duplicate" not in probes

    def test_chained_contract_lints_clean_and_roundtrips_capture(self):
        contract = VerificationContract.from_dict(emit_contract_dict(_manifest()))
        assert contract.lint() == []
        rt = VerificationContract.from_dict(contract.to_dict())
        assert {p.id: p.capture for p in rt.behavioral.probes}["vc-probe-runs"] == {"run_id": "id"}

    def test_placeholder_without_earlier_capture_is_a_lint_error(self):
        raw = emit_contract_dict(_manifest())
        for probe in raw["behavioral"]["probes"]:
            probe.pop("capture", None)  # orphan the {run_id} placeholders
        errors = VerificationContract.from_dict(raw).lint()
        assert any("no earlier probe capturing it" in e for e in errors)


class TestBodyDiscriminatedActionProbes:
    """#948. The same child actions, expressed the other legal way: ONE POST at the
    parameterized path with a body field selecting the behavior. The `/runs/{id}/join`
    regex above requires a literal trailing segment, so this shape derived NOTHING —
    window roll 2 chose it and bought zero behavioral probes, leaving join and leave,
    the application's entire purpose, verified only by a freely-authored suite.

    The fix is emphatically NOT relaxing the regex. With only a field NAME the deriver
    can build `{"action": "sample"}`, which a correct app rejects, so probing on a guess
    manufactures false failures. The author declares the domain instead."""

    def _folded(self, *, values: dict | None = None, required=("action", "name")) -> dict:
        """The reference manifest with join/leave folded into one body-discriminated
        endpoint — roll 2's real shape."""
        raw = _raw()
        raw["api"]["endpoints"] = [
            ep
            for ep in raw["api"]["endpoints"]
            if not str(ep["path"]).endswith(("/join", "/leave"))
        ]
        raw["api"]["endpoints"].append(
            {
                "method": "POST",
                "path": "/runs/{run_id}",
                "summary": "join or leave",
                "request": "ParticipantAction",
                "response": "RunEvent",
                "errors": ["run_not_found", "validation_error", "duplicate_participant"],
            }
        )
        shape: dict = {"required": list(required)}
        if values is not None:
            shape["values"] = values
        raw["api"]["request_shapes"]["ParticipantAction"] = shape
        return raw

    def _probe_ids(self, raw: dict) -> list[str]:
        manifest = InterfaceManifest.from_dict(raw)
        return [p["id"] for p in emit_contract_dict(manifest)["behavioral"]["probes"]]

    def test_undeclared_values_still_derive_nothing(self):
        """The conservative half, and the reason this is a schema change rather than a
        regex change. A shape carrying only field NAMES cannot be probed without
        inventing a value, so it is not probed."""
        ids = self._probe_ids(self._folded())
        assert ids == ["vc-probe-runs", "vc-probe-runs-rejects-blank"]

    def test_declared_values_derive_one_probe_per_behavior(self):
        raw = self._folded(values={"action": ["join", "leave"]})
        manifest = InterfaceManifest.from_dict(raw)
        probes = {p["id"]: p for p in emit_contract_dict(manifest)["behavioral"]["probes"]}
        assert "vc-probe-runs-join" in probes
        assert "vc-probe-runs-leave" in probes

        join = probes["vc-probe-runs-join"]
        assert join["request"]["path"] == "/runs/{run_id}"
        # the discriminator carries the DECLARED value; every other required field is sampled
        assert join["request"]["json"] == {"action": "join", "name": "sample"}
        assert probes["vc-probe-runs-leave"]["request"]["json"]["action"] == "leave"

    def test_the_create_captures_the_parameter_these_probes_need(self):
        raw = self._folded(values={"action": ["join", "leave"]})
        manifest = InterfaceManifest.from_dict(raw)
        contract = VerificationContract.from_dict(emit_contract_dict(manifest))
        assert {p.id: p.capture for p in contract.behavioral.probes}["vc-probe-runs"] == {
            "run_id": "id"
        }
        assert contract.lint() == []

    def test_no_duplicate_probe_is_invented_for_a_folded_endpoint(self):
        """One endpoint carries every action, so a declared 409 cannot be attributed to a
        particular value. Repeating `leave` and expecting 409 would fail a correct app —
        guessing which action conflicts is the class of invention this fix avoids."""
        raw = self._folded(values={"action": ["join", "leave"]})
        assert not [pid for pid in self._probe_ids(raw) if pid.endswith("-duplicate")]

    def test_two_declared_discriminators_are_read_as_none(self):
        """Two would make the probe set a cross product whose size the author never sees,
        and which combinations are legal is not something the shape can state."""
        raw = self._folded(
            values={"action": ["join", "leave"], "mode": ["quiet", "loud"]},
            required=("action", "mode", "name"),
        )
        assert self._probe_ids(raw) == ["vc-probe-runs", "vc-probe-runs-rejects-blank"]

    def test_values_on_an_optional_field_do_not_discriminate(self):
        """A field the request need not carry cannot select the behavior — a probe
        omitting it would exercise an undeclared default."""
        raw = self._folded(values={"action": ["join", "leave"]}, required=("name",))
        assert self._probe_ids(raw) == ["vc-probe-runs", "vc-probe-runs-rejects-blank"]


class TestDeclaredValuesAndTheManifestHash:
    """`values` changes the derived contract, so it must change the manifest hash — a
    manifest whose contract differs must not share a hash with one whose contract does
    not. It is emitted only when declared, so no existing manifest's hash moves."""

    def test_a_manifest_without_values_hashes_exactly_as_before(self):
        """Pinned against the reference manifest, which declares none. If this moves,
        every stored contract binding in the system has been invalidated to record the
        absence of a field none of them use."""
        # Measured on main at 136fffb7, BEFORE `values` existed. A literal, because the
        # whole claim is that this number did not move — comparing the manifest to itself
        # would pass no matter what the projection did.
        assert (
            _manifest().content_hash()
            == "bb472e267e53d5ad29406663b4340de45613dd68fa091fe7f2d06a99b7267530"
        )
        assert all(s.values == () for s in _manifest().api.request_shapes)

    def test_declaring_values_moves_the_hash(self):
        raw = _raw()
        before = InterfaceManifest.from_dict(raw).content_hash()
        raw["api"]["request_shapes"]["RunEventCreate"]["values"] = {"title": ["a", "b"]}
        assert InterfaceManifest.from_dict(raw).content_hash() != before

    def test_values_survive_a_dict_roundtrip(self):
        raw = _raw()
        raw["api"]["request_shapes"]["RunEventCreate"]["values"] = {"title": ["a", "b"]}
        manifest = InterfaceManifest.from_dict(raw)
        shape = next(s for s in manifest.api.request_shapes if s.name == "RunEventCreate")
        assert shape.declared_values("title") == ("a", "b")
        assert shape.declared_values("datetime") == ()
