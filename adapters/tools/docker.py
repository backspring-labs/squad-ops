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


class DockerAdapter(ContainerPort):
    """Docker container adapter.

    Implements ContainerPort for Docker container operations.
    Uses docker CLI for simplicity; could be replaced with docker-py.
    """

    def __init__(self, docker_host: str | None = None):
        """Initialize Docker adapter.

        Args:
            docker_host: Optional Docker host URL (uses DOCKER_HOST env if not set)
        """
        self._docker_host = docker_host

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

    async def run(self, spec: ContainerSpec) -> ContainerResult:
        """Run a container."""
        args = ["run", "--rm"]

        # Add environment variables
        for key, value in spec.env:
            args.extend(["-e", f"{key}={value}"])

        # Add volume mounts
        for host_path, container_path in spec.volumes:
            args.extend(["-v", f"{host_path}:{container_path}"])

        # Add working directory
        if spec.working_dir:
            args.extend(["-w", spec.working_dir])

        # Add image
        args.append(spec.image)

        # Add command
        if spec.command:
            args.extend(spec.command)

        exit_code, stdout, stderr = await self._run_docker(
            *args,
            timeout=spec.timeout_seconds,
        )

        return ContainerResult(
            container_id="",  # Container is removed after run (--rm)
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

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
                "info", "--format", "{{.ServerVersion}}", timeout=5.0
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
