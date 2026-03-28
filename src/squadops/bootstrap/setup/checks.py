"""Bootstrap doctor checks (SIP-0081).

Each check function validates one aspect of the bootstrap profile contract
and returns a CheckResult with pass/fail, fix guidance, and heuristic flag.
"""

from __future__ import annotations

import platform
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from squadops.bootstrap.setup.profile import (
    BootstrapProfile,
    DockerService,
    OllamaModelAlternative,
    OllamaModelExact,
    SystemDep,
)

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

VALID_CATEGORIES = frozenset({"python", "platform", "tools", "docker", "models", "gpu", "auth"})


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single doctor check."""

    name: str
    category: str
    passed: bool
    message: str
    detail: str | None = None
    fix_command: str | None = None
    auto_fixable: bool = False
    heuristic: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Python checks
# ---------------------------------------------------------------------------


def check_python_version(profile: BootstrapProfile) -> CheckResult:
    """Check that the running Python major.minor >= the profile minimum."""
    expected = profile.python.version
    actual = f"{sys.version_info.major}.{sys.version_info.minor}"
    expected_tuple = tuple(int(x) for x in expected.split("."))
    actual_tuple = (sys.version_info.major, sys.version_info.minor)
    if actual_tuple >= expected_tuple:
        manager = profile.python.manager
        return CheckResult(
            name="python_version",
            category="python",
            passed=True,
            message=f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} via {manager}",
        )
    fix = (
        f"pyenv install {expected}"
        if profile.python.manager == "pyenv"
        else f"Install Python {expected}+ via your system package manager"
    )
    return CheckResult(
        name="python_version",
        category="python",
        passed=False,
        message=f"Expected Python >={expected}, found {actual}",
        detail=f"Running: {sys.executable}",
        fix_command=fix,
        auto_fixable=profile.python.manager == "pyenv",
    )


def check_venv_exists(profile: BootstrapProfile) -> CheckResult:
    """Check that .venv exists and has squadops installed (R4: required for all profiles)."""
    venv_path = Path.cwd() / ".venv"
    if not venv_path.is_dir():
        return CheckResult(
            name="venv_exists",
            category="python",
            passed=False,
            message=".venv directory not found",
            detail=f"Expected at {venv_path}",
            fix_command=f"python{profile.python.version} -m venv .venv && .venv/bin/pip install -e .",
            auto_fixable=True,
        )
    # Check that squadops is installed in the venv
    pip_exe = venv_path / "bin" / "pip"
    if not pip_exe.exists():
        pip_exe = venv_path / "Scripts" / "pip.exe"  # Windows fallback
    if pip_exe.exists():
        try:
            result = subprocess.run(
                [str(pip_exe), "show", "squadops"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                return CheckResult(
                    name="venv_exists",
                    category="python",
                    passed=False,
                    message=".venv exists but squadops is not installed",
                    fix_command=".venv/bin/pip install -e .",
                    auto_fixable=True,
                )
        except (subprocess.TimeoutExpired, OSError):
            pass  # Fall through to pass — can't verify, but venv exists
    return CheckResult(
        name="venv_exists",
        category="python",
        passed=True,
        message=f".venv present at {venv_path}",
    )


# ---------------------------------------------------------------------------
# Platform checks
# ---------------------------------------------------------------------------


def check_platform(profile: BootstrapProfile) -> CheckResult:
    """Check OS, version, and distro match the profile."""
    current_os = "darwin" if sys.platform == "darwin" else "linux"
    expected_os = profile.platform.os

    if current_os != expected_os:
        return CheckResult(
            name="platform",
            category="platform",
            passed=False,
            message=f"Expected OS '{expected_os}', running on '{current_os}'",
            fix_command=f"Use a machine running {expected_os}",
        )

    # macOS version check
    if expected_os == "darwin" and profile.platform.min_version:
        mac_ver = platform.mac_ver()[0]
        if mac_ver and _version_lt(mac_ver, profile.platform.min_version):
            return CheckResult(
                name="platform",
                category="platform",
                passed=False,
                message=f"macOS {mac_ver} < required {profile.platform.min_version}",
                fix_command="Update macOS via System Settings > Software Update",
            )

    # Linux distro check
    if expected_os == "linux":
        distro_id, distro_version = _detect_linux_distro()
        if profile.platform.distro and distro_id != profile.platform.distro:
            return CheckResult(
                name="platform",
                category="platform",
                passed=False,
                message=f"Expected distro '{profile.platform.distro}', found '{distro_id}'",
                fix_command=f"Use a machine running {profile.platform.distro}",
            )
        if profile.platform.distro_min_version and distro_version:
            if _version_lt(distro_version, profile.platform.distro_min_version):
                return CheckResult(
                    name="platform",
                    category="platform",
                    passed=False,
                    message=(
                        f"{distro_id} {distro_version} < "
                        f"required {profile.platform.distro_min_version}"
                    ),
                    fix_command=f"Upgrade {distro_id} to >= {profile.platform.distro_min_version}",
                )

    version_str = platform.mac_ver()[0] if current_os == "darwin" else ""
    return CheckResult(
        name="platform",
        category="platform",
        passed=True,
        message=f"{current_os} {version_str}".strip(),
    )


def _detect_linux_distro() -> tuple[str, str]:
    """Read /etc/os-release to detect distro ID and VERSION_ID."""
    try:
        text = Path("/etc/os-release").read_text()
        info: dict[str, str] = {}
        for line in text.splitlines():
            if "=" in line:
                key, _, val = line.partition("=")
                info[key] = val.strip('"')
        return info.get("ID", "unknown"), info.get("VERSION_ID", "")
    except OSError:
        return "unknown", ""


def _version_lt(actual: str, minimum: str) -> bool:
    """Compare dotted version strings. Returns True if actual < minimum."""
    try:
        actual_parts = [int(x) for x in actual.split(".")]
        min_parts = [int(x) for x in minimum.split(".")]
        return actual_parts < min_parts
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# System dependency checks
# ---------------------------------------------------------------------------


def check_system_dep(dep: SystemDep) -> CheckResult:
    """Check that a system dependency is available via its check command."""
    if not dep.check:
        # install: none without a check command — nothing to verify
        return CheckResult(
            name=f"tool:{dep.name}",
            category="tools",
            passed=True,
            message=f"{dep.name} (no check command, skipped)",
        )
    if shutil.which(dep.check.split()[0]) is None and dep.install != "none":
        # Command not on PATH — faster than running subprocess
        fix = _fix_for_dep(dep)
        return CheckResult(
            name=f"tool:{dep.name}",
            category="tools",
            passed=False,
            message=f"{dep.name}: '{dep.check.split()[0]}' not found on PATH",
            fix_command=fix,
            auto_fixable=dep.install in ("brew", "apt"),
        )
    try:
        subprocess.run(
            dep.check,
            shell=True,
            capture_output=True,
            timeout=10,
        )
        # exit code 0 = pass; non-zero also accepted for some tools
        # (e.g. nvidia-smi returns version info regardless of exit code)
        return CheckResult(
            name=f"tool:{dep.name}",
            category="tools",
            passed=True,
            message=f"{dep.name} found",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name=f"tool:{dep.name}",
            category="tools",
            passed=False,
            message=f"{dep.name}: check command timed out",
            detail=f"Command: {dep.check}",
            fix_command=_fix_for_dep(dep),
        )
    except OSError as exc:
        return CheckResult(
            name=f"tool:{dep.name}",
            category="tools",
            passed=False,
            message=f"{dep.name}: check failed ({exc})",
            fix_command=_fix_for_dep(dep),
        )


def _fix_for_dep(dep: SystemDep) -> str:
    """Build a fix command string for a missing system dependency."""
    if dep.install == "brew":
        if dep.cask:
            return f"brew install --cask {dep.package}"
        return f"brew install {dep.package}"
    if dep.install == "apt":
        return f"sudo apt install {dep.package}"
    if dep.install == "script":
        return f"See installation docs for {dep.name}"
    if dep.install == "manual":
        return f"Manually install {dep.name}"
    return f"Install {dep.name}"


# ---------------------------------------------------------------------------
# Docker service checks
# ---------------------------------------------------------------------------


def check_docker_service(svc: DockerService) -> CheckResult:
    """Check that a Docker service is healthy via its declared healthcheck."""
    if svc.healthcheck == "http":
        return _check_http(svc)
    if svc.healthcheck == "tcp":
        return _check_tcp(svc)
    if svc.healthcheck == "docker_health":
        return _check_docker_health(svc)
    return CheckResult(
        name=f"docker:{svc.name}",
        category="docker",
        passed=False,
        message=f"Unknown healthcheck type '{svc.healthcheck}'",
    )


def _check_http(svc: DockerService) -> CheckResult:
    """Check HTTP endpoint returns a 2xx status."""
    try:
        import urllib.request

        req = urllib.request.Request(svc.endpoint, method="GET")
        with urllib.request.urlopen(req, timeout=svc.timeout_seconds) as resp:
            if 200 <= resp.status < 300:
                return CheckResult(
                    name=f"docker:{svc.name}",
                    category="docker",
                    passed=True,
                    message=f"{svc.name} healthy ({svc.endpoint})",
                )
            return CheckResult(
                name=f"docker:{svc.name}",
                category="docker",
                passed=False,
                message=f"{svc.name} returned HTTP {resp.status}",
                detail=f"Endpoint: {svc.endpoint}",
                fix_command=f"docker-compose up -d {svc.name}",
                auto_fixable=True,
            )
    except Exception as exc:
        return CheckResult(
            name=f"docker:{svc.name}",
            category="docker",
            passed=False,
            message=f"{svc.name} unreachable at {svc.endpoint}",
            detail=str(exc),
            fix_command=f"docker-compose up -d {svc.name}",
            auto_fixable=True,
        )


def _check_tcp(svc: DockerService) -> CheckResult:
    """Check that a TCP port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(svc.timeout_seconds)
        result = sock.connect_ex(("localhost", svc.port))
        sock.close()
        if result == 0:
            return CheckResult(
                name=f"docker:{svc.name}",
                category="docker",
                passed=True,
                message=f"{svc.name} listening on port {svc.port}",
            )
        return CheckResult(
            name=f"docker:{svc.name}",
            category="docker",
            passed=False,
            message=f"{svc.name} not listening on port {svc.port}",
            fix_command=f"docker-compose up -d {svc.name}",
            auto_fixable=True,
        )
    except OSError as exc:
        return CheckResult(
            name=f"docker:{svc.name}",
            category="docker",
            passed=False,
            message=f"{svc.name} port {svc.port} check failed",
            detail=str(exc),
            fix_command=f"docker-compose up -d {svc.name}",
            auto_fixable=True,
        )


