"""Execution sandbox factory (SIP-0102 — phase 102.1 slice d).

Config-driven provider selection, same shape as the telemetry/registry
factories: the default is the NoOp sandbox (dormant, byte-identical
behavior); "docker" builds the container-backed service. Missing or unknown
configuration raises — never a fake-working default.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from adapters.execution.container_backend import ContainerBackend
from adapters.tools.docker import DockerAdapter
from squadops.config.schema import ExecutionConfig
from squadops.core.secrets import SecretManager
from squadops.execution.evidence import OperationEvidenceJournal
from squadops.execution.noop import NoOpExecutionSandbox
from squadops.execution.service import ExecutionService
from squadops.execution.workspace import WorkspaceStore
from squadops.ports.execution import ExecutionSandboxPort


def create_execution_service(
    config: ExecutionConfig,
    *,
    operation_commands: Mapping[str, tuple[str, ...]] | None = None,
) -> ExecutionService:
    """Build the service core for the configured provider.

    ``operation_commands`` comes from the environment contract (102.2); until
    it exists, a docker-backed service honestly reports execution operations
    as not-run ("environment provides no command").
    """
    root = Path(config.workspace_root)
    store = WorkspaceStore(root)
    journal = OperationEvidenceJournal(root)
    if config.provider == "noop":
        backend: ExecutionSandboxPort | None = None
    elif config.provider == "docker":
        if not config.image:
            raise ValueError(
                "SQUADOPS__EXECUTION__IMAGE is required for execution provider 'docker'"
            )
        backend = ContainerBackend(
            container=DockerAdapter(),
            store=store,
            image=config.image,
            operation_commands=operation_commands or {},
            app_port=config.app_port,
        )
    else:
        raise ValueError(f"Unknown execution provider: {config.provider}")
    return ExecutionService(store=store, journal=journal, backend=backend)


def create_execution_sandbox(config: ExecutionConfig | None) -> ExecutionSandboxPort:
    """The injectable port: NoOp unless explicitly configured (the parity
    guarantee — absent/default config ⇒ today's in-process behavior)."""
    if config is None or config.provider == "noop":
        return NoOpExecutionSandbox()
    return create_execution_service(config)


def resolve_service_token(
    config: ExecutionConfig, secret_manager: SecretManager | None = None
) -> str:
    """Resolve the service token, honoring secret:// references."""
    token = config.service_token
    if token.startswith("secret://"):
        if secret_manager is None:
            secret_manager = SecretManager()
        token = secret_manager.resolve(token)
    return token
