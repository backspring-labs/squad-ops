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
    # Hardening surface (SIP-0102 §7 items 9–10). Defaults are inert — no flag
    # is emitted, preserving pre-0102 behavior for existing callers; the
    # execution sandbox sets these explicitly on every run.
    network: str | None = None
    memory_limit: str | None = None  # docker --memory syntax, e.g. "2g"
    cpu_limit: float | None = None
    pids_limit: int | None = None
    cap_drop_all: bool = False
    no_new_privileges: bool = False
    # uid:gid to run as (docker --user). None = image default. The sandbox sets
    # this to the workspace owner: with cap_drop_all, root loses DAC_OVERRIDE
    # and cannot write a host-owned bind mount on native Linux (Spark
    # shakedown finding, 2026-07-28); running as the owner needs no capability.
    user: str | None = None
    # Container ports to publish to loopback-only ephemeral host ports
    # (rendered as `-p 127.0.0.1:0:<port>`). Empty = nothing published.
    publish_ports: tuple[int, ...] = ()
    # The detached container's name (#2451 part 4): an app on the sandbox's app network is
    # addressed by it. None = a generated name; every detached container is named, so one whose
    # `docker run -d` timed out can still be found and removed.
    name: str | None = None
    # What a run-to-completion container reads on its standard input (SIP-0113 A3, #2416): the
    # evaluator's request, never on a mounted path. None = no input (`docker run` without `-i`).
    stdin: bytes | None = None
    # The program the container runs in place of its image's entrypoint (`docker run
    # --entrypoint`), ``command`` its arguments. None = the image's own. SIP-0109 §24co: a product's
    # pages are read by the evaluator image's own Chromium, as the qa role reads a sample
    # application's, and not by its driver, so the image and its measures' tag stay as they are.
    entrypoint: str | None = None


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
