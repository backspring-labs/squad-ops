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


def test_docker_provider_is_contract_driven(tmp_path):
    """Bug caught: the backend constructed from ad-hoc config instead of the
    checked-in environment contract — commands/image/identity would drift
    from what §7 item 4 evidence claims."""
    from squadops.sandbox.environment import get_environment_contract

    contract = get_environment_contract("fullstack_fastapi_react")
    service = create_sandbox_service(SandboxConfig(provider="docker", workspace_root=tmp_path))
    backend = service._backend
    assert backend._image == contract.image
    assert backend._operation_commands == contract.commands()
    assert backend._environment_contract_id == contract.contract_id()


def test_config_image_override_wins_but_identity_stays_contract(tmp_path):
    """Bug caught: an image override silently ignored, or the override
    mutating the contract identity — the id must name the contract while the
    result's image_identity names what actually ran."""
    from squadops.sandbox.environment import get_environment_contract

    config = SandboxConfig(provider="docker", workspace_root=tmp_path, image="override:img")
    backend = create_sandbox_service(config)._backend
    assert backend._image == "override:img"
    contract = get_environment_contract("fullstack_fastapi_react")
    assert backend._environment_contract_id == contract.contract_id()


def test_unknown_environment_raises(tmp_path):
    """Bug caught: an unregistered stack silently degrading to some default
    environment instead of surfacing the gap at construction."""
    config = SandboxConfig(provider="docker", workspace_root=tmp_path, environment="nope")
    with pytest.raises(ValueError, match="no environment contract"):
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
