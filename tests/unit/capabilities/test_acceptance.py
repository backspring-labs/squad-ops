"""
Unit tests for the acceptance check engine.

Tests:
- Template resolution
- Path security (chroot enforcement, symlink escape, '..' handling)
- v1 check types: file_exists, non_empty, json_field_equals
- Strict type comparison for json_field_equals
"""

import json
import os

import pytest

from squadops.capabilities.acceptance import AcceptanceCheckEngine
from squadops.capabilities.exceptions import (
    PathEscapeError,
    TemplateResolutionError,
)
from squadops.capabilities.models import (
    AcceptanceCheck,
    AcceptanceContext,
    CheckType,
)


@pytest.fixture
def temp_chroot(tmp_path):
    """Create a temporary chroot directory."""
    chroot = tmp_path / "chroot"
    chroot.mkdir()
    return chroot


@pytest.fixture
def engine(temp_chroot):
    """Create an AcceptanceCheckEngine with temp chroot."""
    return AcceptanceCheckEngine(temp_chroot)


@pytest.fixture
def basic_context(temp_chroot):
    """Create a basic AcceptanceContext."""
    return AcceptanceContext(
        run_root=str(temp_chroot),
        cycle_id="cycle-123",
        workload_id="test_workload",
        task_outputs=(("task1", {"path": "output/file.json", "count": 42}),),
        vars=(
            ("env", "test"),
            ("version", "1.0"),
        ),
    )


class TestTemplateResolution:
    """Tests for template variable resolution."""

    def test_resolve_cycle_id(self, engine, basic_context):
        """Resolves {cycle_id} variable."""
        result = engine.resolve_template("runs/{cycle_id}/output", basic_context)
        assert result == "runs/cycle-123/output"

    def test_resolve_workload_id(self, engine, basic_context):
        """Resolves {workload_id} variable."""
        result = engine.resolve_template("{workload_id}/data", basic_context)
        assert result == "test_workload/data"

    def test_resolve_run_root(self, engine, basic_context, temp_chroot):
        """Resolves {run_root} variable."""
        result = engine.resolve_template("{run_root}/file", basic_context)
        assert result == f"{temp_chroot}/file"

    def test_resolve_vars(self, engine, basic_context):
        """Resolves {vars.name} variables."""
        result = engine.resolve_template("env-{vars.env}-v{vars.version}", basic_context)
        assert result == "env-test-v1.0"

    def test_resolve_task_output(self, engine, basic_context):
        """Resolves {task_id.output_name} variables."""
        result = engine.resolve_template("{task1.path}", basic_context)
        assert result == "output/file.json"

        result = engine.resolve_template("count={task1.count}", basic_context)
        assert result == "count=42"

    def test_resolve_multiple_variables(self, engine, basic_context):
        """Resolves multiple variables in one template."""
        result = engine.resolve_template(
            "runs/{cycle_id}/{vars.env}/{task1.path}",
            basic_context,
        )
        assert result == "runs/cycle-123/test/output/file.json"

    def test_unknown_variable_raises(self, engine, basic_context):
        """Unknown variable raises TemplateResolutionError."""
        with pytest.raises(TemplateResolutionError) as exc:
            engine.resolve_template("{unknown_var}", basic_context)
        assert "unknown_var" in str(exc.value)

    def test_unknown_vars_variable_raises(self, engine, basic_context):
        """Unknown vars.name raises TemplateResolutionError."""
        with pytest.raises(TemplateResolutionError) as exc:
            engine.resolve_template("{vars.missing}", basic_context)
        assert "vars.missing" in str(exc.value)

    def test_unknown_task_output_raises(self, engine, basic_context):
        """Unknown task output raises TemplateResolutionError."""
        with pytest.raises(TemplateResolutionError) as exc:
            engine.resolve_template("{task1.missing}", basic_context)
        assert "task1.missing" in str(exc.value)

    def test_resolve_run_id(self, engine, temp_chroot):
        """Resolves {run_id} variable (SIP-0070, Phase 1.2)."""
        context = AcceptanceContext(
            run_root=str(temp_chroot),
            cycle_id="cycle-123",
            workload_id="wl",
            run_id="run-456",
        )
        result = engine.resolve_template("runs/{run_id}/output", context)
        assert result == "runs/run-456/output"

    def test_resolve_run_id_empty_default(self, engine, basic_context):
        """run_id defaults to empty string."""
        result = engine.resolve_template("prefix-{run_id}-suffix", basic_context)
        assert result == "prefix--suffix"

    def test_resolve_run_id_with_other_vars(self, engine, temp_chroot):
        """run_id resolves alongside other variables."""
        context = AcceptanceContext(
            run_root=str(temp_chroot),
            cycle_id="cyc-1",
            workload_id="wl-1",
            run_id="run-1",
        )
        result = engine.resolve_template("{cycle_id}/{run_id}/{workload_id}", context)
        assert result == "cyc-1/run-1/wl-1"


