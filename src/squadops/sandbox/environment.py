"""Environment contract (SIP-0102 §4.2 — phase 102.2).

The pinned, deterministic declaration of the environment the canonical stack
builds and runs in: image identity, required tools, typed-operation commands,
runtime endpoint facts. The Dockerfile (``infra/sandbox/``) is an adapter
rendering of this contract, never the contract itself.

Deliberately registry-shaped but NOT generalized: the ``StackBlueprint``
schema is deferred until a second real stack exists
(SIP-Stack-Blueprint-Contract); this module holds the one canonical contract
and migrates into the blueprint when that SIP is accepted.

``contract_id()`` is a content hash over the canonical serialization — the
environment-contract identity every operation result records (§7 items 4/15).
Commands may use ``sh -c`` internally (the SIP permits adapters to run shell
underneath); the contract is checked in and never LLM-authored, so this is a
fixed rendering, not a shell surface.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from squadops.sandbox.models import OperationName


@dataclass(frozen=True)
class EnvironmentContract:
    """One stack's declared execution environment."""

    stack: str
    image: str
    required_tools: tuple[tuple[str, str], ...]  # (tool, expected major.minor prefix)
    operation_commands: tuple[tuple[str, tuple[str, ...]], ...]  # (operation, argv)
    app_port: int
    install_network: str

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for operation, argv in self.operation_commands:
            if operation not in OperationName.ALL:
                raise ValueError(f"unknown operation in environment contract: {operation!r}")
            if operation in seen:
                raise ValueError(f"duplicate operation in environment contract: {operation!r}")
            if not argv:
                raise ValueError(f"empty command for operation: {operation!r}")
            seen.add(operation)
        if not (0 < self.app_port < 65536):
            raise ValueError(f"invalid app_port: {self.app_port}")
        if not self.image:
            raise ValueError("environment contract requires an image")

    def commands(self) -> dict[str, tuple[str, ...]]:
        return dict(self.operation_commands)

    def provides(self, operation: str) -> bool:
        return any(op == operation for op, _ in self.operation_commands)

    def to_dict(self) -> dict:
        return {
            "stack": self.stack,
            "image": self.image,
            "required_tools": [list(pair) for pair in self.required_tools],
            "operation_commands": [
                {"operation": op, "argv": list(argv)} for op, argv in self.operation_commands
            ],
            "app_port": self.app_port,
            "install_network": self.install_network,
        }

    def contract_id(self) -> str:
        """Deterministic identity over the full declaration — any change to
        image, tools, or commands is a different contract (§7 items 4/15)."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# The canonical stack's contract (v1.4 floor). Paths are the expander's actual
# layout (coherence is test-enforced against a real expansion):
#   backend/requirements.txt, frontend/package.json (no lockfile → npm install),
#   uvicorn backend.main:app, pytest from the workspace root.
# read_build_diagnostics is deliberately unprovided — the warm-loop inspect
# step is 102.5's concern; unprovided operations are honest not_run.
FULLSTACK_FASTAPI_REACT = EnvironmentContract(
    stack="fullstack_fastapi_react",
    image="squadops-sandbox-env:fastapi-react-1.4-dev",
    required_tools=(("python", "3.12"), ("node", "20"), ("npm", "10")),
    # Dependencies install INTO the cycle workspace (§4.7: no shared installed
    # state; one-shot containers are disposable, the bind-mounted workspace is
    # not) — a venv for python, node_modules for npm. Both are derived state,
    # excluded from revision content by the workspace store. pytest/httpx are
    # harness deps (the scaffolded test harness), not app deps.
    operation_commands=(
        (
            OperationName.INSTALL_DEPENDENCIES,
            (
                "sh",
                "-c",
                "python -m venv .sandbox-venv"
                " && .sandbox-venv/bin/pip install -r backend/requirements.txt pytest httpx"
                " && npm --prefix frontend install",
            ),
        ),
        (OperationName.BUILD_FRONTEND, ("npm", "--prefix", "frontend", "run", "build")),
        (OperationName.RUN_BACKEND_TESTS, (".sandbox-venv/bin/python", "-m", "pytest", "-q")),
        (
            OperationName.START_APPLICATION,
            (
                ".sandbox-venv/bin/python",
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "0.0.0.0",  # noqa: S104 — inside the container; host publish is loopback-only
                "--port",
                "8000",
            ),
        ),
    ),
    app_port=8000,
    install_network="bridge",
)

# #822 stack #2. Same image family as stack #1 — the sandbox env already carries Node 20 and
# npm 10 for the frontend build, so no new language runtime enters the pipeline. What differs
# is every command: one project at the root instead of two trees, and a build step the
# application itself cannot start without.
NEXTJS_TS = EnvironmentContract(
    stack="nextjs_ts",
    image="squadops-sandbox-env:fastapi-react-1.4-dev",
    required_tools=(("node", "20"), ("npm", "10")),
    operation_commands=(
        (OperationName.INSTALL_DEPENDENCIES, ("npm", "ci", "--no-audit", "--no-fund")),
        (OperationName.BUILD_FRONTEND, ("npx", "next", "build")),
        (OperationName.RUN_BACKEND_TESTS, ("npx", "vitest", "run")),
        (
            OperationName.START_APPLICATION,
            (
                "npx",
                "next",
                "start",
                "--hostname",
                "0.0.0.0",  # noqa: S104 — inside the container; host publish is loopback-only
                "--port",
                "8000",
            ),
        ),
    ),
    app_port=8000,
    install_network="bridge",
)


_CONTRACTS: dict[str, EnvironmentContract] = {
    contract.stack: contract for contract in (FULLSTACK_FASTAPI_REACT, NEXTJS_TS)
}


def get_environment_contract(stack: str) -> EnvironmentContract:
    """The checked-in contract for a stack. Unknown stack raises — there is
    no fallback environment."""
    contract = _CONTRACTS.get(stack)
    if contract is None:
        raise ValueError(
            f"no environment contract for stack {stack!r} (known: {sorted(_CONTRACTS)})"
        )
    return contract
