"""Bootstrap doctor checks (SIP-0081).

Each check function validates one aspect of the bootstrap profile contract
and returns a CheckResult with pass/fail, fix guidance, and heuristic flag.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from squadops.bootstrap.database_isolation import (
    DEPLOYMENT_DB_NAME,
    SQLSTATE_INSUFFICIENT_PRIVILEGE,
    TEST_DB_NAME,
    TEST_DB_PASSWORD_ENV,
    TEST_DB_ROLE,
    test_role_dsn,
)
from squadops.bootstrap.setup.profile import (
    BootstrapProfile,
    DockerService,
    MemoryContainment,
    OllamaModelAlternative,
    OllamaModelExact,
    SystemDep,
)

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

VALID_CATEGORIES = frozenset(
    {
        "python",
        "platform",
        "tools",
        "docker",
        "database",
        "models",
        "squad",
        "gpu",
        "auth",
        "broker",
        "verification",
        "sandbox",
    }
)


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
# Database isolation check (#1180)
# ---------------------------------------------------------------------------

#: What the deploy and bootstrap paths run; offered as the fix, never as the mechanism.
_PROVISION_TEST_DATABASE = "./scripts/dev/ops/ensure_test_database.sh"

#: SQLSTATEs the server answers a connection attempt with. Strings at the boundary,
#: named here so the decision below reads as what it is.
_SQLSTATE_INVALID_PASSWORD = "28P01"
_SQLSTATE_INVALID_AUTHORIZATION = "28000"
_SQLSTATE_UNKNOWN_DATABASE = "3D000"


@dataclass(frozen=True)
class ConnectionProbe:
    """What one connection attempt came back with — the server's answer, not ours."""

    connected: bool
    sqlstate: str | None = None  # the server refused, with this SQLSTATE
    error: str | None = None  # text of whatever refused it
    unreachable: bool = False  # nothing answered at all (socket error, timeout)


def _probe_connection(dsn: str) -> ConnectionProbe:
    """Open a connection and close it at once; report what happened."""
    import asyncpg

    async def _attempt() -> ConnectionProbe:
        try:
            conn = await asyncpg.connect(dsn, timeout=5)
        except asyncpg.PostgresError as exc:
            return ConnectionProbe(connected=False, sqlstate=exc.sqlstate, error=str(exc))
        except (OSError, TimeoutError) as exc:
            return ConnectionProbe(connected=False, error=str(exc), unreachable=True)
        await conn.close()
        return ConnectionProbe(connected=True)

    return asyncio.run(_attempt())


