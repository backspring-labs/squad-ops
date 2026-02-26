"""Tools domain models.

Frozen dataclasses for tool operations.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ContainerSpec:
    """Specification for running a container.

    Used with ContainerPort.run() to specify container configuration.
    """

    image: str
    command: list[str] | None = None
    env: tuple[tuple[str, str], ...] = ()
    volumes: tuple[tuple[str, str], ...] = ()  # (host_path, container_path)
    working_dir: str | None = None
    timeout_seconds: float = 300.0


# NOTE: Container volume host paths are NOT validated against PathSecurityPolicy in 0.8.7.
# This is an explicit deferral — container security is handled by Docker's own isolation.
# If host volume validation is needed, add PathValidatedContainerPort wrapper in 0.8.8.


@dataclass(frozen=True)
class ContainerResult:
    """Result of a container run.

    Returned from ContainerPort.run() with execution details.
    """

    container_id: str
    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class VCSStatus:
    """Status of a version-controlled repository.

    Returned from VersionControlPort.status() with repository state.
    """

    branch: str
    is_clean: bool
    modified_files: tuple[str, ...] = ()
    untracked_files: tuple[str, ...] = ()
    ahead: int = 0
    behind: int = 0
