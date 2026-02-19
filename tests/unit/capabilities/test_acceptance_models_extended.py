"""
Unit tests for extended AcceptanceCheck fields and CheckType enum values (SIP-0070 Phase 1.1).

Tests:
- New CheckType enum values (HTTP_STATUS, PROCESS_RUNNING, JSON_SCHEMA, COMMAND_EXIT_CODE)
- AcceptanceCheck __post_init__ validation per check type
- D3 security: cwd relative-only, '..' traversal rejection, env allowlist
"""

import pytest

from squadops.capabilities.models import AcceptanceCheck, CheckType

pytestmark = [pytest.mark.domain_pulse_checks]


class TestCheckTypeEnum:
    """New CheckType enum values exist and are string-valued."""

    def test_http_status_value(self):
        assert CheckType.HTTP_STATUS.value == "http_status"

    def test_process_running_value(self):
        assert CheckType.PROCESS_RUNNING.value == "process_running"

    def test_json_schema_value(self):
        assert CheckType.JSON_SCHEMA.value == "json_schema"

    def test_command_exit_code_value(self):
        assert CheckType.COMMAND_EXIT_CODE.value == "command_exit_code"

    def test_original_values_unchanged(self):
        assert CheckType.FILE_EXISTS.value == "file_exists"
        assert CheckType.NON_EMPTY.value == "non_empty"
        assert CheckType.JSON_FIELD_EQUALS.value == "json_field_equals"


class TestHttpStatusValidation:
    """http_status __post_init__ requires url and expected_status."""

    def test_valid_http_status(self):
        check = AcceptanceCheck(
            check_type=CheckType.HTTP_STATUS,
            target="",
            url="http://localhost:8000/health",
            expected_status=200,
        )
        assert check.url == "http://localhost:8000/health"
        assert check.expected_status == 200

    def test_missing_url_raises(self):
        with pytest.raises(ValueError, match="url"):
            AcceptanceCheck(
                check_type=CheckType.HTTP_STATUS,
                target="",
                expected_status=200,
            )

    def test_missing_expected_status_raises(self):
        with pytest.raises(ValueError, match="expected_status"):
            AcceptanceCheck(
                check_type=CheckType.HTTP_STATUS,
                target="",
                url="http://localhost:8000/health",
            )


class TestProcessRunningValidation:
    """process_running __post_init__ requires container_name."""

    def test_valid_process_running(self):
        check = AcceptanceCheck(
            check_type=CheckType.PROCESS_RUNNING,
            target="",
            container_name="my-container",
        )
        assert check.container_name == "my-container"

    def test_missing_container_name_raises(self):
        with pytest.raises(ValueError, match="container_name"):
            AcceptanceCheck(
                check_type=CheckType.PROCESS_RUNNING,
                target="",
            )


class TestJsonSchemaValidation:
    """json_schema __post_init__ requires target and schema."""

    def test_valid_json_schema(self):
        check = AcceptanceCheck(
            check_type=CheckType.JSON_SCHEMA,
            target="output/report.json",
            schema="schemas/report.schema.json",
        )
        assert check.target == "output/report.json"
        assert check.schema == "schemas/report.schema.json"

    def test_missing_target_raises(self):
        with pytest.raises(ValueError, match="target"):
            AcceptanceCheck(
                check_type=CheckType.JSON_SCHEMA,
                target="",
                schema="schemas/report.schema.json",
            )

    def test_missing_schema_raises(self):
        with pytest.raises(ValueError, match="schema"):
            AcceptanceCheck(
                check_type=CheckType.JSON_SCHEMA,
                target="output/report.json",
            )

    def test_absolute_schema_path_rejected(self):
        with pytest.raises(ValueError, match="relative"):
            AcceptanceCheck(
                check_type=CheckType.JSON_SCHEMA,
                target="output/report.json",
                schema="/etc/schema.json",
            )


class TestCommandExitCodeValidation:
    """command_exit_code __post_init__ validation with D3 security."""

    def test_valid_command(self):
        check = AcceptanceCheck(
            check_type=CheckType.COMMAND_EXIT_CODE,
            target="",
            command=("python", "-c", "print('hello')"),
        )
        assert check.command == ("python", "-c", "print('hello')")
        assert check.expected_exit_code == 0

    def test_empty_command_raises(self):
        with pytest.raises(ValueError, match="non-empty command"):
            AcceptanceCheck(
                check_type=CheckType.COMMAND_EXIT_CODE,
                target="",
                command=(),
            )

    def test_none_command_raises(self):
        with pytest.raises(ValueError, match="non-empty command"):
            AcceptanceCheck(
                check_type=CheckType.COMMAND_EXIT_CODE,
                target="",
            )

    def test_absolute_cwd_rejected(self):
        with pytest.raises(ValueError, match="relative"):
            AcceptanceCheck(
                check_type=CheckType.COMMAND_EXIT_CODE,
                target="",
                command=("ls",),
                cwd="/etc",
            )

    def test_dotdot_traversal_in_cwd_rejected(self):
        with pytest.raises(ValueError, match="\\.\\."):
            AcceptanceCheck(
                check_type=CheckType.COMMAND_EXIT_CODE,
                target="",
                command=("ls",),
                cwd="subdir/../../../etc",
            )

    def test_relative_cwd_accepted(self):
        check = AcceptanceCheck(
            check_type=CheckType.COMMAND_EXIT_CODE,
            target="",
            command=("ls",),
            cwd="subdir/nested",
        )
        assert check.cwd == "subdir/nested"

    def test_env_allowlist(self):
        check = AcceptanceCheck(
            check_type=CheckType.COMMAND_EXIT_CODE,
            target="",
            command=("echo", "test"),
            env=(("MY_VAR", "value"), ("OTHER", "val2")),
        )
        assert check.env == (("MY_VAR", "value"), ("OTHER", "val2"))

    def test_custom_expected_exit_code(self):
        check = AcceptanceCheck(
            check_type=CheckType.COMMAND_EXIT_CODE,
            target="",
            command=("false",),
            expected_exit_code=1,
        )
        assert check.expected_exit_code == 1