def check_test_database_isolation(
    *,
    port: int,
    password: str | None,
    probe: Callable[[str], ConnectionProbe] | None = None,
) -> CheckResult:
    """The integration-test role authenticates on its own database AND is refused by the
    deployment database with a permission error (#1180).

    The negative is the check. A probe that only proved the test database reachable would
    have passed throughout the 2026-08-30 incident; a refusal for any reason other than
    ``42501`` (wrong password, no such database) is not evidence of the grant and fails
    too. The first probe is the paired control: without it, "refused" could be a role that
    does not exist. Unverifiable (no password, no server) warns heuristically — the broker
    pattern; the ``docker`` category already reports a down Postgres in red.
    """
    # Resolved at call time, not bound as a default, so the module attribute is the seam
    # a test patches and the collector never reaches a real server by accident.
    probe = probe or _probe_connection
    name = "database:test-role-isolation"
    if not password:
        return CheckResult(
            name=name,
            category="database",
            passed=False,
            heuristic=True,
            message=f"{TEST_DB_PASSWORD_ENV} is not set — test-role isolation not verified",
            detail=(
                "The bootstrap and deploy paths write it to .env (from .env.example) and "
                "the CLI loads .env; an older .env gets it on the next deploy."
            ),
            fix_command=_PROVISION_TEST_DATABASE,
        )

    own = probe(test_role_dsn(password, port=port, database=TEST_DB_NAME))
    if own.unreachable:
        return CheckResult(
            name=name,
            category="database",
            passed=False,
            heuristic=True,
            message=f"Postgres unreachable on localhost:{port} — test-role isolation not verified",
            detail=own.error,
        )
    if not own.connected:
        if own.sqlstate in (_SQLSTATE_INVALID_PASSWORD, _SQLSTATE_INVALID_AUTHORIZATION):
            message = (
                f"test role {TEST_DB_ROLE!r} cannot authenticate on {TEST_DB_NAME!r} — "
                f"the role is missing, or its password is not {TEST_DB_PASSWORD_ENV}"
            )
        elif own.sqlstate == _SQLSTATE_UNKNOWN_DATABASE:
            message = f"test database {TEST_DB_NAME!r} does not exist"
        else:
            message = f"test role {TEST_DB_ROLE!r} refused by {TEST_DB_NAME!r} ({own.sqlstate})"
        return CheckResult(
            name=name,
            category="database",
            passed=False,
            message=message,
            detail=own.error,
            fix_command=_PROVISION_TEST_DATABASE,
        )

    deployment = probe(test_role_dsn(password, port=port, database=DEPLOYMENT_DB_NAME))
    if deployment.connected:
        return CheckResult(
            name=name,
            category="database",
            passed=False,
            message=(
                f"{TEST_DB_ROLE!r} CAN connect to the deployment database "
                f"{DEPLOYMENT_DB_NAME!r} — REVOKE CONNECT ON DATABASE {DEPLOYMENT_DB_NAME} "
                f"FROM PUBLIC is not applied"
            ),
            detail="The integration suite could reach live cycle data (#1180, #1099).",
            fix_command=_PROVISION_TEST_DATABASE,
        )
    if deployment.sqlstate == SQLSTATE_INSUFFICIENT_PRIVILEGE:
        return CheckResult(
            name=name,
            category="database",
            passed=True,
            message=(
                f"{TEST_DB_ROLE!r} authenticates on {TEST_DB_NAME!r} and is refused by "
                f"{DEPLOYMENT_DB_NAME!r} (permission denied)"
            ),
        )
    if deployment.unreachable:
        return CheckResult(
            name=name,
            category="database",
            passed=False,
            heuristic=True,
            message=f"Postgres stopped answering on localhost:{port} between probes",
            detail=deployment.error,
        )
    return CheckResult(
        name=name,
        category="database",
        passed=False,
        message=(
            f"{DEPLOYMENT_DB_NAME!r} refused {TEST_DB_ROLE!r} with {deployment.sqlstate}, "
            f"not a permission error — a refusal for another reason is not isolation"
        ),
        detail=deployment.error,
        fix_command=_PROVISION_TEST_DATABASE,
    )


# ---------------------------------------------------------------------------
# Ollama model checks
# ---------------------------------------------------------------------------


def _query_ollama_models() -> set[str] | None:
    """Installed Ollama model names, or ``None`` if the backend can't be queried.

    ``None`` (``ollama`` missing / non-zero exit / timeout) is deliberately
    distinct from an empty set (reachable, nothing pulled): callers that
    warn-and-allow on *unverifiable* availability (SIP-0095 §6.3) need that
    distinction, or they'd wrongly block whenever the backend hiccups.
    """
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    models = set()
    for line in result.stdout.splitlines()[1:]:  # skip header
        parts = line.split()
        if parts:
            models.add(parts[0])
    return models


def _get_ollama_models() -> set[str]:
    """Installed Ollama model names, empty on failure (legacy binary pull-check)."""
    return _query_ollama_models() or set()


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
# Broker hygiene checks (#328)
# ---------------------------------------------------------------------------

# Queue-name prefixes retired by SIP-0094 (per-run cycle_results_{run_id} reply
# queues, replaced by durable per-agent {agent_id}_replies). Any surviving queue
# with one of these prefixes is orphaned residue, not a live path.
_RETIRED_QUEUE_PREFIXES = ("cycle_results",)


def _query_broker_queues(service: str = "rabbitmq") -> list[dict] | None:
    """Per-queue ``{name, messages, consumers}`` via ``rabbitmqctl list_queues``
    run inside the broker container.

    The container is resolved from the compose *service* name (``docker compose
    ps -q``) rather than a hardcoded container name, and rabbitmqctl runs as the
    broker admin so no credentials are needed — the same host-side access path
    ``rebuild_and_deploy.sh`` uses. Returns ``None`` when the broker can't be
    queried (docker absent, container down, rabbitmqctl error); callers warn
    heuristically rather than hard-fail on an unqueryable broker.
    """
    try:
        cid_proc = subprocess.run(
            ["docker", "compose", "ps", "-q", service],
            capture_output=True,
            text=True,
            timeout=10,
        )
        container_id = cid_proc.stdout.strip()
        if cid_proc.returncode != 0 or not container_id:
            return None
        proc = subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "rabbitmqctl",
                "list_queues",
                "name",
                "messages",
                "consumers",
                "--formatter",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout)
        return [
            {
                "name": q.get("name", ""),
                "messages": int(q.get("messages", 0) or 0),
                "consumers": int(q.get("consumers", 0) or 0),
            }
            for q in data
        ]
    except (subprocess.TimeoutExpired, OSError, ValueError, json.JSONDecodeError):
        return None


