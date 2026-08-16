"""The Gate 2 static corpus — readiness is judged from emitted bytes (SIP-0104 P2).

Every case here injects a GENERATOR defect: the inputs are internally consistent (the
reference manifest and its own expanded tree), and only the emission is broken. A gate
that re-derived from the generator's intent would pass every one of these — reading the
bytes is what makes them catchable, which is the plan's decisive Gate 2 requirement.

These tests tamper ``emission.files`` only. P1's structural validation (record/output
agreement) is a separate layer with its own corpus; conflating the two here would let a
readiness regression hide behind a structural failure.
"""

from __future__ import annotations

import dataclasses

import pytest

from squadops.capabilities.scaffold import expand
from squadops.capabilities.verification_scaffold import ScaffoldValidationError
from squadops.capabilities.verification_scaffold_emission import emit_verification_scaffold
from squadops.capabilities.verification_scaffold_gate import (
    assess_execution_readiness,
    validate_execution_readiness,
)
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

_CREATE_SHELL = "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"


@pytest.fixture(scope="module")
def manifest():
    return manifest_for_stack("nextjs_ts")


@pytest.fixture(scope="module")
def tree(manifest):
    return expand(manifest)


@pytest.fixture(scope="module")
def emission(manifest, tree):
    return emit_verification_scaffold(manifest, expanded=tree)


def _tamper(emission, path: str, old: str, new: str, rename: str | None = None):
    """A copy of ``emission`` with one file's bytes (and optionally name) altered."""
    files = []
    for f in emission.files:
        if f["name"] == path:
            content = f["content"].replace(old, new)
            assert content != f["content"] or rename, f"tamper did not apply: {old!r}"
            files.append({"name": rename or f["name"], "content": content})
        else:
            files.append(f)
    return dataclasses.replace(emission, files=tuple(files))


def test_the_reference_emission_is_ready(emission, tree, manifest):
    assert assess_execution_readiness(emission, tree, manifest) == []


class TestInjectedGeneratorDefects:
    def test_wrong_emitted_import_path_is_caught(self, emission, tree, manifest):
        """THE decisive Gate 2 case: manifest and tree agree the route exists; only the
        emitted specifier is wrong. Intent-level checks cannot see this."""
        tampered = _tamper(
            emission, _CREATE_SHELL, "'@/app/api/runs/route'", "'@/app/api/run/route'"
        )
        findings = assess_execution_readiness(tampered, tree, manifest)
        assert any("resolves to no file" in f and "@/app/api/run/route" in f for f in findings)

    def test_invoking_an_unexported_handler_is_caught(self, emission, tree, manifest):
        tampered = _tamper(emission, _CREATE_SHELL, "routeApiRuns.POST", "routeApiRuns.PSOT")
        findings = assess_execution_readiness(tampered, tree, manifest)
        assert any("does not export 'PSOT'" in f for f in findings)

    def test_a_named_import_the_module_lacks_is_caught(self, emission, tree, manifest):
        tampered = _tamper(
            emission,
            _CREATE_SHELL,
            "import { reset, all } from '@/lib/store'",
            "import { restart } from '@/lib/store'",
        )
        findings = assess_execution_readiness(tampered, tree, manifest)
        assert any("'restart'" in f and "does not export" in f for f in findings)

    def test_an_undeclared_bare_dependency_is_caught(self, emission, tree, manifest):
        """The roll-9 supertest class, closed for the spine."""
        tampered = _tamper(
            emission,
            _CREATE_SHELL,
            "import { reset, all } from '@/lib/store'",
            "import { reset, all } from '@/lib/store'\nimport { agent } from 'supertest'",
        )
        findings = assess_execution_readiness(tampered, tree, manifest)
        assert any("'supertest'" in f and "not a declared dependency" in f for f in findings)

    def test_a_status_the_contract_does_not_declare_is_caught(self, emission, tree, manifest):
        tampered = _tamper(emission, _CREATE_SHELL, ".toBe(201)", ".toBe(418)")
        findings = assess_execution_readiness(tampered, tree, manifest)
        assert any("asserts status 418" in f for f in findings)

    def test_a_file_outside_the_collection_surface_is_caught(self, emission, tree, manifest):
        """The #884 class: a suite emitted where the include glob cannot see it."""
        tampered = _tamper(
            emission, _CREATE_SHELL, "", "", rename="scaffold/vc-probe-api-runs.test.ts"
        )
        findings = assess_execution_readiness(tampered, tree, manifest)
        assert any("outside the runner's collection surface" in f for f in findings)

    def test_a_stripped_probe_identity_is_caught(self, emission, tree, manifest):
        """Bound criterion identity must survive into the emitted file (plan P2)."""
        tampered = _tamper(emission, _CREATE_SHELL, " [vc-probe-api-runs]", "")
        findings = assess_execution_readiness(tampered, tree, manifest)
        assert any("probe id 'vc-probe-api-runs' does not survive" in f for f in findings)


def test_validate_raises_scaffold_invalid_with_all_findings(emission, tree, manifest):
    """Findings accumulate — a generator with three defects gets one report naming three,
    not three rounds of one."""
    tampered = _tamper(emission, _CREATE_SHELL, ".toBe(201)", ".toBe(418)")
    tampered = _tamper(tampered, _CREATE_SHELL, "routeApiRuns.POST", "routeApiRuns.PSOT")
    with pytest.raises(ScaffoldValidationError, match="scaffold-invalid") as exc:
        validate_execution_readiness(tampered, tree, manifest)
    message = str(exc.value)
    assert "418" in message and "PSOT" in message
