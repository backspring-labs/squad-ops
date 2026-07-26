"""Execution sandbox adapters (SIP-0102)."""

from adapters.sandbox.container_backend import ContainerBackend
from adapters.sandbox.factory import (
    create_execution_sandbox,
    create_sandbox_service,
    resolve_service_token,
)
from adapters.sandbox.http_client import HttpExecutionSandbox, SandboxServiceError

__all__ = [
    "ContainerBackend",
    "SandboxServiceError",
    "HttpExecutionSandbox",
    "create_execution_sandbox",
    "create_sandbox_service",
    "resolve_service_token",
]
