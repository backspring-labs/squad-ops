"""SIP-0092 M1.3 — typed-acceptance integration into _validate_focused.

Covers RC-9 (severity × status blocking matrix), RC-9a (error-vs-failed
wording in missing_components), RC-9b (per-criterion error count with
2-strikes escalation), and RC-12a (skipped-not-error for unset stack).
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.cycle_tasks import DevelopmentDevelopHandler
from squadops.cycles.implementation_plan import TypedCheck

pytestmark = [pytest.mark.domain_capabilities]


def _art(name: str, content: str = "x" * 200) -> dict:
    return {"name": name, "content": content, "media_type": "text/plain", "type": "code"}


def _inputs(criteria, *, expected=("main.py",), focus="Test", config=None):
    return {
        "subtask_focus": focus,
        "expected_artifacts": list(expected),
        "acceptance_criteria": list(criteria),
        "resolved_config": dict(config or {}),
    }


# ---------------------------------------------------------------------------
# Severity × status blocking matrix (RC-9)
# ---------------------------------------------------------------------------


_FASTAPI_ALL = """
from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
def list_users():
    return []
"""

_FASTAPI_MISSING = """
from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
def list_users():
    return []
"""  # missing POST /users


_PROSE_CRITERION = "User CRUD endpoints are present"


class TestSeverityStatusMatrix:
    """RC-9: severity AND status are independent — only error+blocking gates."""

    async def test_severity_error_status_passed_does_not_block(self, tmp_path):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /users"]},
            severity="error",
            description="users endpoint",
        )
        result = await h._validate_output(
            _inputs([criterion], config={"stack": "fastapi"}),
            [_art("main.py", _FASTAPI_ALL)],
        )
        assert result.passed is True
        assert all("acceptance:" not in m for m in result.missing_components)

    async def test_severity_error_status_failed_blocks(self):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /users", "POST /users"]},
            severity="error",
            description="users CRUD",
        )
        result = await h._validate_output(
            _inputs([criterion], config={"stack": "fastapi"}),
            [_art("main.py", _FASTAPI_MISSING)],
        )
        assert result.passed is False
        # RC-9a: app-incompleteness wording, with the description.
        assert "acceptance:users CRUD" in result.missing_components

    async def test_severity_warning_status_failed_does_not_block(self):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /users", "POST /users"]},
            severity="warning",
            description="ideal CRUD",
        )
        result = await h._validate_output(
            _inputs([criterion], config={"stack": "fastapi"}),
            [_art("main.py", _FASTAPI_MISSING)],
        )
        assert result.passed is True
        assert all("acceptance:" not in m for m in result.missing_components)
        # But the failed evaluation appears in checks for evidence visibility.
        typed_checks = [c for c in result.checks if c.get("check") == "acceptance:endpoint_defined"]
        assert len(typed_checks) == 1
        assert typed_checks[0]["status"] == "failed"

    async def test_severity_info_status_failed_does_not_block(self):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="regex_match",
            params={"file": "main.py", "pattern": "totally_absent", "count_min": 1},
            severity="info",
        )
        result = await h._validate_output(
            _inputs([criterion]),
            [_art("main.py", "no match here\n")],
        )
        assert result.passed is True

    async def test_severity_error_status_skipped_does_not_block(self):
        # endpoint_defined requires stack=fastapi; with stack unset the
        # evaluator returns skipped per RC-12a, never an error.
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /x"]},
            severity="error",
        )
        result = await h._validate_output(
            _inputs([criterion]),  # no stack
            [_art("main.py", _FASTAPI_ALL)],
        )
        assert result.passed is True
        typed_checks = [c for c in result.checks if c.get("check") == "acceptance:endpoint_defined"]
        assert typed_checks[0]["status"] == "skipped"
        assert typed_checks[0]["reason"] == "unsupported_stack_or_syntax"


# ---------------------------------------------------------------------------
# RC-9a — error vs failed wording in missing_components
# ---------------------------------------------------------------------------


class TestErrorVsFailedWording:
    async def test_failed_uses_acceptance_prefix(self):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="regex_match",
            params={"file": "main.py", "pattern": "absent_marker", "count_min": 1},
            severity="error",
            description="marker present",
        )
        result = await h._validate_output(
            _inputs([criterion]),
            [_art("main.py", "no match\n")],
        )
        assert "acceptance:marker present" in result.missing_components
        # Sanity: not an evaluator-error.
        assert all(not m.startswith("evaluator-error:") for m in result.missing_components)

    async def test_evaluator_error_uses_evaluator_error_prefix(self):
        # command_exit_zero with argv outside the safelist → status=error.
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="command_exit_zero",
            params={"argv": ["python", "-c", "print(1)"]},
            severity="error",
        )
        result = await h._validate_output(
            _inputs([criterion]),
            [_art("main.py")],
        )
        assert any(
            m.startswith("evaluator-error:command_exit_zero:") for m in result.missing_components
        )
        # Not the app-incompleteness phrasing.
        assert all(not m.startswith("acceptance:") for m in result.missing_components)


# ---------------------------------------------------------------------------
# RC-9b — per-criterion error count + 2-strikes escalation
# ---------------------------------------------------------------------------


class TestPerCriterionErrorEscalation:
    async def test_first_two_errors_surface_third_drops_from_feedback(self):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="command_exit_zero",
            params={"argv": ["python", "-c", "print(1)"]},
            severity="error",
        )
        counts: dict[str, int] = {}
        artifacts = [_art("main.py")]

        # Pass 1 — first error → surfaced in missing_components.
        r1 = await h._validate_output(
            _inputs([criterion]), artifacts, typed_error_counts=counts
        )
        assert any(m.startswith("evaluator-error:") for m in r1.missing_components)

        # Pass 2 — second error → still surfaced.
        r2 = await h._validate_output(
            _inputs([criterion]), artifacts, typed_error_counts=counts
        )
        assert any(m.startswith("evaluator-error:") for m in r2.missing_components)

        # Pass 3 — third error → dropped from feedback (escalated separately).
        r3 = await h._validate_output(
            _inputs([criterion]), artifacts, typed_error_counts=counts
        )
        assert all(not m.startswith("evaluator-error:") for m in r3.missing_components)

        # Counter advanced once per pass.
        assert sum(counts.values()) == 3

    async def test_distinct_criteria_have_distinct_counters(self):
        h = DevelopmentDevelopHandler()
        c1 = TypedCheck(
            check="command_exit_zero",
            params={"argv": ["python", "-c", "1"]},
            severity="error",
        )
        c2 = TypedCheck(
            check="command_exit_zero",
            params={"argv": ["python", "-c", "2"]},
            severity="error",
        )
        counts: dict[str, int] = {}
        artifacts = [_art("main.py")]

        await h._validate_output(_inputs([c1]), artifacts, typed_error_counts=counts)
        await h._validate_output(_inputs([c2]), artifacts, typed_error_counts=counts)
        await h._validate_output(_inputs([c1]), artifacts, typed_error_counts=counts)

        # c1 saw 2 errors; c2 saw 1; total 3.
        assert len(counts) == 2
        assert sum(counts.values()) == 3


# ---------------------------------------------------------------------------
# Config gates
# ---------------------------------------------------------------------------


class TestConfigGates:
    async def test_typed_acceptance_disabled_skips_all_typed(self):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="regex_match",
            params={"file": "main.py", "pattern": "absent", "count_min": 1},
            severity="error",
            description="x",
        )
        result = await h._validate_output(
            _inputs([criterion], config={"typed_acceptance": False}),
            [_art("main.py", "no match")],
        )
        assert result.passed is True
        typed = [c for c in result.checks if c.get("check") == "acceptance:regex_match"]
        assert typed[0]["status"] == "skipped"
        assert typed[0]["reason"] == "typed_acceptance_disabled"

    async def test_command_acceptance_disabled_skips_only_commands(self):
        h = DevelopmentDevelopHandler()
        cmd = TypedCheck(
            check="command_exit_zero",
            params={"argv": ["pyflakes", "main.py"]},
            severity="error",
        )
        regex = TypedCheck(
            check="regex_match",
            params={"file": "main.py", "pattern": "absent", "count_min": 1},
            severity="error",
            description="r",
        )
        result = await h._validate_output(
            _inputs([cmd, regex], config={"command_acceptance_checks": False}),
            [_art("main.py", "no match")],
        )
        cmd_check = [c for c in result.checks if c["check"] == "acceptance:command_exit_zero"][0]
        regex_check = [c for c in result.checks if c["check"] == "acceptance:regex_match"][0]
        assert cmd_check["status"] == "skipped"
        assert cmd_check["reason"] == "command_acceptance_checks_disabled"
        # Regex still evaluates and fails.
        assert regex_check["status"] == "failed"
        assert "acceptance:r" in result.missing_components


# ---------------------------------------------------------------------------
# Prose criteria preserved as informational
# ---------------------------------------------------------------------------


class TestProseCriteriaInformational:
    async def test_prose_strings_never_block(self):
        h = DevelopmentDevelopHandler()
        result = await h._validate_output(
            _inputs([_PROSE_CRITERION]),
            [_art("main.py")],
        )
        assert result.passed is True
        prose_check = [c for c in result.checks if c["check"] == "acceptance_criteria_prose"][0]
        assert prose_check["criteria"] == [_PROSE_CRITERION]
        assert prose_check["evaluation"] == "included_in_evidence"

    async def test_mixed_prose_and_typed_only_typed_can_block(self):
        h = DevelopmentDevelopHandler()
        prose = _PROSE_CRITERION
        typed = TypedCheck(
            check="regex_match",
            params={"file": "main.py", "pattern": "absent", "count_min": 1},
            severity="error",
            description="x",
        )
        result = await h._validate_output(
            _inputs([prose, typed]),
            [_art("main.py", "no match")],
        )
        assert result.passed is False
        # Prose check still recorded as informational.
        prose_check = [c for c in result.checks if c["check"] == "acceptance_criteria_prose"][0]
        assert prose_check["passed"] is True


# ---------------------------------------------------------------------------
# TypedCheck.fingerprint() invariants
# ---------------------------------------------------------------------------


class TestFingerprint:
    def test_same_shape_same_fingerprint(self):
        c1 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"}, severity="error")
        c2 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"}, severity="error")
        assert c1.fingerprint() == c2.fingerprint()

    def test_description_does_not_affect_fingerprint(self):
        c1 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"}, description="one")
        c2 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"}, description="two")
        assert c1.fingerprint() == c2.fingerprint()

    def test_param_change_changes_fingerprint(self):
        c1 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"})
        c2 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "y"})
        assert c1.fingerprint() != c2.fingerprint()

    def test_severity_change_changes_fingerprint(self):
        c1 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"}, severity="error")
        c2 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"}, severity="warning")
        assert c1.fingerprint() != c2.fingerprint()

    def test_param_key_order_does_not_matter(self):
        c1 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"})
        c2 = TypedCheck(check="regex_match", params={"pattern": "x", "file": "a"})
        assert c1.fingerprint() == c2.fingerprint()