def check_broker_hygiene(service: str = "rabbitmq") -> list[CheckResult]:
    """Flag broker cruft: queues on a retired naming scheme, and any queue
    holding messages with no consumer (undrained backlog). Both are the residue
    the SIP-0094 migration left and the #323 consumer churn would have shown
    (#328). An unqueryable broker warns (~) rather than failing.
    """
    queues = _query_broker_queues(service)
    if queues is None:
        return [
            CheckResult(
                name="broker:queues",
                category="broker",
                passed=False,
                heuristic=True,
                message="Broker not queryable — skipped queue hygiene",
                detail=(
                    "Could not run `rabbitmqctl list_queues` in the broker container "
                    "(docker unavailable or broker not running)."
                ),
            )
        ]

    results: list[CheckResult] = []

    retired = sorted(
        q["name"] for q in queues if any(q["name"].startswith(p) for p in _RETIRED_QUEUE_PREFIXES)
    )
    if retired:
        preview = ", ".join(retired[:5]) + (" …" if len(retired) > 5 else "")
        results.append(
            CheckResult(
                name="broker:retired-queues",
                category="broker",
                passed=False,
                message=(
                    f"{len(retired)} queue(s) use a retired naming scheme "
                    "(pre-SIP-0094 cycle_results_*)"
                ),
                detail=f"Orphaned by the SIP-0094 per-agent reply-queue migration: {preview}",
                fix_command=(
                    "Delete after confirming the backlog is dead history, e.g. "
                    "`docker compose exec rabbitmq rabbitmqctl delete_queue <name>`"
                ),
            )
        )

    undrained = sorted(
        (q for q in queues if q["messages"] > 0 and q["consumers"] == 0),
        key=lambda q: -q["messages"],
    )
    if undrained:
        preview = ", ".join(f"{q['name']} ({q['messages']} msg)" for q in undrained[:5])
        results.append(
            CheckResult(
                name="broker:undrained-queues",
                category="broker",
                passed=False,
                message=f"{len(undrained)} queue(s) hold messages with no consumer",
                detail=f"Undrained backlog — results produced but nothing draining: {preview}",
                fix_command=(
                    "Investigate the missing consumer; drain or delete the queue "
                    "once the backlog is confirmed dead."
                ),
            )
        )

    if not results:
        results.append(
            CheckResult(
                name="broker:queues",
                category="broker",
                passed=True,
                message=(
                    f"{len(queues)} broker queue(s) healthy — no retired schemes, "
                    "no undrained backlogs"
                ),
            )
        )
    return results


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


def _collect_database_checks(profile: BootstrapProfile) -> list[CheckResult]:
    """Test-role isolation, only when the profile declares the postgres service — the
    broker pattern. The port is the profile's; the password is the CLI's ``.env`` load."""
    pg = next((svc for svc in profile.docker_services if svc.name == "postgres"), None)
    if pg is None:
        return []
    return [
        check_test_database_isolation(
            port=pg.port or 5432,  # every profile declares it; 5432 is Postgres's own default
            password=os.environ.get(TEST_DB_PASSWORD_ENV),
        )
    ]


def _collect_models_checks(profile: BootstrapProfile) -> list[CheckResult]:
    installed_models = _get_ollama_models()
    results: list[CheckResult] = []
    for model in profile.ollama_models:
        if isinstance(model, OllamaModelExact):
            results.append(check_ollama_model_exact(model, installed_models))
        elif isinstance(model, OllamaModelAlternative):
            results.append(check_ollama_model_alternative(model, installed_models))
    return results


