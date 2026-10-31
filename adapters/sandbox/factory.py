"""Execution sandbox factory (SIP-0102 — phase 102.1 slice d).

Config-driven provider selection, same shape as the telemetry/registry
factories: the default is the NoOp sandbox (dormant, byte-identical
behavior); "docker" builds the container-backed service. Missing or unknown
configuration raises — never a fake-working default.
"""

from __future__ import annotations

from pathlib import Path

from adapters.sandbox.container_backend import ContainerBackend
from adapters.sandbox.scenario_runner import ContainerScenarioRunner
from adapters.tools.docker import DockerAdapter
from squadops.config.schema import SandboxClientConfig, SandboxConfig
from squadops.core.secrets import SecretManager
from squadops.ports.sandbox import ExecutionSandboxPort
from squadops.ports.scenarios import ScenarioRunnerPort
from squadops.sandbox.environment import EVALUATOR_IMAGE, get_environment_contract
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
        container = DockerAdapter()
        backend = ContainerBackend(
            container=container,
            store=store,
            image=config.image or contract.image,
            operation_commands=contract.commands(),
            app_port=contract.app_port,
            install_network=contract.install_network,
            environment_contract_id=contract.contract_id(),
            build_mutates_source=contract.build_mutates_source,
            cache_root=Path(config.cache_root) if config.cache_root else None,
            app_network=config.app_network,
        )
        # SIP-0113 §4.1, A3 (#2414): the scenario runner, beside the cycle's execution, on the same
        # image and posture. Each stack's environment contract starts a blueprint tree.
        runner = ContainerScenarioRunner(
            container=container,
            root=root,
            image=config.image or contract.image,
            install_network=contract.install_network,
            app_network=config.app_network,
            evaluator_image=EVALUATOR_IMAGE,
        )
        return SandboxService(
            store=store,
            journal=journal,
            backend=backend,
            environment_report=backend.environment_report,
            scenario_runner=runner,
        )
    else:
        raise ValueError(f"Unknown sandbox provider: {config.provider}")
    return SandboxService(store=store, journal=journal, backend=backend)


def create_execution_sandbox(config: SandboxConfig) -> ExecutionSandboxPort:
    """The injectable port. ``noop`` is the parity guarantee (today's in-process behavior),
    and it is named, never reached by an absent config (#1568)."""
    if config.provider == "noop":
        return NoOpExecutionSandbox()
    return create_sandbox_service(config)


def create_sandbox_client(config: SandboxClientConfig | None) -> ExecutionSandboxPort | None:
    """The runtime API's client of the sandbox service (#2451, the owner's ruling of 2026-10-18):
    one binding for every caller in the runtime API, SIP-0112's seeding and SIP-0113's runner
    alike. ``none`` is no client: each caller reads the sandbox as unavailable. An absent section
    is refused, since the selector is required where it is read (#1568)."""
    if config is None:
        raise ValueError(
            "the runtime API needs SQUADOPS__SANDBOX_CLIENT__PROVIDER (none | http): it is required "
            "where it is read (#1568, #2451)"
        )
    if config.provider == "none":
        return None
    from adapters.sandbox.http_client import HttpExecutionSandbox

    return HttpExecutionSandbox(
        base_url=config.service_url,
        service_token=config.service_token,
        command_timeout_seconds=config.command_timeout_seconds,
    )


def create_scenario_runner(config: SandboxClientConfig | None) -> ScenarioRunnerPort | None:
    """SIP-0113's runner in the runtime API (#2414), on the binding ``create_sandbox_client``
    reads: ``none`` is no runner, so each evaluation records ``no_runner``, and an absent section
    is refused the same way. Its own client only for the timeout an evaluation needs."""
    # ``config is None`` never reaches the second test: the first refuses it. It narrows the type.
    if create_sandbox_client(config) is None or config is None:
        return None
    from adapters.sandbox.http_client import HttpScenarioRunner

    return HttpScenarioRunner(base_url=config.service_url, service_token=config.service_token)


def resolve_service_token(config: SandboxConfig, secret_manager: SecretManager | None) -> str:
    """Resolve the service token, honoring secret:// references.

    ``secret_manager`` is required, and ``None`` only where no secrets provider is configured
    (#1982). This built ``SecretManager()`` itself when given none, which raises ``TypeError``
    (a manager needs a provider), so a ``secret://`` token failed the sandbox at startup.
    A reference with no manager to resolve it is refused with the reason.
    """
    token = config.service_token
    if token.startswith("secret://"):
        if secret_manager is None:
            raise ValueError(
                "the sandbox service token is a secret:// reference, and no secrets provider "
                "is configured to resolve it (set SQUADOPS__SECRETS__PROVIDER)"
            )
        token = secret_manager.resolve(token)
    return token
