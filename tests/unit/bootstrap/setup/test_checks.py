"""Doctor check function tests (SIP-0081).

Each test answers: "What bug would this catch?"
"""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

from squadops.bootstrap.setup.checks import (
    CheckResult,
    check_auth_token,
    check_docker_service,
    check_nvidia_gpu,
    check_ollama_model_alternative,
    check_ollama_model_exact,
    check_platform,
    check_python_version,
    check_system_dep,
    check_venv_exists,
    run_checks,
)
from squadops.bootstrap.setup.profile import (
    BootstrapProfile,
    DockerService,
    OllamaModelAlternative,
    OllamaModelExact,
    PlatformSpec,
    PythonSpec,
    SystemDep,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile(
    *,
    os: str = "darwin",
    min_version: str | None = None,
    distro: str | None = None,
    distro_min_version: str | None = None,
    python_version: str = "3.11",
    python_manager: str = "pyenv",
    system_deps: list | None = None,
    docker_services: list | None = None,
    ollama_models: list | None = None,
) -> BootstrapProfile:
    return BootstrapProfile(
        schema_version=1,
        name="test",
        description="test profile",
        platform=PlatformSpec(
            os=os,
            min_version=min_version,
            distro=distro,
            distro_min_version=distro_min_version,
        ),
        python=PythonSpec(version=python_version, manager=python_manager),
        system_deps=system_deps or [],
        docker_services=docker_services or [],
        ollama_models=ollama_models or [],
    )


# ---------------------------------------------------------------------------
# Python version checks
# ---------------------------------------------------------------------------


class TestPythonVersion:
    def test_pass(self):
        """Correct version detected — prevents false negatives."""
        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        profile = _profile(python_version=version)
        result = check_python_version(profile)
        assert result.passed is True
        assert result.category == "python"
        assert version in result.message

    def test_pass_higher_version(self):
        """Running a higher Python than the minimum still passes."""
        # Use a version lower than current to verify >= semantics
        profile = _profile(python_version="3.10")
        result = check_python_version(profile)
        assert result.passed is True

    def test_fail(self):
        """Version below minimum returns failure with fix command."""
        profile = _profile(python_version="99.0")
        result = check_python_version(profile)
        assert result.passed is False
        assert "99.0" in result.message
        assert result.fix_command is not None

    def test_fail_pyenv_fix(self):
        """pyenv manager provides specific fix command."""
        profile = _profile(python_version="99.0", python_manager="pyenv")
        result = check_python_version(profile)
        assert "pyenv install" in result.fix_command

    def test_fail_system_fix(self):
        """system manager provides generic fix message."""
        profile = _profile(python_version="99.0", python_manager="system")
        result = check_python_version(profile)
        assert "system package manager" in result.fix_command


# ---------------------------------------------------------------------------
# Venv checks
# ---------------------------------------------------------------------------


class TestVenvExists:
    def test_venv_present(self, tmp_path, monkeypatch):
        """Pass when .venv exists with squadops installed."""
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        pip_bin = venv_dir / "bin"
        pip_bin.mkdir()
        pip_exe = pip_bin / "pip"
        pip_exe.write_text("#!/bin/sh\n")
        pip_exe.chmod(0o755)
        monkeypatch.chdir(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = check_venv_exists(_profile())
        assert result.passed is True

    def test_venv_missing(self, tmp_path, monkeypatch):
        """.venv missing returns failure with creation command."""
        monkeypatch.chdir(tmp_path)
        result = check_venv_exists(_profile())
        assert result.passed is False
        assert ".venv" in result.message
        assert result.fix_command is not None
        assert "venv" in result.fix_command

    def test_venv_required_for_system_python(self, tmp_path, monkeypatch):
        """.venv check runs even for manager: system profiles (R4)."""
        monkeypatch.chdir(tmp_path)
        profile = _profile(python_manager="system")
        result = check_venv_exists(profile)
        assert result.passed is False  # No .venv exists

    def test_venv_exists_but_squadops_not_installed(self, tmp_path, monkeypatch):
        """Catches missing editable install inside existing venv."""
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        pip_bin = venv_dir / "bin"
        pip_bin.mkdir()
        pip_exe = pip_bin / "pip"
        pip_exe.write_text("#!/bin/sh\n")
        pip_exe.chmod(0o755)
        monkeypatch.chdir(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)  # pip show fails
            result = check_venv_exists(profile=_profile())
        assert result.passed is False
        assert "not installed" in result.message


# ---------------------------------------------------------------------------
# Platform checks
# ---------------------------------------------------------------------------


class TestPlatform:
    def test_darwin_pass(self, monkeypatch):
        """macOS detected correctly when profile expects darwin."""
        monkeypatch.setattr(sys, "platform", "darwin")
        profile = _profile(os="darwin")
        result = check_platform(profile)
        assert result.passed is True

    def test_wrong_os(self, monkeypatch):
        """Wrong OS detected and reported with fix guidance."""
        monkeypatch.setattr(sys, "platform", "linux")
        profile = _profile(os="darwin")
        result = check_platform(profile)
        assert result.passed is False
        assert "darwin" in result.message

    @patch("squadops.bootstrap.setup.checks.platform")
    def test_darwin_version_too_low(self, mock_platform, monkeypatch):
        """macOS version below minimum is caught."""
        monkeypatch.setattr(sys, "platform", "darwin")
        mock_platform.mac_ver.return_value = ("13.0", ("", "", ""), "")
        profile = _profile(os="darwin", min_version="14.0")
        result = check_platform(profile)
        assert result.passed is False
        assert "13.0" in result.message

    def test_linux_distro_mismatch(self, monkeypatch):
        """Wrong distro detected and reported."""
        monkeypatch.setattr(sys, "platform", "linux")
        with patch(
            "squadops.bootstrap.setup.checks._detect_linux_distro",
            return_value=("fedora", "39"),
        ):
            profile = _profile(os="linux", distro="ubuntu")
            result = check_platform(profile)
        assert result.passed is False
        assert "ubuntu" in result.message
        assert "fedora" in result.message

    def test_linux_distro_version_too_low(self, monkeypatch):
        """Distro version below minimum is caught."""
        monkeypatch.setattr(sys, "platform", "linux")
        with patch(
            "squadops.bootstrap.setup.checks._detect_linux_distro",
            return_value=("ubuntu", "20.04"),
        ):
            profile = _profile(os="linux", distro="ubuntu", distro_min_version="22.04")
            result = check_platform(profile)
        assert result.passed is False
        assert "20.04" in result.message


# ---------------------------------------------------------------------------
# System dependency checks
# ---------------------------------------------------------------------------


class TestSystemDep:
    def test_found(self):
        """check command exits 0 -> pass."""
        dep = SystemDep(name="git", install="brew", check="git --version", package="git")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with patch("shutil.which", return_value="/usr/bin/git"):
                result = check_system_dep(dep)
        assert result.passed is True
        assert result.category == "tools"

    def test_missing_brew(self):
        """Missing brew dep returns brew install command as fix."""
        dep = SystemDep(name="ollama", install="brew", check="ollama --version", package="ollama")
        with patch("shutil.which", return_value=None):
            result = check_system_dep(dep)
        assert result.passed is False
        assert result.fix_command == "brew install ollama"
        assert result.auto_fixable is True

    def test_missing_apt(self):
        """Missing apt dep returns apt install command as fix."""
        dep = SystemDep(name="curl", install="apt", check="curl --version", package="curl")
        with patch("shutil.which", return_value=None):
            result = check_system_dep(dep)
        assert result.passed is False
        assert result.fix_command == "sudo apt install curl"

    def test_missing_cask(self):
        """Missing cask dep uses --cask flag in fix."""
        dep = SystemDep(
            name="docker",
            install="brew",
            check="docker --version",
            package="docker",
            cask=True,
        )
        with patch("shutil.which", return_value=None):
            result = check_system_dep(dep)
        assert result.fix_command == "brew install --cask docker"

    def test_no_check_command(self):
        """Dep with install: none and no check command is skipped."""
        dep = SystemDep(name="nvidia-smi", install="none")
        result = check_system_dep(dep)
        assert result.passed is True
        assert "skipped" in result.message

    def test_timeout(self):
        """Check command timeout returns failure."""
        dep = SystemDep(name="slow", install="manual", check="sleep 999")
        with patch("shutil.which", return_value="/usr/bin/sleep"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("sleep", 10)):
                result = check_system_dep(dep)
        assert result.passed is False
        assert "timed out" in result.message


# ---------------------------------------------------------------------------
# Docker service checks
# ---------------------------------------------------------------------------


class TestDockerService:
    def test_http_healthy(self):
        """HTTP endpoint returns 200 -> pass."""
        svc = DockerService(
            name="runtime-api",
            healthcheck="http",
            endpoint="http://localhost:8001/health",
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = lambda s: mock_resp
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = check_docker_service(svc)
        assert result.passed is True
        assert result.category == "docker"

    def test_http_down(self):
        """HTTP endpoint unreachable -> fail with endpoint in message."""
        svc = DockerService(
            name="runtime-api",
            healthcheck="http",
            endpoint="http://localhost:8001/health",
        )
        with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("refused")):
            result = check_docker_service(svc)
        assert result.passed is False
        assert "8001" in result.message or "runtime-api" in result.message
        assert result.fix_command is not None

    def test_tcp_healthy(self):
        """TCP port open -> pass."""
        svc = DockerService(name="postgres", healthcheck="tcp", port=5432)
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_socket.return_value = mock_sock
            result = check_docker_service(svc)
        assert result.passed is True
        assert "5432" in result.message

    def test_tcp_down(self):
        """TCP port closed -> fail with port in message."""
        svc = DockerService(name="postgres", healthcheck="tcp", port=5432)
        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 111  # Connection refused
            mock_socket.return_value = mock_sock
            result = check_docker_service(svc)
        assert result.passed is False
        assert "5432" in result.message
        assert result.fix_command is not None

    def test_docker_health_healthy(self):
        """docker inspect shows healthy -> pass."""
        svc = DockerService(name="redis", healthcheck="docker_health")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="healthy\n", returncode=0)
            result = check_docker_service(svc)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Ollama model checks
# ---------------------------------------------------------------------------


class TestOllamaModels:
    def test_exact_model_present(self):
        """Model in installed set -> pass."""
        model = OllamaModelExact(name="qwen2.5:7b")
        result = check_ollama_model_exact(model, {"qwen2.5:7b", "llama3:8b"})
        assert result.passed is True

    def test_exact_model_missing(self):
        """Model absent -> fail with pull command as fix."""
        model = OllamaModelExact(name="qwen2.5:7b")
        result = check_ollama_model_exact(model, set())
        assert result.passed is False
        assert result.fix_command == "ollama pull qwen2.5:7b"

    def test_exact_model_optional_missing(self):
        """Optional model missing -> still passes."""
        model = OllamaModelExact(name="qwen2.5:7b", required=False)
        result = check_ollama_model_exact(model, set())
        assert result.passed is True
        assert "optional" in result.message

    def test_alternative_one_present(self):
        """One of required_one_of found -> pass (R9)."""
        model = OllamaModelAlternative(required_one_of=["qwen2.5:72b", "qwen2.5:32b"], tier="large")
        result = check_ollama_model_alternative(model, {"qwen2.5:72b"})
        assert result.passed is True
        assert "large" in result.message

    def test_alternative_none_present(self):
        """None found -> fail listing alternatives + tier (R9)."""
        model = OllamaModelAlternative(required_one_of=["qwen2.5:72b", "qwen2.5:32b"], tier="large")
        result = check_ollama_model_alternative(model, set())
        assert result.passed is False
        assert "large" in result.message
        assert "qwen2.5:72b" in result.message
        assert result.fix_command == "ollama pull qwen2.5:72b"


# ---------------------------------------------------------------------------
# GPU checks (R10)
# ---------------------------------------------------------------------------


class TestGpuChecks:
    def test_nvidia_smi_missing_hard_fail(self):
        """nvidia-smi not found -> hard fail, heuristic=False (R10)."""
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run") as mock_run:
                # ollama ps for heuristic
                mock_run.return_value = MagicMock(returncode=1, stdout="")
                results = check_nvidia_gpu()
        smi_result = next(r for r in results if r.name == "gpu:nvidia-smi")
        assert smi_result.passed is False
        assert smi_result.heuristic is False

    def test_ollama_gpu_access_heuristic(self):
        """GPU layer check is heuristic-only, does not count as hard failure (R10)."""
        with patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
            with patch("subprocess.run") as mock_run:
                # nvidia-smi succeeds, ollama ps no GPU
                mock_run.side_effect = [
                    MagicMock(returncode=0),  # nvidia-smi
                    MagicMock(returncode=0, stdout="NAME\tSIZE\n"),  # ollama ps
                ]
                results = check_nvidia_gpu()
        ollama_result = next(r for r in results if r.name == "gpu:ollama-access")
        assert ollama_result.heuristic is True


# ---------------------------------------------------------------------------
# Auth check
# ---------------------------------------------------------------------------


class TestAuthToken:
    def test_no_token(self):
        """Missing token file -> fail with login command."""
        with patch("squadops.cli.auth.load_cached_token", return_value=None):
            result = check_auth_token()
        assert result.passed is False
        assert "squadops login" in result.fix_command

    def test_expired_token(self):
        """Expired token -> fail."""
        mock_token = MagicMock()
        with patch("squadops.cli.auth.load_cached_token", return_value=mock_token):
            with patch("squadops.cli.auth.is_expired", return_value=True):
                result = check_auth_token()
        assert result.passed is False
        assert "expired" in result.message

    def test_valid_token(self):
        """Valid token -> pass with remaining time."""
        import time

        mock_token = MagicMock()
        mock_token.expires_at = time.time() + 3600
        with patch("squadops.cli.auth.load_cached_token", return_value=mock_token):
            with patch("squadops.cli.auth.is_expired", return_value=False):
                result = check_auth_token()
        assert result.passed is True
        assert "remaining" in result.message


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class TestRunChecks:
    def test_skips_gpu_for_non_spark(self):
        """dev-mac profile doesn't run GPU checks (no nvidia deps)."""
        profile = _profile(
            system_deps=[
                SystemDep(name="git", install="brew", check="git --version", package="git"),
            ]
        )
        with (
            patch("squadops.bootstrap.setup.checks.check_python_version") as mock_py,
            patch("squadops.bootstrap.setup.checks.check_venv_exists") as mock_venv,
            patch("squadops.bootstrap.setup.checks.check_platform") as mock_plat,
            patch("squadops.bootstrap.setup.checks.check_system_dep") as mock_dep,
            patch("squadops.bootstrap.setup.checks.check_nvidia_gpu") as mock_gpu,
            patch("squadops.bootstrap.setup.checks.check_auth_token") as mock_auth,
        ):
            mock_py.return_value = CheckResult("py", "python", True, "ok")
            mock_venv.return_value = CheckResult("venv", "python", True, "ok")
            mock_plat.return_value = CheckResult("plat", "platform", True, "ok")
            mock_dep.return_value = CheckResult("dep", "tools", True, "ok")
            mock_auth.return_value = CheckResult("auth", "auth", True, "ok")
            run_checks(profile)
            mock_gpu.assert_not_called()

    def test_runs_gpu_for_nvidia_profile(self):
        """Profile with nvidia deps triggers GPU checks."""
        profile = _profile(
            system_deps=[
                SystemDep(name="nvidia-smi", install="none", check="nvidia-smi"),
            ]
        )
        with (
            patch("squadops.bootstrap.setup.checks.check_python_version") as mock_py,
            patch("squadops.bootstrap.setup.checks.check_venv_exists") as mock_venv,
            patch("squadops.bootstrap.setup.checks.check_platform") as mock_plat,
            patch("squadops.bootstrap.setup.checks.check_system_dep") as mock_dep,
            patch("squadops.bootstrap.setup.checks.check_nvidia_gpu") as mock_gpu,
            patch("squadops.bootstrap.setup.checks.check_auth_token") as mock_auth,
        ):
            mock_py.return_value = CheckResult("py", "python", True, "ok")
            mock_venv.return_value = CheckResult("venv", "python", True, "ok")
            mock_plat.return_value = CheckResult("plat", "platform", True, "ok")
            mock_dep.return_value = CheckResult("dep", "tools", True, "ok")
            mock_gpu.return_value = [CheckResult("gpu", "gpu", True, "ok")]
            mock_auth.return_value = CheckResult("auth", "auth", True, "ok")
            run_checks(profile)
            mock_gpu.assert_called_once()

    def test_category_filter(self):
        """--check category filters to only that category."""
        profile = _profile()
        with (
            patch("squadops.bootstrap.setup.checks.check_python_version") as mock_py,
            patch("squadops.bootstrap.setup.checks.check_venv_exists") as mock_venv,
            patch("squadops.bootstrap.setup.checks.check_platform") as mock_plat,
            patch("squadops.bootstrap.setup.checks.check_auth_token") as mock_auth,
        ):
            mock_py.return_value = CheckResult("py", "python", True, "ok")
            mock_venv.return_value = CheckResult("venv", "python", True, "ok")
            results = run_checks(profile, category="python")
            mock_plat.assert_not_called()
            mock_auth.assert_not_called()
            assert len(results) == 2

    def test_fix_command_present_on_failures(self):
        """Every hard failure has a non-None fix_command."""
        # Use real check functions with mocked externals
        dep = SystemDep(name="missing", install="brew", check="missing_tool", package="missing")
        with patch("shutil.which", return_value=None):
            result = check_system_dep(dep)
        assert result.passed is False
        assert result.fix_command is not None
