"""
Bootstrap CLI command tests (SIP-0081).

Each test answers: "What bug would this catch?"
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from squadops.bootstrap.setup.checks import CheckResult
from squadops.cli.main import app

runner = CliRunner()


def _mock_profile():
    """Create a mock BootstrapProfile for testing."""
    profile = MagicMock()
    profile.schema_version = 1
    return profile


def _pass_results():
    return [
        CheckResult(name="python_version", category="python", passed=True, message="ok"),
        CheckResult(name="venv_exists", category="python", passed=True, message="ok"),
    ]


class TestBootstrapCLI:
    @patch("squadops.cli.commands.bootstrap.load_bootstrap_profile")
    def test_unknown_profile_error(self, mock_load):
        """Clear error for non-existent profile before any install."""
        from squadops.bootstrap.setup.profile import BootstrapProfileError

        mock_load.side_effect = BootstrapProfileError("Profile 'bogus' not found")
        result = runner.invoke(app, ["bootstrap", "bogus"])
        assert result.exit_code == 1
        assert "bogus" in result.output or "bogus" in (result.stderr or "")

    @patch("squadops.cli.commands.bootstrap.load_bootstrap_profile")
    def test_loads_profile_before_shell(self, mock_load):
        """Profile validation runs before shell invocation."""
        mock_load.return_value = _mock_profile()
        with patch("squadops.cli.commands.bootstrap._BOOTSTRAP_SCRIPT") as mock_script:
            mock_script.is_file.return_value = False
            mock_script.__str__ = lambda _: "/fake/path"
            result = runner.invoke(app, ["bootstrap", "dev-mac"])
        # Profile was loaded (no BootstrapProfileError)
        mock_load.assert_called_once_with("dev-mac")
        # But script missing → exit 1
        assert result.exit_code == 1

    @patch("squadops.cli.commands.bootstrap.write_state")
    @patch("squadops.cli.commands.bootstrap.run_checks", return_value=_pass_results())
    @patch("subprocess.run")
    @patch("squadops.cli.commands.bootstrap._BOOTSTRAP_SCRIPT")
    @patch("squadops.cli.commands.bootstrap.load_bootstrap_profile")
    def test_dry_run_no_state_written(self, mock_load, mock_script, mock_run, mock_checks, mock_write):
        """--dry-run doesn't write state file."""
        mock_load.return_value = _mock_profile()
        mock_script.is_file.return_value = True
        mock_script.parents.__getitem__ = lambda s, i: MagicMock(parent=MagicMock())
        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(app, ["bootstrap", "dev-mac", "--dry-run"])
        assert result.exit_code == 0
        mock_write.assert_not_called()

    @patch("subprocess.run")
    @patch("squadops.cli.commands.bootstrap._BOOTSTRAP_SCRIPT")
    @patch("squadops.cli.commands.bootstrap.load_bootstrap_profile")
    def test_skip_docker_flag(self, mock_load, mock_script, mock_run):
        """--skip-docker passes through to shell script."""
        mock_load.return_value = _mock_profile()
        mock_script.is_file.return_value = True
        mock_script.__str__ = lambda _: "/fake/bootstrap.sh"
        mock_script.parents.__getitem__ = lambda s, i: MagicMock(parent=MagicMock())
        mock_run.return_value = MagicMock(returncode=0)
        with patch("squadops.cli.commands.bootstrap.run_checks", return_value=_pass_results()):
            with patch("squadops.cli.commands.bootstrap.write_state"):
                runner.invoke(app, ["bootstrap", "dev-mac", "--skip-docker"])
        # First call is the bootstrap.sh invocation
        cmd = mock_run.call_args_list[0][0][0]
        assert "--skip-docker" in cmd

    @patch("subprocess.run")
    @patch("squadops.cli.commands.bootstrap._BOOTSTRAP_SCRIPT")
    @patch("squadops.cli.commands.bootstrap.load_bootstrap_profile")
    def test_skip_models_flag(self, mock_load, mock_script, mock_run):
        """--skip-models passes through to shell script."""
        mock_load.return_value = _mock_profile()
        mock_script.is_file.return_value = True
        mock_script.__str__ = lambda _: "/fake/bootstrap.sh"
        mock_script.parents.__getitem__ = lambda s, i: MagicMock(parent=MagicMock())
        mock_run.return_value = MagicMock(returncode=0)
        with patch("squadops.cli.commands.bootstrap.run_checks", return_value=_pass_results()):
            with patch("squadops.cli.commands.bootstrap.write_state"):
                runner.invoke(app, ["bootstrap", "dev-mac", "--skip-models"])
        # First call is the bootstrap.sh invocation
        cmd = mock_run.call_args_list[0][0][0]
        assert "--skip-models" in cmd

    @patch("squadops.cli.commands.bootstrap.write_state")
    @patch("squadops.cli.commands.bootstrap.run_checks", return_value=_pass_results())
    @patch("subprocess.run")
    @patch("squadops.cli.commands.bootstrap._BOOTSTRAP_SCRIPT")
    @patch("squadops.cli.commands.bootstrap.load_bootstrap_profile")
    def test_writes_state_file(self, mock_load, mock_script, mock_run, mock_checks, mock_write):
        """State file created after successful run (R3)."""
        mock_load.return_value = _mock_profile()
        mock_script.is_file.return_value = True
        mock_script.parents.__getitem__ = lambda s, i: MagicMock(parent=MagicMock())
        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(app, ["bootstrap", "dev-mac"])
        assert result.exit_code == 0
        mock_write.assert_called_once()
        state = mock_write.call_args[0][0]
        assert state.profile == "dev-mac"
        assert state.doctor_summary["total"] == 2
        assert state.doctor_summary["passed"] == 2

    @patch("squadops.cli.commands.bootstrap.run_checks", return_value=_pass_results())
    @patch("subprocess.run")
    @patch("squadops.cli.commands.bootstrap._BOOTSTRAP_SCRIPT")
    @patch("squadops.cli.commands.bootstrap.load_bootstrap_profile")
    def test_runs_doctor_at_end(self, mock_load, mock_script, mock_run, mock_checks):
        """Doctor is invoked as final step after bootstrap."""
        mock_load.return_value = _mock_profile()
        mock_script.is_file.return_value = True
        mock_script.parents.__getitem__ = lambda s, i: MagicMock(parent=MagicMock())
        mock_run.return_value = MagicMock(returncode=0)
        with patch("squadops.cli.commands.bootstrap.write_state"):
            result = runner.invoke(app, ["bootstrap", "dev-mac"])
        assert result.exit_code == 0
        mock_checks.assert_called_once()
        assert "2/2 checks passed" in result.output
