"""#670 — qa.test joins the typed-acceptance seam (owner-ruled fork 1).

The gap this closes, measured on shk-3: qa task 4 emitted
``backend/tests/test_runs.py`` with four authored typed checks and produced
NO typed-check evaluation — the checks were render-only, and the #689
framework injection never arrived either. These tests are that exhibit
inverted: authored checks and framework injections must both be load-bearing
on qa emissions, with dev-parity #423 evidence-gap accounting.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.cycles.implementation_plan import TypedCheck

pytestmark = [pytest.mark.domain_capabilities]

# Valid-Python filler so fixtures never trip the #689 injection by accident.
_VALID_TEST = "import json\n\n\ndef test_shapes():\n    assert json.loads('{}') == {}\n"

# The shk-3 / #689 exhibit class: a call-time NameError the suite would only
# surface when executed — `respones` is never defined.
_NAMEERROR_TEST = "import json\n\n\ndef test_runs():\n    assert respones.status_code == 200\n"

# Imports an app entry module directly — the SIP-0100 harness-boundary
# violation the scaffold-bound check exists to reject.
_BOUNDARY_VIOLATION_TEST = (
    "from app.main import app\n\n\ndef test_direct():\n    assert app is not None\n"
)


def _art(name: str, content: str) -> dict:
    return {"name": name, "content": content, "media_type": "text/x-python", "type": "test"}


def _inputs(criteria=(), *, expected=("backend/tests/test_runs.py",)) -> dict:
    return {
        "subtask_focus": "QA suite",
        "expected_artifacts": list(expected),
        "acceptance_criteria": list(criteria),
        # the fleet shape: build_profile resolves the check stack (#503)
        "resolved_config": {"build_profile": "fullstack_fastapi_react"},
    }


class TestAuthoredChecksAreLoadBearing:
    async def test_authored_check_failure_blocks_validation(self):
        # render-only no more: an authored error-severity check that fails
        # must fail qa validation, not decorate it
        h = QATestHandler()
        criteria = [
            TypedCheck(
                check="function_defined",
                params={
                    "file": "backend/tests/test_runs.py",
                    "name_prefix": "test_",
                    "min_count": 3,
                },
                severity="error",
                description="suite defines at least three test functions",
            )
        ]
        result = await h._validate_output(
            _inputs(criteria), [_art("backend/tests/test_runs.py", _VALID_TEST)]
        )
        assert result.passed is False
        row = next(c for c in result.checks if c["check"] == "acceptance:function_defined")
        assert row["status"] == "failed"
        assert "Typed checks failed" in result.summary

    async def test_authored_check_pass_keeps_validation_green(self):
        h = QATestHandler()
        criteria = [
            TypedCheck(
                check="function_defined",
                params={"file": "backend/tests/test_runs.py", "name_prefix": "test_"},
                severity="error",
                description="suite defines test functions",
            )
        ]
        result = await h._validate_output(
            _inputs(criteria), [_art("backend/tests/test_runs.py", _VALID_TEST)]
        )
        assert result.passed is True

    async def test_sip0100_harness_boundary_binding_is_real(self):
        # the SIP-0100 scaffold binds harness_boundary onto qa.test slots;
        # until #670 those bound checks evaluated nowhere
        h = QATestHandler()
        criteria = [
            TypedCheck(
                check="harness_boundary",
                params={
                    "file": "backend/tests/test_direct.py",
                    "entry_modules": ["app.main", "main"],
                },
                severity="error",
                description="suite consumes the scaffold client fixture",
            )
        ]
        result = await h._validate_output(
            _inputs(criteria, expected=("backend/tests/test_direct.py",)),
            [_art("backend/tests/test_direct.py", _BOUNDARY_VIOLATION_TEST)],
        )
        assert result.passed is False
        row = next(c for c in result.checks if c["check"] == "acceptance:harness_boundary")
        assert row["status"] == "failed"


class TestFrameworkInjectionReachesQa:
    async def test_undefined_names_injected_on_py_emission(self):
        # the shk-3 exhibit inverted: zero authored criteria, yet the .py
        # emission with a call-time NameError is caught at acceptance
        h = QATestHandler()
        result = await h._validate_output(
            _inputs(), [_art("backend/tests/test_runs.py", _NAMEERROR_TEST)]
        )
        row = next((c for c in result.checks if c["check"] == "acceptance:undefined_names"), None)
        assert row is not None, "framework injection never reached the qa emission"
        assert row["status"] == "failed"
        assert result.passed is False

    async def test_a_js_suite_gets_the_js_check_and_out_of_language_files_none(self):
        """#605's property, restated for #939: a `.js` suite is never fed the Python
        analyser — it gets the JS one, which skips honestly where tsc is absent and
        passes a suite whose names are all imported — and a file in no emission
        language (a JSON fixture) gets no row at all. Either way the task passes."""
        import shutil

        h = QATestHandler()
        result = await h._validate_output(
            _inputs(expected=("frontend/tests/app.test.js",)),
            [
                _art(
                    "frontend/tests/app.test.js",
                    "import { test } from 'vitest'\ntest('x', () => {})\n",
                ),
                _art("frontend/tests/fixture.json", "{}"),
            ],
        )
        rows = {
            c["params"]["file"]: c
            for c in result.checks
            if c["check"] == "acceptance:undefined_names"
        }
        assert set(rows) == {"frontend/tests/app.test.js"}
        row = rows["frontend/tests/app.test.js"]
        if shutil.which("tsc") is None:
            assert row["status"] == "skipped"
            assert row["actual"]["missing_module"] == "tsc"
        else:
            assert row["status"] == "passed"
        assert result.passed is True


class TestEvidenceGapParityWithDev:
    async def test_evaluator_gap_does_not_fail_the_task(self):
        # #423 on the qa surface: an authored error check the evaluator cannot
        # run is an honest non-pass that blocks at the roll-up, not here
        h = QATestHandler()
        criteria = [
            TypedCheck(
                check="import_present",
                params={"file": "frontend/tests/app.test.tsx", "module": "vitest"},
                severity="error",
                description="suite imports the harness",
            )
        ]
        result = await h._validate_output(
            _inputs(criteria, expected=("frontend/tests/app.test.tsx",)),
            [_art("frontend/tests/app.test.tsx", "import {test} from 'vitest'")],
        )
        row = next(c for c in result.checks if c["check"] == "acceptance:import_present")
        assert row["evidence_gap"] is True
        assert row["passed"] is False
        assert result.passed is True  # the gap blocks at SIP-0096, not the task
