"""Execution factory wiring + parity guard (SIP-0102 — 102.1 slice d)."""

import pytest

from adapters.sandbox.factory import (
    create_execution_sandbox,
    create_sandbox_service,
    resolve_service_token,
)
from squadops.config.schema import SandboxConfig
from squadops.sandbox.noop import NoOpExecutionSandbox


def test_default_and_absent_config_yield_the_noop_sandbox(tmp_path):
    """THE parity guard: an unconfigured stack must get the NoOp sandbox —
    bug caught: default wiring quietly constructing a real backend, breaking
    the inert-to-merge guarantee on every deployed stack."""
    assert isinstance(create_execution_sandbox(None), NoOpExecutionSandbox)
    default = create_execution_sandbox(SandboxConfig(workspace_root=tmp_path))
    assert isinstance(default, NoOpExecutionSandbox)


def test_docker_provider_without_image_raises(tmp_path):
    """Bug caught: a fake-working default image masking missing config (the
    _get_default_instances lesson) — must surface the error instead."""
    config = SandboxConfig(provider="docker", workspace_root=tmp_path)
    with pytest.raises(ValueError, match="IMAGE is required"):
        create_sandbox_service(config)


def test_unknown_provider_raises(tmp_path):
    """Bug caught: a typo'd provider silently degrading to NoOp — the stack
    would believe the sandbox is on while everything runs in-process."""
    config = SandboxConfig(provider="dokcer", workspace_root=tmp_path)
    with pytest.raises(ValueError, match="Unknown sandbox provider"):
        create_sandbox_service(config)


def test_service_token_passthrough_for_plain_values(tmp_path):
    """Bug caught: token mangling on the non-secret path — every request
    would 401 against a service configured with the same literal."""
    config = SandboxConfig(workspace_root=tmp_path, service_token="tok-123")
    assert resolve_service_token(config) == "tok-123"
