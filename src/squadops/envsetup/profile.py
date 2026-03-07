"""Bootstrap profile schema and loading (SIP-0081).

Defines the BootstrapProfile frozen dataclass and strict v1 schema validation.
Profile YAML is the authoritative source of environment requirements (R1/R3 in plan).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1

VALID_INSTALL_METHODS = frozenset({"brew", "apt", "bundled", "script", "manual", "none"})
VALID_HEALTHCHECK_TYPES = frozenset({"http", "tcp", "docker_health"})
VALID_PYTHON_MANAGERS = frozenset({"pyenv", "system"})
VALID_PLATFORMS = frozenset({"darwin", "linux"})

_BOOTSTRAP_PROFILES_DIR = Path(__file__).resolve().parents[3] / "config" / "profiles" / "bootstrap"

# Top-level keys allowed in v1 schema (unknown fields are rejected).
_ALLOWED_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "name",
        "description",
        "platform",
        "python",
        "system_deps",
        "docker_services",
        "ollama_models",
        "deployment_profile",
        "squad_profile",
    }
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BootstrapProfileError(Exception):
    """Raised when a bootstrap profile fails validation."""


# ---------------------------------------------------------------------------
# Domain models (frozen dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlatformSpec:
    os: str
    min_version: str | None = None
    distro: str | None = None
    distro_min_version: str | None = None


@dataclass(frozen=True)
class PythonSpec:
    version: str
    manager: str
    extras: list[str] = field(default_factory=list)
    test_deps: str | None = None


@dataclass(frozen=True)
class SystemDep:
    name: str
    install: str
    check: str | None = None
    package: str | None = None
    cask: bool = False
    required: bool = True
    confirm: bool = False


@dataclass(frozen=True)
class DockerService:
    name: str
    healthcheck: str
    port: int | None = None
    endpoint: str | None = None
    timeout_seconds: int = 30


@dataclass(frozen=True)
class OllamaModelExact:
    name: str
    required: bool = True


@dataclass(frozen=True)
class OllamaModelAlternative:
    required_one_of: list[str]
    tier: str | None = None


OllamaModel = OllamaModelExact | OllamaModelAlternative


@dataclass(frozen=True)
class BootstrapProfile:
    schema_version: int
    name: str
    description: str
    platform: PlatformSpec
    python: PythonSpec
    system_deps: list[SystemDep] = field(default_factory=list)
    docker_services: list[DockerService] = field(default_factory=list)
    ollama_models: list[OllamaModel] = field(default_factory=list)
    deployment_profile: str | None = None
    squad_profile: str | None = None


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_system_dep(dep_data: dict, index: int) -> SystemDep:
    """Validate and construct a SystemDep from raw YAML dict."""
    name = dep_data.get("name")
    if not name:
        raise BootstrapProfileError(f"system_deps[{index}]: 'name' is required")

    install = dep_data.get("install")
    if not install:
        raise BootstrapProfileError(f"system_deps[{index}] ({name}): 'install' is required")
    if install not in VALID_INSTALL_METHODS:
        raise BootstrapProfileError(
            f"system_deps[{index}] ({name}): invalid install method '{install}', "
            f"must be one of {sorted(VALID_INSTALL_METHODS)}"
        )

    cask = dep_data.get("cask", False)
    if cask and install != "brew":
        raise BootstrapProfileError(
            f"system_deps[{index}] ({name}): 'cask: true' is only valid with 'install: brew'"
        )

    package = dep_data.get("package")
    if install in ("brew", "apt") and not package:
        raise BootstrapProfileError(
            f"system_deps[{index}] ({name}): 'package' is required when install is '{install}'"
        )

    check = dep_data.get("check")
    if install != "none" and not check:
        raise BootstrapProfileError(
            f"system_deps[{index}] ({name}): 'check' is required when install is not 'none'"
        )

    return SystemDep(
        name=name,
        install=install,
        check=check,
        package=package,
        cask=cask,
        required=dep_data.get("required", True),
        confirm=dep_data.get("confirm", False),
    )


def _validate_docker_service(svc_data: dict, index: int) -> DockerService:
    """Validate and construct a DockerService from raw YAML dict."""
    name = svc_data.get("name")
    if not name:
        raise BootstrapProfileError(f"docker_services[{index}]: 'name' is required")

    healthcheck = svc_data.get("healthcheck")
    if not healthcheck:
        raise BootstrapProfileError(f"docker_services[{index}] ({name}): 'healthcheck' is required")
    if healthcheck not in VALID_HEALTHCHECK_TYPES:
        raise BootstrapProfileError(
            f"docker_services[{index}] ({name}): invalid healthcheck '{healthcheck}', "
            f"must be one of {sorted(VALID_HEALTHCHECK_TYPES)}"
        )

    endpoint = svc_data.get("endpoint")
    if healthcheck == "http" and not endpoint:
        raise BootstrapProfileError(
            f"docker_services[{index}] ({name}): 'endpoint' is required for healthcheck 'http'"
        )

    port = svc_data.get("port")
    if healthcheck == "tcp" and port is None:
        raise BootstrapProfileError(
            f"docker_services[{index}] ({name}): 'port' is required for healthcheck 'tcp'"
        )

    return DockerService(
        name=name,
        healthcheck=healthcheck,
        port=port,
        endpoint=endpoint,
        timeout_seconds=svc_data.get("timeout_seconds", 30),
    )


def _validate_ollama_model(model_data: dict, index: int) -> OllamaModel:
    """Validate and construct an OllamaModel from raw YAML dict."""
    if "required_one_of" in model_data:
        alternatives = model_data["required_one_of"]
        if not isinstance(alternatives, list) or len(alternatives) == 0:
            raise BootstrapProfileError(
                f"ollama_models[{index}]: 'required_one_of' must be a non-empty list"
            )
        return OllamaModelAlternative(
            required_one_of=alternatives,
            tier=model_data.get("tier"),
        )

    name = model_data.get("name")
    if not name:
        raise BootstrapProfileError(
            f"ollama_models[{index}]: 'name' is required for exact model requirements"
        )
    return OllamaModelExact(
        name=name,
        required=model_data.get("required", True),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_bootstrap_profile(name: str, *, profiles_dir: Path | None = None) -> BootstrapProfile:
    """Load and validate a bootstrap profile from YAML.

    Args:
        name: Profile name (e.g. 'dev-mac'). Loaded from
              ``config/profiles/bootstrap/<name>.yaml``.
        profiles_dir: Override the profiles directory (for testing).

    Returns:
        A validated BootstrapProfile.

    Raises:
        BootstrapProfileError: If the profile is missing, malformed, or fails
            schema validation.
    """
    base_dir = profiles_dir or _BOOTSTRAP_PROFILES_DIR
    profile_path = base_dir / f"{name}.yaml"

    if not profile_path.exists():
        available = list_bootstrap_profiles(profiles_dir=base_dir)
        raise BootstrapProfileError(
            f"Bootstrap profile '{name}' not found at {profile_path}. "
            f"Available profiles: {available}"
        )

    try:
        with open(profile_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise BootstrapProfileError(f"Failed to parse {profile_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise BootstrapProfileError(f"Profile '{name}' must be a YAML mapping, got {type(raw)}")

    # ── Schema version ──────────────────────────────────────────────────
    schema_version = raw.get("schema_version")
    if schema_version is None:
        raise BootstrapProfileError(
            f"Profile '{name}': 'schema_version' is required. Add 'schema_version: 1'."
        )
    if schema_version != SCHEMA_VERSION:
        raise BootstrapProfileError(
            f"Profile '{name}': unsupported schema_version {schema_version} "
            f"(this version supports schema_version {SCHEMA_VERSION})"
        )

    # ── Reject unknown top-level keys ───────────────────────────────────
    unknown_keys = set(raw.keys()) - _ALLOWED_TOP_LEVEL_KEYS
    if unknown_keys:
        raise BootstrapProfileError(
            f"Profile '{name}': unknown top-level fields {sorted(unknown_keys)}. "
            f"Allowed fields: {sorted(_ALLOWED_TOP_LEVEL_KEYS)}"
        )

    # ── Required fields ─────────────────────────────────────────────────
    profile_name = raw.get("name")
    if not profile_name:
        raise BootstrapProfileError(f"Profile '{name}': 'name' is required")

    description = raw.get("description", "")

    # ── Platform ────────────────────────────────────────────────────────
    platform_raw = raw.get("platform")
    if not platform_raw or not isinstance(platform_raw, dict):
        raise BootstrapProfileError(f"Profile '{name}': 'platform' mapping is required")

    platform_os = platform_raw.get("os")
    if not platform_os:
        raise BootstrapProfileError(f"Profile '{name}': 'platform.os' is required")
    if platform_os not in VALID_PLATFORMS:
        raise BootstrapProfileError(
            f"Profile '{name}': invalid platform.os '{platform_os}', "
            f"must be one of {sorted(VALID_PLATFORMS)}"
        )

    platform = PlatformSpec(
        os=platform_os,
        min_version=platform_raw.get("min_version"),
        distro=platform_raw.get("distro"),
        distro_min_version=platform_raw.get("distro_min_version"),
    )

    # ── Python ──────────────────────────────────────────────────────────
    python_raw = raw.get("python")
    if not python_raw or not isinstance(python_raw, dict):
        raise BootstrapProfileError(f"Profile '{name}': 'python' mapping is required")

    python_version = python_raw.get("version")
    if not python_version:
        raise BootstrapProfileError(f"Profile '{name}': 'python.version' is required")

    python_manager = python_raw.get("manager")
    if not python_manager:
        raise BootstrapProfileError(f"Profile '{name}': 'python.manager' is required")
    if python_manager not in VALID_PYTHON_MANAGERS:
        raise BootstrapProfileError(
            f"Profile '{name}': invalid python.manager '{python_manager}', "
            f"must be one of {sorted(VALID_PYTHON_MANAGERS)}"
        )

    python_spec = PythonSpec(
        version=python_version,
        manager=python_manager,
        extras=python_raw.get("extras", []),
        test_deps=python_raw.get("test_deps"),
    )

    # ── System deps ─────────────────────────────────────────────────────
    system_deps = [_validate_system_dep(dep, i) for i, dep in enumerate(raw.get("system_deps", []))]

    # ── Docker services ─────────────────────────────────────────────────
    docker_services = [
        _validate_docker_service(svc, i) for i, svc in enumerate(raw.get("docker_services", []))
    ]

    # ── Ollama models ───────────────────────────────────────────────────
    ollama_models = [
        _validate_ollama_model(model, i) for i, model in enumerate(raw.get("ollama_models", []))
    ]

    return BootstrapProfile(
        schema_version=schema_version,
        name=profile_name,
        description=description,
        platform=platform,
        python=python_spec,
        system_deps=system_deps,
        docker_services=docker_services,
        ollama_models=ollama_models,
        deployment_profile=raw.get("deployment_profile"),
        squad_profile=raw.get("squad_profile"),
    )


def list_bootstrap_profiles(*, profiles_dir: Path | None = None) -> list[str]:
    """Return sorted names of available bootstrap profiles.

    Args:
        profiles_dir: Override the profiles directory (for testing).
    """
    base_dir = profiles_dir or _BOOTSTRAP_PROFILES_DIR
    if not base_dir.exists():
        return []
    return sorted(p.stem for p in base_dir.glob("*.yaml"))