def _check_docker_health(svc: DockerService) -> CheckResult:
    """Check container health via docker inspect."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", svc.name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        status = result.stdout.strip()
        if status == "healthy":
            return CheckResult(
                name=f"docker:{svc.name}",
                category="docker",
                passed=True,
                message=f"{svc.name} container healthy",
            )
        return CheckResult(
            name=f"docker:{svc.name}",
            category="docker",
            passed=False,
            message=f"{svc.name} container status: {status or 'not found'}",
            fix_command=f"docker-compose up -d {svc.name}",
            auto_fixable=True,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return CheckResult(
            name=f"docker:{svc.name}",
            category="docker",
            passed=False,
            message=f"{svc.name} docker inspect failed",
            detail=str(exc),
            fix_command="docker-compose up -d",
            auto_fixable=True,
        )


# ---------------------------------------------------------------------------
# Ollama model checks
# ---------------------------------------------------------------------------


def _get_ollama_models() -> set[str]:
    """Get set of installed Ollama model names."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return set()
        models = set()
        for line in result.stdout.splitlines()[1:]:  # skip header
            parts = line.split()
            if parts:
                models.add(parts[0])
        return models
    except (subprocess.TimeoutExpired, OSError):
        return set()


def check_ollama_model_exact(model: OllamaModelExact, installed: set[str]) -> CheckResult:
    """Check that an exact model is installed."""
    if model.name in installed:
        return CheckResult(
            name=f"model:{model.name}",
            category="models",
            passed=True,
            message=f"{model.name} installed",
        )
    return CheckResult(
        name=f"model:{model.name}",
        category="models",
        passed=not model.required,
        message=f"{model.name} not found" + ("" if model.required else " (optional)"),
        fix_command=f"ollama pull {model.name}",
        auto_fixable=True,
    )


