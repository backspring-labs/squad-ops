"""
Doctor CLI command tests (SIP-0081).

Each test answers: "What bug would this catch?"
"""

from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from squadops.bootstrap.setup.checks import CheckResult
from squadops.cli.main import app

runner = CliRunner()


def _make_results(
    *,
    all_pass: bool = True,
    include_heuristic_warning: bool = False,
    include_failure: bool = False,
) -> list[CheckResult]:
    """Build a list of CheckResults for testing."""
    results = [
        CheckResult(name="python_version", category="python", passed=True, message="Python 3.11.14 via pyenv"),
        CheckResult(name="venv_exists", category="python", passed=True, message=".venv present"),
        CheckResult(name="platform", category="platform", passed=True, message="darwin 14.5"),
        CheckResult(name="tool:git", category="tools", passed=True, message="git found"),
    ]
    if include_heuristic_warning:
        results.append(
            CheckResult(
                name="gpu:ollama-access", category="gpu",
                passed=False, message="Ollama GPU access not detected",
                heuristic=True,
            )
        )
    if include_failure:
        results.append(
            CheckResult(
                name="docker:postgres", category="docker",
                passed=False, message="postgres not listening on port 5432",
                fix_command="docker-compose up -d postgres",
                auto_fixable=True,
            )
        )
    return results


class TestDoctorCLI:
    @patch("squadops.cli.commands.doctor.run_checks", return_value=_make_results())
    @patch("squadops.cli.commands.doctor.load_bootstrap_profile")
    def test_all_pass_exit_0(self, mock_load, mock_checks):
        """Exit code 0 when all checks pass."""
        result = runner.invoke(app, ["doctor", "dev-mac"])
        assert result.exit_code == 0

    @patch(
        "squadops.cli.commands.doctor.run_checks",
        return_value=_make_results(include_heuristic_warning=True),
    )
    @patch("squadops.cli.commands.doctor.load_bootstrap_profile")
    def test_heuristic_warning_still_exit_0(self, mock_load, mock_checks):
        """Heuristic-only warnings don't cause exit 1."""
        result = runner.invoke(app, ["doctor", "dev-mac"])
        assert result.exit_code == 0

    @patch(
        "squadops.cli.commands.doctor.run_checks",
        return_value=_make_results(include_failure=True),
    )
    @patch("squadops.cli.commands.doctor.load_bootstrap_profile")
    def test_any_fail_exit_1(self, mock_load, mock_checks):
        """Exit code 1 when any hard check fails."""
        result = runner.invoke(app, ["doctor", "dev-mac"])
        assert result.exit_code == 1

    @patch("squadops.cli.commands.doctor.run_checks", return_value=_make_results())
    @patch("squadops.cli.commands.doctor.load_bootstrap_profile")
    def test_json_output(self, mock_load, mock_checks):
        """--json produces valid JSON with expected schema."""
        result = runner.invoke(app, ["doctor", "dev-mac", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["profile"] == "dev-mac"
        assert "checks" in data
        assert "summary" in data
        assert data["summary"]["total"] == 4
        assert data["summary"]["passed"] == 4
        assert data["summary"]["failed"] == 0

    @patch(
        "squadops.cli.commands.doctor.run_checks",
        return_value=[
            CheckResult(name="python_version", category="python", passed=True, message="ok"),
        ],
    )
    @patch("squadops.cli.commands.doctor.load_bootstrap_profile")
    def test_single_category(self, mock_load, mock_checks):
        """--check filters to one category."""
        result = runner.invoke(app, ["doctor", "dev-mac", "--check", "python"])
        assert result.exit_code == 0
        mock_checks.assert_called_once()
        _, kwargs = mock_checks.call_args
        assert kwargs["category"] == "python"

    def test_unknown_profile(self, tmp_path):
        """Clear error for non-existent profile."""
        from squadops.bootstrap.setup.profile import BootstrapProfileError

        with patch(
            "squadops.cli.commands.doctor.load_bootstrap_profile",
            side_effect=BootstrapProfileError("not found"),
        ):
            result = runner.invoke(app, ["doctor", "nonexistent"])
        assert result.exit_code == 1

    @patch(
        "squadops.cli.commands.doctor.run_checks",
        return_value=_make_results(include_failure=True),
    )
    @patch("squadops.cli.commands.doctor.load_bootstrap_profile")
    def test_failure_shows_fix(self, mock_load, mock_checks):
        """Failed checks include fix guidance in output."""
        result = runner.invoke(app, ["doctor", "dev-mac"])
        assert "docker-compose up -d postgres" in result.output

    @patch(
        "squadops.cli.commands.doctor.run_checks",
        return_value=_make_results(include_heuristic_warning=True),
    )
    @patch("squadops.cli.commands.doctor.load_bootstrap_profile")
    def test_heuristic_marker(self, mock_load, mock_checks):
        """Heuristic warnings use ~ marker in output."""
        result = runner.invoke(app, ["doctor", "dev-mac"])
        assert "~" in result.output
