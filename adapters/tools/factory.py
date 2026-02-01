"""Tools adapter factory.

Factory functions for creating tool adapters with security wrappers.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from adapters.tools.docker import DockerAdapter
from adapters.tools.git import GitAdapter, PathValidatedVCS
from adapters.tools.local_filesystem import (
    LocalFileSystemAdapter,
    PathValidatedFileSystem,
)
from squadops.ports.tools.container import ContainerPort
from squadops.ports.tools.filesystem import FileSystemPort
from squadops.ports.tools.vcs import VersionControlPort
from squadops.tools.security import PathSecurityPolicy

if TYPE_CHECKING:
    from squadops.core.secret_manager import SecretManager


def create_filesystem_provider(
    provider: str = "local",
    allowed_roots: tuple[Path, ...] | None = None,
    production_mode: bool = False,
    **config,
) -> FileSystemPort:
    """Create a filesystem provider.

    Args:
        provider: Provider name ("local")
        allowed_roots: Allowed root directories for path validation.
                       Required in production mode.
        production_mode: If True, requires allowed_roots
        **config: Additional provider-specific configuration

    Returns:
        FileSystemPort implementation (wrapped with path validation)

    Raises:
        ValueError: If provider is unknown or allowed_roots missing in production
    """
    if production_mode and not allowed_roots:
        raise ValueError("allowed_roots is required in production mode")

    if provider == "local":
        raw_adapter = LocalFileSystemAdapter()

        # Wrap with path validation if allowed_roots provided
        if allowed_roots:
            policy = PathSecurityPolicy(allowed_roots)
            return PathValidatedFileSystem(raw_adapter, policy)

        return raw_adapter

    raise ValueError(f"Unknown filesystem provider: {provider}")


def create_container_provider(
    provider: str = "docker",
    secret_manager: SecretManager | None = None,
    docker_host: str | None = None,
    **config,
) -> ContainerPort:
    """Create a container provider.

    Args:
        provider: Provider name ("docker")
        secret_manager: Optional secret manager for resolving secret:// refs
        docker_host: Docker host URL (may be secret:// ref)
        **config: Additional provider-specific configuration

    Returns:
        ContainerPort implementation

    Raises:
        ValueError: If provider is unknown
    """
    # Resolve secret:// refs via SecretManager (SIP §7.6)
    if secret_manager and docker_host and docker_host.startswith("secret://"):
        docker_host = secret_manager.resolve(docker_host[9:])

    if provider == "docker":
        return DockerAdapter(docker_host=docker_host)

    raise ValueError(f"Unknown container provider: {provider}")


def create_vcs_provider(
    provider: str = "git",
    allowed_roots: tuple[Path, ...] | None = None,
    production_mode: bool = False,
    **config,
) -> VersionControlPort:
    """Create a VCS provider.

    Args:
        provider: Provider name ("git")
        allowed_roots: Allowed root directories for repo path validation.
                       Required in production mode.
        production_mode: If True, requires allowed_roots
        **config: Additional provider-specific configuration

    Returns:
        VersionControlPort implementation (wrapped with path validation)

    Raises:
        ValueError: If provider is unknown or allowed_roots missing in production
    """
    if production_mode and not allowed_roots:
        raise ValueError("allowed_roots is required in production mode")

    if provider == "git":
        raw_adapter = GitAdapter()

        # Wrap with path validation if allowed_roots provided
        if allowed_roots:
            policy = PathSecurityPolicy(allowed_roots)
            return PathValidatedVCS(raw_adapter, policy)

        return raw_adapter

    raise ValueError(f"Unknown VCS provider: {provider}")