def check_ollama_model_alternative(
    model: OllamaModelAlternative, installed: set[str]
) -> CheckResult:
    """Check that at least one model from required_one_of is installed (R9)."""
    found = [m for m in model.required_one_of if m in installed]
    if found:
        return CheckResult(
            name=f"model:{'|'.join(model.required_one_of)}",
            category="models",
            passed=True,
            message=f"{found[0]} installed (from tier: {model.tier or 'unspecified'})",
        )
    tier_label = f" (tier: {model.tier})" if model.tier else ""
    return CheckResult(
        name=f"model:{'|'.join(model.required_one_of)}",
        category="models",
        passed=False,
        message=(
            f"Missing required model{tier_label}: "
            f"expected one of {model.required_one_of}; none found"
        ),
        fix_command=f"ollama pull {model.required_one_of[0]}",
        auto_fixable=True,
    )


# ---------------------------------------------------------------------------
# GPU checks (R10)
# ---------------------------------------------------------------------------


def check_nvidia_gpu() -> list[CheckResult]:
    """Run GPU checks: hard checks + heuristic probe."""
    results = []

    # Hard check: nvidia-smi
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            proc = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=10)
            if proc.returncode == 0:
                results.append(
                    CheckResult(
                        name="gpu:nvidia-smi",
                        category="gpu",
                        passed=True,
                        message="nvidia-smi available",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="gpu:nvidia-smi",
                        category="gpu",
                        passed=False,
                        message="nvidia-smi failed",
                        detail=proc.stderr.strip(),
                        fix_command="Install NVIDIA drivers",
                    )
                )
        except (subprocess.TimeoutExpired, OSError):
            results.append(
                CheckResult(
                    name="gpu:nvidia-smi",
                    category="gpu",
                    passed=False,
                    message="nvidia-smi execution failed",
                    fix_command="Install NVIDIA drivers",
                )
            )
    else:
        results.append(
            CheckResult(
                name="gpu:nvidia-smi",
                category="gpu",
                passed=False,
                message="nvidia-smi not found",
                fix_command="Install NVIDIA drivers",
            )
        )

    # Hard check: nvidia-container-toolkit
    nct = shutil.which("nvidia-container-toolkit")
    if nct:
        results.append(
            CheckResult(
                name="gpu:nvidia-container-toolkit",
                category="gpu",
                passed=True,
                message="nvidia-container-toolkit found",
            )
        )
    else:
        results.append(
            CheckResult(
                name="gpu:nvidia-container-toolkit",
                category="gpu",
                passed=False,
                message="nvidia-container-toolkit not found",
                fix_command="sudo apt install nvidia-container-toolkit",
            )
        )

    # Heuristic: Ollama GPU access probe
    try:
        proc = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=10)
        gpu_detected = "gpu" in proc.stdout.lower() if proc.returncode == 0 else False
        results.append(
            CheckResult(
                name="gpu:ollama-access",
                category="gpu",
                passed=gpu_detected,
                message="Ollama GPU access detected"
                if gpu_detected
                else "Ollama GPU access not detected",
                heuristic=True,
            )
        )
    except (subprocess.TimeoutExpired, OSError):
        results.append(
            CheckResult(
                name="gpu:ollama-access",
                category="gpu",
                passed=False,
                message="Could not probe Ollama GPU access",
                heuristic=True,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Auth check
# ---------------------------------------------------------------------------


def check_auth_token() -> CheckResult:
    """Check that a cached auth token exists and is not expired."""
    try:
        from squadops.cli.auth import is_expired, load_cached_token

        token = load_cached_token()
        if token is None:
            return CheckResult(
                name="auth_token",
                category="auth",
                passed=False,
                message="No cached auth token found",
                fix_command="squadops login",
                auto_fixable=True,
            )
        if is_expired(token):
            return CheckResult(
                name="auth_token",
                category="auth",
                passed=False,
                message="Auth token is expired",
                fix_command="squadops login",
                auto_fixable=True,
            )
        remaining = token.expires_at - time.time()
        minutes = int(remaining / 60)
        return CheckResult(
            name="auth_token",
            category="auth",
            passed=True,
            message=f"Token valid ({minutes}m remaining)",
        )
    except ImportError:
        return CheckResult(
            name="auth_token",
            category="auth",
            passed=False,
            message="Auth module not available",
            detail="squadops CLI may not be installed",
            fix_command=".venv/bin/pip install -e .",
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _collect_python_checks(profile: BootstrapProfile) -> list[CheckResult]:
    return [check_python_version(profile), check_venv_exists(profile)]


def _collect_platform_checks(profile: BootstrapProfile) -> list[CheckResult]:
    return [check_platform(profile)]


def _collect_tools_checks(profile: BootstrapProfile) -> list[CheckResult]:
    return [check_system_dep(dep) for dep in profile.system_deps]


def _collect_docker_checks(profile: BootstrapProfile) -> list[CheckResult]:
    return [check_docker_service(svc) for svc in profile.docker_services]


def _collect_models_checks(profile: BootstrapProfile) -> list[CheckResult]:
    installed_models = _get_ollama_models()
    results: list[CheckResult] = []
    for model in profile.ollama_models:
        if isinstance(model, OllamaModelExact):
            results.append(check_ollama_model_exact(model, installed_models))
        elif isinstance(model, OllamaModelAlternative):
            results.append(check_ollama_model_alternative(model, installed_models))
    return results


def _collect_gpu_checks(profile: BootstrapProfile) -> list[CheckResult]:
    has_nvidia = any("nvidia" in dep.name for dep in profile.system_deps)
    return list(check_nvidia_gpu()) if has_nvidia else []


def _collect_auth_checks(profile: BootstrapProfile) -> list[CheckResult]:
    return [check_auth_token()]


_CHECK_REGISTRY: list[tuple[str, object]] = [
    ("python", _collect_python_checks),
    ("platform", _collect_platform_checks),
    ("tools", _collect_tools_checks),
    ("docker", _collect_docker_checks),
    ("models", _collect_models_checks),
    ("gpu", _collect_gpu_checks),
    ("auth", _collect_auth_checks),
]


def run_checks(
    profile: BootstrapProfile,
    *,
    category: str | None = None,
) -> list[CheckResult]:
    """Run all applicable checks for a profile.

    Args:
        profile: The bootstrap profile to validate against.
        category: If set, only run checks in this category.

    Returns:
        List of CheckResult in execution order.
    """
    results: list[CheckResult] = []
    for cat, collect_fn in _CHECK_REGISTRY:
        if category is None or category == cat:
            results.extend(collect_fn(profile))
    return results