class TestPathSecurity:
    """Tests for path security / chroot enforcement."""

    def test_valid_path_within_chroot(self, engine, basic_context, temp_chroot):
        """Valid paths within chroot are accepted."""
        # Create the target file
        target = temp_chroot / "data" / "file.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("content")

        path = engine.validate_and_resolve_path("data/file.txt", basic_context)
        assert path == target

    def test_dotdot_as_segment_raises(self, engine, basic_context):
        """'..' as a path segment raises PathEscapeError."""
        with pytest.raises(PathEscapeError) as exc:
            engine.validate_and_resolve_path("data/../../../etc/passwd", basic_context)
        assert ".." in str(exc.value) or "escape" in str(exc.value).lower()

    def test_dotdot_at_start_raises(self, engine, basic_context):
        """'..' at the start of path raises PathEscapeError."""
        with pytest.raises(PathEscapeError):
            engine.validate_and_resolve_path("../outside", basic_context)

    def test_dotdot_as_substring_allowed(self, engine, basic_context, temp_chroot):
        """'..' as substring in filename is allowed."""
        # Create file with '..' in name
        target = temp_chroot / "file..name.txt"
        target.write_text("content")

        # This should NOT raise
        path = engine.validate_and_resolve_path("file..name.txt", basic_context)
        assert path == target

    def test_dotdot_in_directory_name_allowed(self, engine, basic_context, temp_chroot):
        """'..' as substring in directory name is allowed."""
        # Create directory with '..' in name
        target_dir = temp_chroot / "data..v2"
        target_dir.mkdir()
        target = target_dir / "file.txt"
        target.write_text("content")

        path = engine.validate_and_resolve_path("data..v2/file.txt", basic_context)
        assert path == target

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks may require admin on Windows")
    def test_symlink_escape_raises(self, engine, basic_context, temp_chroot, tmp_path):
        """Symlink pointing outside chroot raises PathEscapeError."""
        # Create a target outside chroot
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("secret data")

        # Create symlink inside chroot pointing outside
        link = temp_chroot / "escape_link"
        link.symlink_to(outside)

        with pytest.raises(PathEscapeError):
            engine.validate_and_resolve_path("escape_link/secret.txt", basic_context)

    def test_resolved_path_outside_chroot_raises(self, engine, basic_context):
        """Paths that resolve outside chroot raise PathEscapeError."""
        # Use enough '..' to escape
        with pytest.raises(PathEscapeError):
            engine.validate_and_resolve_path("a/b/c/../../../../outside", basic_context)


