"""Bootstrap profile schema validation tests (SIP-0081).

Each test answers: "What bug would this catch?"
"""

from __future__ import annotations

import pytest

from squadops.envsetup.profile import (
    BootstrapProfile,
    BootstrapProfileError,
    DockerService,
    OllamaModelAlternative,
    OllamaModelExact,
    PlatformSpec,
    PythonSpec,
    SystemDep,
    list_bootstrap_profiles,
    load_bootstrap_profile,
)

# ---------------------------------------------------------------------------
# Happy path — valid profiles load correctly
# ---------------------------------------------------------------------------


class TestLoadValidProfile:
    """Verify that well-formed profiles are loaded with all fields intact."""

    def test_load_full_profile(self, tmp_profile_dir, write_profile, valid_profile_data):
        """All fields round-trip correctly through YAML → dataclass."""
        write_profile("test-profile", valid_profile_data)
        profile = load_bootstrap_profile("test-profile", profiles_dir=tmp_profile_dir)

        assert isinstance(profile, BootstrapProfile)
        assert profile.schema_version == 1
        assert profile.name == "test-profile"
        assert profile.description == "A test profile"
        assert profile.deployment_profile == "local"
        assert profile.squad_profile == "full-squad"

        # Platform
        assert profile.platform == PlatformSpec(os="darwin", min_version="14.0")

        # Python
        assert profile.python == PythonSpec(
            version="3.11", manager="pyenv", extras=[], test_deps="tests/requirements.txt"
        )

        # System deps
        assert len(profile.system_deps) == 1
        assert profile.system_deps[0] == SystemDep(
            name="git", install="brew", check="git --version", package="git"
        )

        # Docker services
        assert len(profile.docker_services) == 1
        assert profile.docker_services[0] == DockerService(
            name="postgres", healthcheck="tcp", port=5432, timeout_seconds=30
        )

        # Ollama models
        assert len(profile.ollama_models) == 1
        assert profile.ollama_models[0] == OllamaModelExact(name="qwen2.5:7b", required=True)

    def test_load_minimal_profile(self, tmp_profile_dir, write_profile, minimal_profile_data):
        """Defaults for optional fields (empty lists, None) are applied correctly."""
        write_profile("minimal", minimal_profile_data)
        profile = load_bootstrap_profile("minimal", profiles_dir=tmp_profile_dir)

        assert profile.name == "minimal"
        assert profile.description == ""
        assert profile.system_deps == []
        assert profile.docker_services == []
        assert profile.ollama_models == []
        assert profile.deployment_profile is None
        assert profile.squad_profile is None
        assert profile.python.extras == []
        assert profile.python.test_deps is None

    def test_system_dep_defaults(self, tmp_profile_dir, write_profile, minimal_profile_data):
        """SystemDep optional fields default correctly."""
        minimal_profile_data["system_deps"] = [
            {"name": "git", "check": "git --version", "install": "apt", "package": "git"}
        ]
        write_profile("dep-defaults", minimal_profile_data)
        profile = load_bootstrap_profile("dep-defaults", profiles_dir=tmp_profile_dir)

        dep = profile.system_deps[0]
        assert dep.cask is False
        assert dep.required is True
        assert dep.confirm is False

    def test_docker_service_timeout_default(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """DockerService timeout_seconds defaults to 30."""
        minimal_profile_data["docker_services"] = [
            {"name": "redis", "healthcheck": "tcp", "port": 6379}
        ]
        write_profile("svc-defaults", minimal_profile_data)
        profile = load_bootstrap_profile("svc-defaults", profiles_dir=tmp_profile_dir)

        assert profile.docker_services[0].timeout_seconds == 30


# ---------------------------------------------------------------------------
# Schema version validation
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    """Catch schema version mismatches before any other validation runs."""

    def test_reject_missing_schema_version(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """Missing schema_version must fail with a clear message."""
        del minimal_profile_data["schema_version"]
        write_profile("no-version", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="schema_version.*required"):
            load_bootstrap_profile("no-version", profiles_dir=tmp_profile_dir)

    def test_reject_wrong_schema_version(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """Unsupported schema_version rejected with version-specific message."""
        minimal_profile_data["schema_version"] = 2
        write_profile("v2", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="unsupported schema_version 2"):
            load_bootstrap_profile("v2", profiles_dir=tmp_profile_dir)


# ---------------------------------------------------------------------------
# Unknown fields — prevent YAML drift
# ---------------------------------------------------------------------------


class TestUnknownFields:
    """Catch accidental extra keys that silently accumulate in profiles."""

    def test_reject_unknown_top_level_fields(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """Extra top-level keys are rejected to prevent mystery drift."""
        minimal_profile_data["magic_setting"] = True
        write_profile("extra-key", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="unknown top-level.*magic_setting"):
            load_bootstrap_profile("extra-key", profiles_dir=tmp_profile_dir)


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------


class TestRequiredFields:
    """Catch profiles missing mandatory fields before they cause runtime errors."""

    @pytest.mark.parametrize(
        "missing_field",
        ["name", "platform", "python"],
    )
    def test_reject_missing_required_field(
        self, tmp_profile_dir, write_profile, minimal_profile_data, missing_field
    ):
        """Each required top-level field must cause a clear error when missing."""
        del minimal_profile_data[missing_field]
        write_profile("missing", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match=f"'{missing_field}'.*required"):
            load_bootstrap_profile("missing", profiles_dir=tmp_profile_dir)

    def test_reject_missing_platform_os(self, tmp_profile_dir, write_profile, minimal_profile_data):
        """platform.os is required."""
        minimal_profile_data["platform"] = {"min_version": "14.0"}
        write_profile("no-os", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="platform.os.*required"):
            load_bootstrap_profile("no-os", profiles_dir=tmp_profile_dir)

    def test_reject_invalid_platform_os(self, tmp_profile_dir, write_profile, minimal_profile_data):
        """Invalid platform.os value is rejected."""
        minimal_profile_data["platform"]["os"] = "windows"
        write_profile("bad-os", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="invalid platform.os 'windows'"):
            load_bootstrap_profile("bad-os", profiles_dir=tmp_profile_dir)


# ---------------------------------------------------------------------------
# System deps validation
# ---------------------------------------------------------------------------


class TestSystemDepsValidation:
    """Catch install method, package, and check field misconfigurations."""

    def test_reject_invalid_install_method(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """Typos in install method are caught (e.g., 'yum')."""
        minimal_profile_data["system_deps"] = [
            {"name": "foo", "check": "foo --version", "install": "yum"}
        ]
        write_profile("bad-install", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="invalid install method 'yum'"):
            load_bootstrap_profile("bad-install", profiles_dir=tmp_profile_dir)

    def test_reject_cask_without_brew(self, tmp_profile_dir, write_profile, minimal_profile_data):
        """cask: true only makes sense with install: brew."""
        minimal_profile_data["system_deps"] = [
            {"name": "foo", "check": "foo", "install": "apt", "package": "foo", "cask": True}
        ]
        write_profile("cask-apt", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="cask.*only valid with.*brew"):
            load_bootstrap_profile("cask-apt", profiles_dir=tmp_profile_dir)

    def test_reject_missing_package_for_brew(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """install: brew requires a package name."""
        minimal_profile_data["system_deps"] = [{"name": "foo", "check": "foo", "install": "brew"}]
        write_profile("brew-no-pkg", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="package.*required.*brew"):
            load_bootstrap_profile("brew-no-pkg", profiles_dir=tmp_profile_dir)

    def test_reject_missing_package_for_apt(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """install: apt requires a package name."""
        minimal_profile_data["system_deps"] = [{"name": "foo", "check": "foo", "install": "apt"}]
        write_profile("apt-no-pkg", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="package.*required.*apt"):
            load_bootstrap_profile("apt-no-pkg", profiles_dir=tmp_profile_dir)

    def test_reject_missing_check_for_non_none(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """install != none requires a check command to verify presence."""
        minimal_profile_data["system_deps"] = [{"name": "foo", "install": "brew", "package": "foo"}]
        write_profile("no-check", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="check.*required.*not 'none'"):
            load_bootstrap_profile("no-check", profiles_dir=tmp_profile_dir)

    def test_allow_missing_check_for_none(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """install: none does not require a check command."""
        minimal_profile_data["system_deps"] = [{"name": "nvidia-smi", "install": "none"}]
        write_profile("none-no-check", minimal_profile_data)

        profile = load_bootstrap_profile("none-no-check", profiles_dir=tmp_profile_dir)
        assert profile.system_deps[0].check is None

    @pytest.mark.parametrize("method", ["brew", "apt", "bundled", "script", "manual", "none"])
    def test_all_valid_install_methods_accepted(
        self, tmp_profile_dir, write_profile, minimal_profile_data, method
    ):
        """Every documented install method loads without error."""
        dep = {"name": "foo", "install": method}
        if method in ("brew", "apt"):
            dep["package"] = "foo-pkg"
        if method != "none":
            dep["check"] = "foo --version"
        minimal_profile_data["system_deps"] = [dep]
        write_profile(f"method-{method}", minimal_profile_data)

        profile = load_bootstrap_profile(f"method-{method}", profiles_dir=tmp_profile_dir)
        assert profile.system_deps[0].install == method


# ---------------------------------------------------------------------------
# Docker service validation
# ---------------------------------------------------------------------------


class TestDockerServiceValidation:
    """Catch healthcheck type and required field misconfigurations."""

    def test_reject_invalid_healthcheck(self, tmp_profile_dir, write_profile, minimal_profile_data):
        """Invalid healthcheck type is caught (e.g., 'ping')."""
        minimal_profile_data["docker_services"] = [{"name": "db", "healthcheck": "ping"}]
        write_profile("bad-hc", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="invalid healthcheck 'ping'"):
            load_bootstrap_profile("bad-hc", profiles_dir=tmp_profile_dir)

    def test_reject_http_without_endpoint(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """healthcheck: http requires an endpoint URL."""
        minimal_profile_data["docker_services"] = [{"name": "api", "healthcheck": "http"}]
        write_profile("http-no-ep", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="endpoint.*required.*http"):
            load_bootstrap_profile("http-no-ep", profiles_dir=tmp_profile_dir)

    def test_reject_tcp_without_port(self, tmp_profile_dir, write_profile, minimal_profile_data):
        """healthcheck: tcp requires a port number."""
        minimal_profile_data["docker_services"] = [{"name": "db", "healthcheck": "tcp"}]
        write_profile("tcp-no-port", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="port.*required.*tcp"):
            load_bootstrap_profile("tcp-no-port", profiles_dir=tmp_profile_dir)


# ---------------------------------------------------------------------------
# Ollama model validation
# ---------------------------------------------------------------------------


class TestOllamaModelValidation:
    """Catch model requirement schema errors."""

    def test_exact_model_requirement(self, tmp_profile_dir, write_profile, minimal_profile_data):
        """Exact model parsed as OllamaModelExact with correct fields."""
        minimal_profile_data["ollama_models"] = [{"name": "qwen2.5:7b", "required": True}]
        write_profile("exact-model", minimal_profile_data)
        profile = load_bootstrap_profile("exact-model", profiles_dir=tmp_profile_dir)

        model = profile.ollama_models[0]
        assert isinstance(model, OllamaModelExact)
        assert model.name == "qwen2.5:7b"
        assert model.required is True

    def test_required_one_of_model(self, tmp_profile_dir, write_profile, minimal_profile_data):
        """Alternative model set parsed as OllamaModelAlternative."""
        minimal_profile_data["ollama_models"] = [
            {"required_one_of": ["qwen2.5:72b", "qwen2.5:32b"], "tier": "large"}
        ]
        write_profile("alt-model", minimal_profile_data)
        profile = load_bootstrap_profile("alt-model", profiles_dir=tmp_profile_dir)

        model = profile.ollama_models[0]
        assert isinstance(model, OllamaModelAlternative)
        assert model.required_one_of == ["qwen2.5:72b", "qwen2.5:32b"]
        assert model.tier == "large"

    def test_reject_model_without_name_or_alternatives(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """Model entry with neither name nor required_one_of is rejected."""
        minimal_profile_data["ollama_models"] = [{"required": True}]
        write_profile("no-model-id", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="name.*required"):
            load_bootstrap_profile("no-model-id", profiles_dir=tmp_profile_dir)

    def test_reject_empty_required_one_of(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """required_one_of must be a non-empty list."""
        minimal_profile_data["ollama_models"] = [{"required_one_of": []}]
        write_profile("empty-alt", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="required_one_of.*non-empty"):
            load_bootstrap_profile("empty-alt", profiles_dir=tmp_profile_dir)


# ---------------------------------------------------------------------------
# Profile listing
# ---------------------------------------------------------------------------


class TestListProfiles:
    """Catch missing or incorrectly discovered profile files."""

    def test_list_profiles(self, tmp_profile_dir, write_profile, minimal_profile_data):
        """Returns sorted names of YAML files in the profiles directory."""
        write_profile("beta", minimal_profile_data)
        write_profile("alpha", minimal_profile_data)

        profiles = list_bootstrap_profiles(profiles_dir=tmp_profile_dir)
        assert profiles == ["alpha", "beta"]

    def test_list_profiles_empty_dir(self, tmp_path):
        """Returns empty list for a directory with no YAML files."""
        empty = tmp_path / "empty"
        empty.mkdir()
        assert list_bootstrap_profiles(profiles_dir=empty) == []

    def test_list_profiles_nonexistent_dir(self, tmp_path):
        """Returns empty list when directory does not exist."""
        assert list_bootstrap_profiles(profiles_dir=tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# Profile not found
# ---------------------------------------------------------------------------


class TestProfileNotFound:
    """Catch clear error when profile YAML file is missing."""

    def test_nonexistent_profile(self, tmp_profile_dir):
        """Missing profile gives a clear error with available alternatives."""
        with pytest.raises(BootstrapProfileError, match="not found"):
            load_bootstrap_profile("nonexistent", profiles_dir=tmp_profile_dir)


# ---------------------------------------------------------------------------
# Real profile loading — validates the shipped YAML files
# ---------------------------------------------------------------------------


class TestRealProfiles:
    """Catch regressions in the three shipped bootstrap profile YAML files."""

    def test_load_dev_mac_profile(self):
        """dev-mac.yaml loads without error and has expected structure."""
        profile = load_bootstrap_profile("dev-mac")
        assert profile.name == "dev-mac"
        assert profile.platform.os == "darwin"
        assert profile.python.manager == "pyenv"
        assert len(profile.system_deps) >= 4
        assert len(profile.docker_services) >= 6
        assert len(profile.ollama_models) >= 3
        assert profile.deployment_profile == "local"

    def test_load_dev_pc_profile(self):
        """dev-pc.yaml loads without error and has expected structure."""
        profile = load_bootstrap_profile("dev-pc")
        assert profile.name == "dev-pc"
        assert profile.platform.os == "linux"
        assert profile.platform.distro == "ubuntu"
        assert profile.python.manager == "pyenv"
        assert profile.deployment_profile == "local"

    def test_load_local_spark_profile(self):
        """local-spark.yaml loads without error and has expected structure."""
        profile = load_bootstrap_profile("local-spark")
        assert profile.name == "local-spark"
        assert profile.platform.os == "linux"
        assert profile.platform.distro_min_version == "24.04"
        assert profile.python.manager == "system"
        assert profile.deployment_profile == "staging"

        # Spark has GPU deps
        gpu_deps = [d for d in profile.system_deps if "nvidia" in d.name]
        assert len(gpu_deps) == 2
        assert all(d.install == "none" for d in gpu_deps)

        # Spark has large models
        assert len(profile.ollama_models) >= 4


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Catch malformed YAML and type errors."""

    def test_reject_non_mapping_yaml(self, tmp_profile_dir):
        """YAML that parses to a list/string instead of dict is rejected."""
        path = tmp_profile_dir / "bad.yaml"
        path.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(BootstrapProfileError, match="must be a YAML mapping"):
            load_bootstrap_profile("bad", profiles_dir=tmp_profile_dir)

    def test_reject_invalid_yaml_syntax(self, tmp_profile_dir):
        """Malformed YAML is caught with a parse error."""
        path = tmp_profile_dir / "broken.yaml"
        path.write_text("name: [unclosed", encoding="utf-8")

        with pytest.raises(BootstrapProfileError, match="Failed to parse"):
            load_bootstrap_profile("broken", profiles_dir=tmp_profile_dir)

    def test_reject_invalid_python_manager(
        self, tmp_profile_dir, write_profile, minimal_profile_data
    ):
        """Invalid python.manager value is rejected."""
        minimal_profile_data["python"]["manager"] = "conda"
        write_profile("bad-mgr", minimal_profile_data)

        with pytest.raises(BootstrapProfileError, match="invalid python.manager 'conda'"):
            load_bootstrap_profile("bad-mgr", profiles_dir=tmp_profile_dir)

    def test_frozen_dataclass(self):
        """BootstrapProfile is immutable."""
        profile = load_bootstrap_profile("dev-mac")
        with pytest.raises(AttributeError):
            profile.name = "changed"
