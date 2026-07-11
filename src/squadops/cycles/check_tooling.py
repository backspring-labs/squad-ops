"""Resolve which framework-check tooling a deployment provisions (SIP-0096 §6.3/§8).

The frontend build check needs Node, which #306 provisions in the **qa agent
image** via ``agents/instances/qa/system-packages.txt`` — not in runtime-api or
on the host. So availability cannot be probed with ``shutil.which``; the only
create-time-knowable signal is that provisioning **declaration**.

This resolver reads it. The same ``agents/instances/`` tree is COPY'd into the
runtime-api image *and* present on the host checkout, so create-time preflight
and ``squadops doctor`` resolve the same answer — the §8 parity requirement
("doctor's non-executable report agrees with runtime behavior"). When the
declarations can't be found, the resolver returns ``None`` so the pure decision
*warns rather than blocks* — never block on missing evidence.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from squadops.cycles.check_registry import TOOL_NODE

logger = logging.getLogger(__name__)

# apt package (as declared in a role's system-packages.txt) → the framework tool
# identifier used in the check registry's ``required_tooling``.
_PACKAGE_TO_TOOL: dict[str, str] = {
    "nodejs": TOOL_NODE,
    "npm": TOOL_NODE,
}


def _find_instances_dir() -> Path | None:
    """First existing ``agents/instances`` dir — container, local, or base-path.

    Mirrors ``entrypoint``'s instances.yaml lookup so the resolver agrees with
    where the roster actually lives in each runtime.
    """
    candidates = (
        Path("/app/agents/instances"),
        Path("agents/instances"),
        Path(os.getenv("SQUADOPS_BASE_PATH", ".")) / "agents/instances",
    )
    for path in candidates:
        if path.is_dir():
            return path
    return None


def resolve_provisioned_tooling(instances_dir: Path | None = None) -> frozenset[str] | None:
    """Framework tools provisioned across the deployment's agent roles.

    Unions ``system-packages.txt`` declarations across roles and maps them to
    tool identifiers. Returns:

    - a (possibly empty) set when the declarations were read — an empty/partial
      set is *verifiable absence* and blocks a required check that needs the tool;
    - ``None`` when the ``agents/instances`` tree can't be located — *unverifiable*,
      so the decision warns and allows.

    Union-across-roles answers "is this tool provisioned anywhere in the
    deployment"; today only the qa role declares Node and only qa runs the
    frontend check, so the union is exact. If a check ever needs role-precise
    tooling, the registry can carry the owning role.
    """
    root = instances_dir or _find_instances_dir()
    if root is None or not root.is_dir():
        logger.info("check_tooling_unresolved: agents/instances not found")
        return None

    tools: set[str] = set()
    for pkg_file in sorted(root.glob("*/system-packages.txt")):
        try:
            lines = pkg_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            pkg = raw.strip()
            if not pkg or pkg.startswith("#"):
                continue
            tool = _PACKAGE_TO_TOOL.get(pkg)
            if tool:
                tools.add(tool)
    return frozenset(tools)