class TestFileExistsCheck:
    """Tests for file_exists acceptance check."""

    def test_file_exists_pass(self, engine, basic_context, temp_chroot):
        """file_exists passes when file exists."""
        target = temp_chroot / "exists.txt"
        target.write_text("content")

        check = AcceptanceCheck(
            check_type=CheckType.FILE_EXISTS,
            target="exists.txt",
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is True
        assert result.error is None

    def test_file_exists_fail(self, engine, basic_context):
        """file_exists fails when file doesn't exist."""
        check = AcceptanceCheck(
            check_type=CheckType.FILE_EXISTS,
            target="missing.txt",
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is False
        assert "does not exist" in result.error

    def test_file_exists_with_template(self, engine, basic_context, temp_chroot):
        """file_exists resolves templates in target."""
        target = temp_chroot / "runs" / "cycle-123" / "output.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("content")

        check = AcceptanceCheck(
            check_type=CheckType.FILE_EXISTS,
            target="runs/{cycle_id}/output.txt",
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is True


class TestNonEmptyCheck:
    """Tests for non_empty acceptance check."""

    def test_non_empty_pass(self, engine, basic_context, temp_chroot):
        """non_empty passes when file exists and has content."""
        target = temp_chroot / "nonempty.txt"
        target.write_text("content")

        check = AcceptanceCheck(
            check_type=CheckType.NON_EMPTY,
            target="nonempty.txt",
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is True

    def test_non_empty_fail_missing(self, engine, basic_context):
        """non_empty fails when file doesn't exist."""
        check = AcceptanceCheck(
            check_type=CheckType.NON_EMPTY,
            target="missing.txt",
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is False
        assert "does not exist" in result.error

    def test_non_empty_fail_empty(self, engine, basic_context, temp_chroot):
        """non_empty fails when file is empty."""
        target = temp_chroot / "empty.txt"
        target.write_text("")

        check = AcceptanceCheck(
            check_type=CheckType.NON_EMPTY,
            target="empty.txt",
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is False
        assert "empty" in result.error.lower()


class TestJsonFieldEqualsCheck:
    """Tests for json_field_equals acceptance check with strict typing."""

    def test_json_field_equals_string_pass(self, engine, basic_context, temp_chroot):
        """json_field_equals passes for matching string value."""
        target = temp_chroot / "data.json"
        target.write_text(json.dumps({"status": "success"}))

        check = AcceptanceCheck(
            check_type=CheckType.JSON_FIELD_EQUALS,
            target="data.json",
            field_path="status",
            expected_value="success",
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is True
        assert result.actual_value == "success"

    def test_json_field_equals_number_pass(self, engine, basic_context, temp_chroot):
        """json_field_equals passes for matching number value."""
        target = temp_chroot / "data.json"
        target.write_text(json.dumps({"count": 42}))

        check = AcceptanceCheck(
            check_type=CheckType.JSON_FIELD_EQUALS,
            target="data.json",
            field_path="count",
            expected_value=42,
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is True

    def test_json_field_equals_boolean_pass(self, engine, basic_context, temp_chroot):
        """json_field_equals passes for matching boolean value."""
        target = temp_chroot / "data.json"
        target.write_text(json.dumps({"enabled": True}))

        check = AcceptanceCheck(
            check_type=CheckType.JSON_FIELD_EQUALS,
            target="data.json",
            field_path="enabled",
            expected_value=True,
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is True

    def test_json_field_equals_nested_path(self, engine, basic_context, temp_chroot):
        """json_field_equals navigates nested paths."""
        target = temp_chroot / "data.json"
        target.write_text(
            json.dumps(
                {
                    "metadata": {
                        "status": "completed",
                        "details": {
                            "code": 200,
                        },
                    }
                }
            )
        )

        check = AcceptanceCheck(
            check_type=CheckType.JSON_FIELD_EQUALS,
            target="data.json",
            field_path="metadata.status",
            expected_value="completed",
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is True

        check2 = AcceptanceCheck(
            check_type=CheckType.JSON_FIELD_EQUALS,
            target="data.json",
            field_path="metadata.details.code",
            expected_value=200,
        )
        result2 = engine.evaluate(check2, basic_context)
        assert result2.passed is True

    def test_json_field_equals_strict_type_int_vs_float(self, engine, basic_context, temp_chroot):
        """json_field_equals strict type: int != float."""
        target = temp_chroot / "data.json"
        # JSON doesn't distinguish int/float, but Python does after loading
        target.write_text(json.dumps({"value": 1}))

        # Expecting float 1.0, actual is int 1
        check = AcceptanceCheck(
            check_type=CheckType.JSON_FIELD_EQUALS,
            target="data.json",
            field_path="value",
            expected_value=1.0,
        )
        result = engine.evaluate(check, basic_context)
        # Note: json.loads produces int for 1, so this should fail
        # But JSON treats 1 and 1.0 the same; after loading, Python has int
        # So int(1) != float(1.0) in strict comparison
        assert result.passed is False
        assert "Type mismatch" in result.error

    def test_json_field_equals_strict_type_string_vs_number(
        self, engine, basic_context, temp_chroot
    ):
        """json_field_equals strict type: string '1' != number 1."""
        target = temp_chroot / "data.json"
        target.write_text(json.dumps({"value": "1"}))

        check = AcceptanceCheck(
            check_type=CheckType.JSON_FIELD_EQUALS,
            target="data.json",
            field_path="value",
            expected_value=1,
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is False
        assert "Type mismatch" in result.error

    def test_json_field_equals_strict_type_string_vs_boolean(
        self, engine, basic_context, temp_chroot
    ):
        """json_field_equals strict type: string 'true' != boolean True."""
        target = temp_chroot / "data.json"
        target.write_text(json.dumps({"value": "true"}))

        check = AcceptanceCheck(
            check_type=CheckType.JSON_FIELD_EQUALS,
            target="data.json",
            field_path="value",
            expected_value=True,
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is False
        assert "Type mismatch" in result.error

    def test_json_field_equals_missing_field(self, engine, basic_context, temp_chroot):
        """json_field_equals fails for missing field."""
        target = temp_chroot / "data.json"
        target.write_text(json.dumps({"other": "value"}))

        check = AcceptanceCheck(
            check_type=CheckType.JSON_FIELD_EQUALS,
            target="data.json",
            field_path="status",
            expected_value="success",
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is False
        assert "not found" in result.error.lower()

    def test_json_field_equals_invalid_json(self, engine, basic_context, temp_chroot):
        """json_field_equals fails for invalid JSON."""
        target = temp_chroot / "bad.json"
        target.write_text("not valid json {")

        check = AcceptanceCheck(
            check_type=CheckType.JSON_FIELD_EQUALS,
            target="bad.json",
            field_path="status",
            expected_value="success",
        )
        result = engine.evaluate(check, basic_context)
        assert result.passed is False
        assert "Invalid JSON" in result.error


class TestEvaluateAll:
    """Tests for evaluate_all (no short-circuit behavior)."""

    def test_evaluate_all_no_short_circuit(self, engine, basic_context, temp_chroot):
        """evaluate_all evaluates all checks even if some fail."""
        # Create only one of two expected files
        exists = temp_chroot / "exists.txt"
        exists.write_text("content")

        checks = (
            AcceptanceCheck(
                check_type=CheckType.FILE_EXISTS,
                target="missing1.txt",
            ),
            AcceptanceCheck(
                check_type=CheckType.FILE_EXISTS,
                target="exists.txt",
            ),
            AcceptanceCheck(
                check_type=CheckType.FILE_EXISTS,
                target="missing2.txt",
            ),
        )

        report = engine.evaluate_all(checks, basic_context)

        # All checks should be evaluated
        assert len(report.results) == 3
        assert report.results[0].passed is False
        assert report.results[1].passed is True
        assert report.results[2].passed is False
        assert report.all_passed is False

    def test_evaluate_all_all_pass(self, engine, basic_context, temp_chroot):
        """evaluate_all with all passing checks."""
        f1 = temp_chroot / "file1.txt"
        f2 = temp_chroot / "file2.txt"
        f1.write_text("content1")
        f2.write_text("content2")

        checks = (
            AcceptanceCheck(check_type=CheckType.FILE_EXISTS, target="file1.txt"),
            AcceptanceCheck(check_type=CheckType.NON_EMPTY, target="file2.txt"),
        )

        report = engine.evaluate_all(checks, basic_context)
        assert report.all_passed is True
        assert len(report.results) == 2