def _collect_squad_checks(profile: BootstrapProfile) -> list[CheckResult]:
    """Model-availability for the box's squad profile, via the SHARED create-time
    decision (SIP-0095 §8, #224) — so ``doctor`` and cycle-create agree on what
    "available" means. Blocks name a definitively-missing model; an unreachable
    backend warns (heuristic ``~``) rather than fails, per warn-and-allow (§6.3).
    """
    if not profile.squad_profile:
        return []

    # Local imports: only doctor's `squad` category needs these, and this confines
    # the adapter import to the bootstrap-wiring layer (#154).
    from adapters.cycles.config_squad_profile import ConfigSquadProfile
    from squadops.cycles.models import ProfileNotFoundError
    from squadops.cycles.preflight import model_availability_decision

    pid = profile.squad_profile
    try:
        squad = asyncio.run(ConfigSquadProfile().get_profile(pid))
    except ProfileNotFoundError:
        return [
            CheckResult(
                name=f"squad profile `{pid}`",
                category="squad",
                passed=False,
                message=f"squad profile `{pid}` is not defined in config/squad-profiles.yaml",
            )
        ]

    decision = model_availability_decision(squad, _query_ollama_models())
    if not decision.blocking and not decision.warnings:
        count = len({a.model for a in squad.agents if a.enabled and a.model})
        return [
            CheckResult(
                name=f"squad `{pid}` models",
                category="squad",
                passed=True,
                message=f"all {count} model(s) for squad `{pid}` are available",
            )
        ]

    results = [
        CheckResult(name=f"squad `{pid}` model", category="squad", passed=False, message=f.message)
        for f in decision.blocking
    ]
    results.extend(
        # unverifiable → warn (~), not a hard fail (warn-and-allow)
        CheckResult(
            name=f"squad `{pid}` model",
            category="squad",
            passed=False,
            heuristic=True,
            message=f.message,
        )
        for f in decision.warnings
    )
    return results


def _collect_gpu_checks(profile: BootstrapProfile) -> list[CheckResult]:
    has_nvidia = any("nvidia" in dep.name for dep in profile.system_deps)
    return list(check_nvidia_gpu()) if has_nvidia else []


#: systemd's own unit-state word, named rather than compared as a literal: "active" also
#: spells a CycleStatus/FlowState value, and the #380 enum-shadow guard is right to refuse
#: a bare comparison — these are two unrelated vocabularies that happen to share a string.
_SYSTEMD_ACTIVE = "active"


