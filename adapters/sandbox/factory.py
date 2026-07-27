"""Execution sandbox factory (SIP-0102 — phase 102.1 slice d).

Config-driven provider selection, same shape as the telemetry/registry
factories: the default is the NoOp sandbox (dormant, byte-identical
behavior); "docker" builds the container-backed service. Missing or unknown
configuration raises — never a fake-working default.
"""

from __future__ import annotations

from pathlib import Path

from adapters.sandbox.container_backend import ContainerBackend
from adapters.tools.docker import DockerAdapter
from squadops.config.schema import SandboxConfig
from squadops.core.secrets import SecretManager
from squadops.ports.sandbox import ExecutionSandboxPort
from squadops.sandbox.environment import get_environment_contract
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.noop import NoOpExecutionSandbox
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import WorkspaceStore


def create_sandbox_service(config: SandboxConfig) -> SandboxService:
    """Build the service core for the configured provider.

    The docker provider is driven entirely by the checked-in environment
    contract (§4.2): typed-operation commands, app port, install egress, and
    the pinned image (``config.image`` may override — the actually-used image
    rides every result as evidence), with the contract's identity stamped on
    every result (§7 item 4).
    """
    root = Path(config.workspace_root)
    store = WorkspaceStore(root)
    journal = OperationEvidenceJournal(root)
    if config.provider == "noop":
        backend: ExecutionSandboxPort | None = None
    elif config.provider == "docker":
        contract = get_environment_contract(config.environment)
        backend = ContainerBackend(
            container=DockerAdapter(),
            store=store,
            image=config.image or contract.image,
            operation_commands=contract.commands(),
            app_port=contract.app_port,
            install_network=contract.install_network,
            environment_contract_id=contract.contract_id(),
        )
    else:
        raise ValueError(f"Unknown sandbox provider: {config.provider}")
    return SandboxService(store=store, journal=journal, backend=backend)


def create_execution_sandbox(config: SandboxConfig | None) -> ExecutionSandboxPort:
    """The injectable port: NoOp unless explicitly configured (the parity
    guarantee — absent/default config ⇒ today's in-process behavior)."""
    if config is None or config.provider == "noop":
        return NoOpExecutionSandbox()
    return create_sandbox_service(config)


def resolve_service_token(
    config: SandboxConfig, secret_manager: SecretManager | None = None
) -> str:
    """Resolve the service token, honoring secret:// references."""
    token = config.service_token
    if token.startswith("secret://"):
        if secret_manager is None:
            secret_manager = SecretManager()
        token = secret_manager.resolve(token)
    return token
