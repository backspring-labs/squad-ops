"""The assertion-kind gate (#1153): a free-authored suite's literal assertions against the
manifest's declared field kinds.

1.6.6 React roll 3 (``cyc_38d1e1689766``): the manifest declared
``LeaveResult.removed: boolean``; every qa emission asserted ``body["removed"] == "Carol"``;
the round-0 repair set it ``True`` — correct per the contract — and was rejected by the
suite's own assertion, three rounds running; rejected, audit FAIL. The contradiction is
between an assertion and a declared kind, so it is decidable at emission — the
free-authored counterpart of #1094's fill kind gate. Each test names the bug it catches;
the replays run the stored suites of the roll that cost it and of two accepted rolls.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from squadops.capabilities.response_shape import declared_field_kinds
from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.acceptance_check_spec import CHECK_ASSERTION_KINDS
from squadops.cycles.acceptance_checks import (
    assertion_literal_kinds_js,
    assertion_literal_kinds_python,
)
from squadops.cycles.acceptance_evaluation import get_check
from squadops.cycles.failure_evidence import FailureLocus, classify_failure_locus
from squadops.cycles.task_plan import _assertion_kind_criteria

pytestmark = [pytest.mark.domain_cycles]

_REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"


def _kinds(name: str) -> dict[str, str]:
    manifest = InterfaceManifest.from_yaml(
        (_REPLAYS / f"{name}-interface_manifest.yaml").read_text()
    )
    return declared_field_kinds(manifest)


async def _evaluate(tmp_path: Path, rel: str, source: str, kinds: dict[str, str]):
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source)
    return await get_check(CHECK_ASSERTION_KINDS).evaluate(
        {"file": rel, "field_kinds": kinds}, tmp_path
    )


class TestThePythonExtractor:
    def test_the_roll_3_shape_and_its_neighbours(self):
        """Bug caught: reading only one operand order, or missing ``.get`` and ``is``."""
        tree = ast.parse(
            'assert body["removed"] == "Carol"\n'
            'assert "Carol" == body["removed"]\n'
            'assert resp.json().get("removed") is True\n'
            'assert body["participants"] == ["Alice"]\n'
            'assert body["run"]["participant_count"] == 2\n'
            'assert body["run"] == {"id": "r1"}\n'
            'assert body["count"] == -1\n'
        )
        assert assertion_literal_kinds_python(tree) == [
            ("removed", "string", 1),
            ("removed", "string", 2),
            ("removed", "boolean", 3),
            ("participants", "list", 4),
            ("participant_count", "number", 5),
            ("run", "object", 6),
            ("count", "number", 7),
        ]

    def test_what_is_out_of_scope_yields_nothing(self):
        """Bug caught: judging a comparison to a name, a call, ``None``, ``!=`` or ``in`` —
        none of which the text decides, and each a false positive in a blocking check."""
        tree = ast.parse(
            'assert body["id"] == run_id\n'
            'assert body["id"] == make_id()\n'
            'assert body.get("distance") is None\n'
            'assert body["removed"] != "Carol"\n'
            'assert "Carol" in body["participants"]\n'
            'assert body["removed"]\n'
            'assert 1 < body["count"] < 3\n'
        )
        assert assertion_literal_kinds_python(tree) == []


class TestTheJsExtractor:
    def test_the_vitest_forms(self):
        source = (
            "expect(body.removed).toBe('Carol')\n"
            'expect(res.body["removed"]).toEqual("Alice")\n'
            "expect((await res.json()).participants).toStrictEqual([])\n"
            "expect(run.participant_count).toBe(2)\n"
            "expect(data.run).toEqual({ id: 'r1' })\n"
            "expect(data.ok).toBe(true)\n"
        )
        assert assertion_literal_kinds_js(source) == [
            ("removed", "string", 1),
            ("removed", "string", 2),
            ("participants", "list", 3),
            ("participant_count", "number", 4),
            ("run", "object", 5),
            ("ok", "boolean", 6),
        ]

    def test_negation_names_and_null_are_out_of_scope(self):
        source = (
            "expect(body.removed).not.toBe('Carol')\n"
            "expect(body.id).toBe(runId)\n"
            "expect(body.distance).toBe(null)\n"
            "expect(body.distance).toBeUndefined()\n"
            "expect(screen.getByText('x')).toBeInTheDocument()\n"
        )
        assert assertion_literal_kinds_js(source) == []


class TestDeclaredFieldKinds:
    def test_the_roll_3_manifest_declares_removed_as_boolean(self):
        kinds = _kinds("1-6-6-react-roll-3")
        assert kinds["removed"] == "boolean"
        assert kinds["participants"] == "list"
        assert kinds["participant_count"] == "number"
        assert kinds["id"] == "string"

    def test_a_name_declared_with_two_kinds_is_left_out(self):
        """Bug caught: guessing which entity a body is. ``status`` is a string on one entity
        and a number on another; the gate must not bind it to either."""
        manifest = SimpleNamespace(
            entities=[
                SimpleNamespace(
                    name="Run",
                    fields=[
                        SimpleNamespace(name="status", type="string"),
                        SimpleNamespace(name="id", type="string"),
                    ],
                ),
                SimpleNamespace(
                    name="Job",
                    fields=[
                        SimpleNamespace(name="status", type="integer"),
                        SimpleNamespace(name="owner", type="Run"),
                        SimpleNamespace(name="tags", type="list[string]"),
                        SimpleNamespace(name="blob", type="mystery"),
                    ],
                ),
            ]
        )
        assert declared_field_kinds(manifest) == {"id": "string", "owner": "object", "tags": "list"}
        assert declared_field_kinds(None) == {}


class TestTheEvaluator:
    async def test_the_roll_3_contradiction_fails_naming_field_line_and_kind(self, tmp_path):
        outcome = await _evaluate(
            tmp_path,
            "backend/tests/test_runs.py",
            'def test_leave(client):\n    body = client.post("/runs/1/leave").json()\n'
            '    assert body["removed"] == "Carol"\n',
            _kinds("1-6-6-react-roll-3"),
        )
        assert outcome.status == "failed"
        assert "line 3: removed asserted as string" in outcome.reason
        assert "declares removed: boolean" in outcome.reason
        assert outcome.actual["contradictions"] == [
            {"line": 3, "field": "removed", "asserted": "string", "declared": "boolean"}
        ]

    async def test_a_compatible_assertion_and_an_undeclared_field_pass(self, tmp_path):
        outcome = await _evaluate(
            tmp_path,
            "backend/tests/test_runs.py",
            'def test_leave(client):\n    body = client.post("/runs/1/leave").json()\n'
            '    assert body["removed"] is True\n    assert body["participants"] == []\n'
            '    assert body["not_declared"] == "anything"\n',
            _kinds("1-6-6-react-roll-3"),
        )
        assert outcome.status == "passed"
        assert outcome.actual["assertions_read"] == 3

    async def test_the_react_frontend_suite_is_read_too(self, tmp_path):
        outcome = await _evaluate(
            tmp_path,
            "frontend/src/tests/views.test.jsx",
            "import { expect, it } from 'vitest'\n"
            "it('leaves', async () => {\n"
            "  const body = await leave()\n"
            "  expect(body.removed).toBe('Carol')\n"
            "})\n",
            _kinds("1-6-6-react-roll-3"),
        )
        assert outcome.status == "failed"
        assert "line 4: removed asserted as string" in outcome.reason

    async def test_no_declaration_is_an_injection_bug_not_the_suites(self, tmp_path):
        outcome = await _evaluate(tmp_path, "backend/tests/test_runs.py", "x = 1\n", {})
        assert outcome.status == "error"
        assert outcome.reason == "missing_field_kinds"

    async def test_a_syntax_error_is_the_syntax_gates(self, tmp_path):
        outcome = await _evaluate(
            tmp_path, "backend/tests/test_runs.py", "def broken(:\n", {"removed": "boolean"}
        )
        assert outcome.status == "skipped"
        assert outcome.reason == "unsupported_stack_or_syntax"


class TestInjectionAndRouting:
    def test_bound_qa_suites_get_the_gate_with_the_manifests_kinds(self):
        """Bug caught: the check injected without its data, or onto files outside the
        stack's QA namespace, or in author mode."""
        manifest = InterfaceManifest.from_yaml(
            (_REPLAYS / "1-6-6-react-roll-3-interface_manifest.yaml").read_text()
        )
        contract = SimpleNamespace(skeleton=SimpleNamespace(expander="fullstack_fastapi_react"))
        task = SimpleNamespace(
            expected_artifacts=[
                "backend/tests/test_runs.py",
                "frontend/src/tests/views.test.jsx",
                "backend/routes.py",
                "notes.md",
            ]
        )
        checks = _assertion_kind_criteria("qa.test", task, contract, manifest)
        assert [c.params["file"] for c in checks] == [
            "backend/tests/test_runs.py",
            "frontend/src/tests/views.test.jsx",
        ]
        assert all(c.check == CHECK_ASSERTION_KINDS for c in checks)
        assert checks[0].params["field_kinds"]["removed"] == "boolean"
        assert checks[0].id == "assertion-kinds:backend/tests/test_runs.py"
        assert _assertion_kind_criteria("development.develop", task, contract, manifest) == []
        assert _assertion_kind_criteria("qa.test", task, None, manifest) == []
        assert _assertion_kind_criteria("qa.test", task, contract, None) == []

    def test_a_failed_gate_is_the_suites_own_defect(self):
        """Bug caught: routing the contradiction to the dev chain — roll 3's three rounds
        repaired a correct app against a wrong test."""
        row = {"check": f"acceptance:{CHECK_ASSERTION_KINDS}", "passed": False, "status": "failed"}
        assert classify_failure_locus({"validation_result": {"checks": [row]}}) == (
            FailureLocus.OWN_ARTIFACT
        )


class TestReplays:
    """The stored suites, under their own manifests. Roll 3 must be rejected naming
    ``removed: boolean``; the accepted rolls' suites must pass — the over-rejection
    control, without which a blocking check is a new way to lose a correct app."""

    async def test_roll_3_is_rejected_with_the_declared_kind_named(self, tmp_path):
        outcome = await _evaluate(
            tmp_path,
            "backend/tests/test_runs.py",
            (_REPLAYS / "1-6-6-react-roll-3-backend-suite.py.txt").read_text(),
            _kinds("1-6-6-react-roll-3"),
        )
        assert outcome.status == "failed"
        assert outcome.actual["contradictions"] == [
            {"line": 167, "field": "removed", "asserted": "string", "declared": "boolean"}
        ]

    @pytest.mark.parametrize("roll", ["1-6-6-react-roll-1", "1-6-6-react-roll-5"])
    async def test_the_accepted_rolls_suites_pass(self, tmp_path, roll):
        outcome = await _evaluate(
            tmp_path,
            "backend/tests/test_runs.py",
            (_REPLAYS / f"{roll}-backend-suite.py.txt").read_text(),
            _kinds(roll),
        )
        assert outcome.status == "passed"
        assert outcome.actual["assertions_read"] > 0