def _systemctl(*args: str) -> tuple[int, str]:
    """Run systemctl, returning ``(returncode, stdout)``; a missing systemctl is rc 127."""
    try:
        proc = subprocess.run(
            ["systemctl", *args], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return proc.returncode, proc.stdout.strip()


def _earlyoom_thresholds(exec_start: str) -> tuple[int | None, int | None]:
    """The ``-m`` and ``-s`` percentages off the unit's actual ExecStart.

    Read from what the unit RUNS, not from ``/etc/default/earlyoom``: an override file, a
    drop-in, or a hand-edited unit all change the former and leave the latter looking
    right. Values may be written ``-m 10`` or ``-m10``, and a ``PERCENT[,KILL_PERCENT]``
    pair takes the first number.
    """
    memory = swap = None
    tokens = exec_start.replace("=", " ").split()
    for i, token in enumerate(tokens):
        for flag, name in (("-m", "memory"), ("-s", "swap")):
            if not token.startswith(flag):
                continue
            raw = token[len(flag) :] or (tokens[i + 1] if i + 1 < len(tokens) else "")
            head = raw.split(",")[0].strip().rstrip("%")
            if not head.isdigit():
                continue
            if name == "memory":
                memory = int(head)
            else:
                swap = int(head)
    return memory, swap


def check_memory_containment(containment: MemoryContainment) -> list[CheckResult]:
    """Is a memory runaway bounded to one process, or does it take the box? (#1178)

    Three findings, because "installed" is not the property that matters. The
    2026-08-29 livelock ran with 23% of swap free the whole time, so an earlyoom at its
    stock ``-s 10`` would have watched the box die without firing — a check that stopped
    at "the daemon is active" would have passed throughout the outage it exists to
    prevent.
    """
    results: list[CheckResult] = []
    daemon = containment.daemon

    rc, state = _systemctl("is-active", daemon)
    active = rc == 0 and state == _SYSTEMD_ACTIVE
    if rc == 127:
        return [
            CheckResult(
                name=f"memory:{daemon}",
                category="memory",
                passed=False,
                heuristic=True,
                message="systemctl unavailable — memory containment cannot be verified here",
            )
        ]
    results.append(
        CheckResult(
            name=f"memory:{daemon}",
            category="memory",
            passed=active,
            message=(
                f"{daemon} is active — a memory runaway is bounded to one process"
                if active
                else f"{daemon} is {state or 'not installed'}: a memory runaway takes the box"
            ),
            fix_command=None if active else f"sudo apt install {containment.package}",
        )
    )

    if active:
        _, exec_start = _systemctl("show", "-p", "ExecStart", "--value", daemon)
        memory, swap = _earlyoom_thresholds(exec_start)
        # THE check. Swap must not be able to veto the kill on this box.
        swap_ok = swap is not None and swap >= containment.free_swap_percent
        results.append(
            CheckResult(
                name=f"memory:{daemon} swap threshold",
                category="memory",
                passed=swap_ok,
                message=(
                    f"free-swap threshold {swap}% cannot veto a kill "
                    f"(declared >= {containment.free_swap_percent}%)"
                    if swap_ok
                    else f"free-swap threshold is {swap if swap is not None else 'unset'}%, "
                    f"below the declared {containment.free_swap_percent}% — swap can veto "
                    f"the kill, which is why the 2026-08-29 livelock ran to a power cycle "
                    f"with 23% of swap still free"
                ),
                detail=exec_start or None,
                fix_command=(
                    None
                    if swap_ok
                    else f"set -s {containment.free_swap_percent} in /etc/default/{daemon} "
                    f"and `sudo systemctl restart {daemon}`"
                ),
            )
        )
        if memory is not None and memory != containment.free_memory_percent:
            results.append(
                CheckResult(
                    name=f"memory:{daemon} memory threshold",
                    category="memory",
                    passed=False,
                    heuristic=True,
                    message=(
                        f"free-memory threshold is {memory}%, profile declares "
                        f"{containment.free_memory_percent}%"
                    ),
                )
            )

    if containment.swappiness is not None:
        try:
            proc = subprocess.run(
                ["sysctl", "-n", "vm.swappiness"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            current = proc.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            current = ""
        matches = current.isdigit() and int(current) <= containment.swappiness
        results.append(
            CheckResult(
                name="memory:swappiness",
                category="memory",
                passed=matches,
                heuristic=True,  # mitigation, not containment — never a hard fail
                message=(
                    f"vm.swappiness={current} — the box prefers reclaiming to swapping"
                    if matches
                    else f"vm.swappiness={current or 'unknown'}, declared "
                    f"{containment.swappiness} — swapping is preferred longer, which "
                    f"lengthens a thrash before containment fires"
                ),
                fix_command=(
                    None if matches else f"sudo sysctl -w vm.swappiness={containment.swappiness}"
                ),
            )
        )
    return results


def _collect_memory_checks(profile: BootstrapProfile) -> list[CheckResult]:
    """Only for a profile that declares containment — mirrors how the GPU checks gate on
    an nvidia dependency. A laptop profile makes no claim and is asked nothing."""
    if profile.memory_containment is None:
        return []
    return check_memory_containment(profile.memory_containment)


def _collect_auth_checks(profile: BootstrapProfile) -> list[CheckResult]:
    return [check_auth_token()]


def _collect_broker_checks(profile: BootstrapProfile) -> list[CheckResult]:
    """Broker hygiene, only when the profile declares the rabbitmq service —
    mirrors how the GPU checks gate on an nvidia dependency."""
    broker_svc = next((svc for svc in profile.docker_services if svc.name == "rabbitmq"), None)
    if broker_svc is None:
        return []
    return check_broker_hygiene(broker_svc.name)


def _collect_verification_checks(profile: BootstrapProfile) -> list[CheckResult]:
    """SIP-0096 §8: report which tooling-backed framework checks can execute here.

    Deployment-scoped (not per cycle-request profile): for each framework check
    that needs external tooling, is that tooling provisioned in this deployment
    (``agents/instances/*/system-packages.txt``)? This is the same resolution the
    create-time preflight parity uses, so doctor's report agrees with the runtime
    reject (§8 parity). Checks with no external tooling are always executable and
    reported only implicitly (nothing to verify). Unresolvable provisioning →
    heuristic pass (never red when it cannot verify — the broker pattern)."""
    from squadops.cycles.check_registry import FRAMEWORK_CHECKS
    from squadops.cycles.check_tooling import resolve_provisioned_tooling

    provisioned = resolve_provisioned_tooling()
    results: list[CheckResult] = []
    for check in FRAMEWORK_CHECKS.values():
        if not check.required_tooling:
            continue
        needs = ", ".join(check.required_tooling)
        if provisioned is None:
            results.append(
                CheckResult(
                    name=f"check_tooling:{check.check_id}",
                    category="verification",
                    passed=True,
                    heuristic=True,
                    message=f"{check.check_id} needs {needs} — provisioning could not be resolved",
                )
            )
            continue
        missing = [t for t in check.required_tooling if t not in provisioned]
        if missing:
            results.append(
                CheckResult(
                    name=f"check_tooling:{check.check_id}",
                    category="verification",
                    passed=False,
                    message=(
                        f"{check.check_id} requires {', '.join(missing)}, not provisioned — "
                        f"a profile requiring it is rejected at create-time preflight"
                    ),
                    detail="Provisioned via agents/instances/<role>/system-packages.txt",
                    fix_command="Declare the package in the role's system-packages.txt and rebuild",
                )
            )
        else:
            results.append(
                CheckResult(
                    name=f"check_tooling:{check.check_id}",
                    category="verification",
                    passed=True,
                    message=f"{check.check_id} tooling provisioned ({needs})",
                )
            )
    return results


# ---------------------------------------------------------------------------
# Sandbox checks (SIP-0102 phase 102.2c)
# ---------------------------------------------------------------------------


def _fetch_sandbox_report(service_url: str) -> dict | None:
    """Best-effort GET of the sandbox service's /health environment block;
    None ⇒ unverifiable (the decision warns, never blocks on missing
    evidence)."""
    import httpx

    try:
        response = httpx.get(f"{service_url.rstrip('/')}/health", timeout=2.0)
        if response.status_code == 200:
            return response.json().get("environment")
    except (httpx.HTTPError, ValueError):
        pass
    return None


def _collect_sandbox_checks(profile: BootstrapProfile) -> list[CheckResult]:
    """Sandbox environment reconciliation — the SAME decision the cycle-create
    preflight applies (SIP-0102 102.2c), rendered as doctor results, so
    doctor and create-time never disagree."""
    from squadops.sandbox.environment import get_environment_contract
    from squadops.sandbox.main import sandbox_config_from_env
    from squadops.sandbox.preflight import sandbox_environment_decision

    try:
        cfg = sandbox_config_from_env()
    except ValueError as exc:
        return [
            CheckResult(
                name="sandbox_config",
                category="sandbox",
                passed=False,
                message=f"sandbox configuration is invalid: {exc}",
            )
        ]
    if cfg.provider != "docker":
        return [
            CheckResult(
                name="sandbox_dormant",
                category="sandbox",
                passed=True,
                message="sandbox provider is 'noop' (dormant) — nothing to verify",
            )
        ]
    try:
        expected: str | None = get_environment_contract(cfg.environment).contract_id()
    except ValueError:
        expected = None
    decision = sandbox_environment_decision(
        provider=cfg.provider,
        expected_contract_id=expected,
        report=_fetch_sandbox_report(cfg.service_url),
    )
    results = [
        CheckResult(
            name=f.code,
            category="sandbox",
            passed=False,
            message=f.message,
            fix_command=(
                "./scripts/dev/build_sandbox_env_image.sh"
                if f.code == "sandbox_image_missing"
                else None
            ),
        )
        for f in decision.blocking
    ]
    results += [
        CheckResult(
            name=f.code,
            category="sandbox",
            passed=False,
            message=f.message,
            heuristic=True,  # warn-and-allow parity with create-time preflight
        )
        for f in decision.warnings
    ]
    if not results:
        results.append(
            CheckResult(
                name="sandbox_environment",
                category="sandbox",
                passed=True,
                message=(
                    f"sandbox environment verified (contract {expected[:12]}…, image present)"
                ),
            )
        )
    return results


_CHECK_REGISTRY: list[tuple[str, object]] = [
    ("python", _collect_python_checks),
    ("platform", _collect_platform_checks),
    ("tools", _collect_tools_checks),
    ("docker", _collect_docker_checks),
    ("database", _collect_database_checks),
    ("models", _collect_models_checks),
    ("squad", _collect_squad_checks),
    ("gpu", _collect_gpu_checks),
    ("memory", _collect_memory_checks),
    ("auth", _collect_auth_checks),
    ("broker", _collect_broker_checks),
    ("verification", _collect_verification_checks),
    ("sandbox", _collect_sandbox_checks),
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
