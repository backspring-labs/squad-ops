"""Docker container adapter.

Implementation of ContainerPort for Docker.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from __future__ import annotations

import asyncio
from typing import Any

from squadops.ports.tools.container import ContainerPort
from squadops.tools.exceptions import ToolContainerError
from squadops.tools.models import ContainerResult, ContainerSpec

# #158: default timeout for the docker daemon health probe (`docker info`).
_DEFAULT_HEALTH_TIMEOUT = 5.0


class DockerAdapter(ContainerPort):
    """Docker container adapter.

    Implements ContainerPort for Docker container operations.
    Uses docker CLI for simplicity; could be replaced with docker-py.
    """

    def __init__(
        self,
        docker_host: str | None = None,
        health_timeout_seconds: float = _DEFAULT_HEALTH_TIMEOUT,
    ):
        """Initialize Docker adapter.

        Args:
            docker_host: Optional Docker host URL (uses DOCKER_HOST env if not set)
            health_timeout_seconds: Timeout for the daemon health probe (#158).
        """
        self._docker_host = docker_host
        self._health_timeout = health_timeout_seconds

    async def _run_docker(
        self,
        *args: str,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        """Run docker command.

        Args:
            *args: Docker command arguments
            timeout: Optional timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        cmd = ["docker"]
        if self._docker_host:
            cmd.extend(["-H", self._docker_host])
        cmd.extend(args)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )

            return (
                proc.returncode or 0,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
            )
        except TimeoutError as e:
            raise ToolContainerError(f"Docker command timed out after {timeout}s") from e
        except Exception as e:
            raise ToolContainerError(f"Docker command failed: {e}") from e

    @staticmethod
    def _render_run_args(spec: ContainerSpec) -> list[str]:
        """Render a spec into `docker run` arguments (shared by foreground and
        detached runs)."""
        args: list[str] = []

        # Add environment variables
        for key, value in spec.env:
            args.extend(["-e", f"{key}={value}"])

        # Add volume mounts
        for host_path, container_path in spec.volumes:
            args.extend(["-v", f"{host_path}:{container_path}"])

        # Add working directory
        if spec.working_dir:
            args.extend(["-w", spec.working_dir])

        # Hardening flags (SIP-0102): emitted only when the spec sets them, so
        # pre-0102 callers keep byte-identical docker invocations.
        if spec.network is not None:
            args.extend(["--network", spec.network])
        if spec.memory_limit is not None:
            args.extend(["--memory", spec.memory_limit])
        if spec.cpu_limit is not None:
            args.extend(["--cpus", str(spec.cpu_limit)])
        if spec.pids_limit is not None:
            args.extend(["--pids-limit", str(spec.pids_limit)])
        if spec.cap_drop_all:
            args.extend(["--cap-drop", "ALL"])
        if spec.no_new_privileges:
            args.extend(["--security-opt", "no-new-privileges"])
        for port in spec.publish_ports:
            args.extend(["-p", f"127.0.0.1:0:{port}"])

        # Add image
        args.append(spec.image)

        # Add command
        if spec.command:
            args.extend(spec.command)

        return args

    async def run(self, spec: ContainerSpec) -> ContainerResult:
        """Run a container."""
        exit_code, stdout, stderr = await self._run_docker(
            "run",
            "--rm",
            *self._render_run_args(spec),
            timeout=spec.timeout_seconds,
        )

        return ContainerResult(
            container_id="",  # Container is removed after run (--rm)
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    async def run_detached(self, spec: ContainerSpec) -> str:
        """Start a container detached; returns its id."""
        exit_code, stdout, stderr = await self._run_docker(
            "run",
            "-d",
            "--rm",
            *self._render_run_args(spec),
            timeout=spec.timeout_seconds,
        )
        if exit_code != 0:
            raise ToolContainerError(f"Failed to start container: {stderr}")
        container_id = stdout.strip().splitlines()[-1] if stdout.strip() else ""
        if not container_id:
            raise ToolContainerError("docker run -d returned no container id")
        return container_id

    async def has_image(self, image: str) -> bool:
        """Whether the image exists locally (distinguishes absent from
        daemon-unreachable — only definitive absence returns False)."""
        exit_code, _stdout, stderr = await self._run_docker("image", "inspect", image)
        if exit_code == 0:
            return True
        if "no such image" in stderr.lower():
            return False
        raise ToolContainerError(f"Failed to inspect image: {stderr}")

    async def resolve_host_port(self, container_id: str, container_port: int) -> int:
        """Resolve a published container port to its ephemeral host port."""
        exit_code, stdout, stderr = await self._run_docker(
            "port", container_id, str(container_port)
        )
        if exit_code != 0:
            raise ToolContainerError(f"Failed to resolve port mapping: {stderr}")
        # Output shape: "127.0.0.1:49153" (possibly one line per protocol).
        for line in stdout.splitlines():
            host_part = line.strip().rsplit(":", 1)
            if len(host_part) == 2 and host_part[1].isdigit():
                return int(host_part[1])
        raise ToolContainerError(f"Unparseable port mapping output: {stdout!r}")

    async def stop(self, container_id: str) -> None:
        """Stop a running container."""
        exit_code, _, stderr = await self._run_docker("stop", container_id)
        if exit_code != 0:
            raise ToolContainerError(f"Failed to stop container: {stderr}")

    async def logs(self, container_id: str, tail: int | None = None) -> str:
        """Get container logs."""
        args = ["logs"]
        if tail is not None:
            args.extend(["--tail", str(tail)])
        args.append(container_id)

        exit_code, stdout, stderr = await self._run_docker(*args)
        if exit_code != 0:
            raise ToolContainerError(f"Failed to get logs: {stderr}")

        return stdout + stderr

    async def health(self) -> dict[str, Any]:
        """Check Docker daemon health."""
        try:
            exit_code, stdout, _ = await self._run_docker(
                "info", "--format", "{{.ServerVersion}}", timeout=self._health_timeout
            )
            return {
                "healthy": exit_code == 0,
                "docker_version": stdout.strip() if exit_code == 0 else None,
                "docker_host": self._docker_host or "default",
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "docker_host": self._docker_host or "default",
            }
