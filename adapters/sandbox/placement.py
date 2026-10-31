"""Where the sandbox runs an app, and how it reaches it (#2451 part 4; SIP-0102 §11h).

Inside a deploy the sandbox service is a container: an app published to the host's loopback is out
of its reach, and an app holding evaluation secrets must have no route out. So on the app network an
app runs under a name of its own with nothing published, and is reached by that name. Without one,
as on a host run, it publishes to loopback. The backend's runtime unit and the scenario runner's app
both run this way.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from squadops.ports.tools.container import ContainerPort
from squadops.tools.models import ContainerSpec


def placement(app_network: str | None, label: str, ports: tuple[int, ...]) -> dict[str, Any]:
    """The spec fields that place an app: on ``app_network`` under a fresh name, or ``ports``
    published to loopback."""
    if app_network is None:
        return {"publish_ports": ports}
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "-", label)[:40]
    return {"network": app_network, "name": f"squadops-app-{safe}-{uuid.uuid4().hex[:8]}"}


async def address(
    container: ContainerPort, container_id: str, spec: ContainerSpec, port: int
) -> tuple[str, int]:
    """The host and port the service reaches the app's ``port`` at: its name on the app network, or
    loopback's published port."""
    if spec.network is not None and spec.name:
        return spec.name, port
    return "127.0.0.1", await container.resolve_host_port(container_id, port)
