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

#: The one sandbox environment image, named for what it ships — Python 3.12, Node 20, npm 10
#: — and the SIP-0102 floor it implements, not for the stack that first needed it. Every
#: registered stack's contract pins this reference and `scripts/dev/build_sandbox_env_image.sh`
#: reads it from here, so the tag has exactly one source (#1197: the old tag,
#: `fastapi-react-1.4-dev`, named stack #1 while serving both stacks, and the name landed
#: verbatim in Next.js boot-audit evidence lines). The tag is part of every contract's
#: `contract_id()`, so changing it changes the contract hash on every stack — a deliberate
#: act at a point where a hash change is expected, never mid-set.
SANDBOX_ENV_IMAGE = "squadops-sandbox-env:py3.12-node20-1.4"

#: SIP-0113's evaluator image (A2, #2416): headless Chromium, Lighthouse and axe, and #1937's ruff
#: and ESLint, built from ``infra/evaluator`` by ``scripts/dev/build_evaluator_image.sh``, which
#: reads the tag from here. The tag is each quality measure's version, which the window records (the
#: 2.4 plan's §1.3), so it moves whenever the image's sources, or the lint config each request
#: carries, do: ``test_evaluator_image.py`` pins their digest to it.
EVALUATOR_IMAGE = "squadops-evaluator:lighthouse13.5-axe4.14-ruff0.16-eslint10.12-8"
#: The Chromium the evaluator image installs (its Dockerfile's ``CHROME_PATH``). SIP-0109 §24co: a
#: product's client routes are read by it directly, as the qa role reads a sample application's
#: (``route_rendering.DUMP_DOM_FLAGS``), so its driver, and the image's tag, are unchanged.
EVALUATOR_BROWSER = "/usr/bin/chromium"


@dataclass(frozen=True)
class EnvironmentContract:
    """One stack's declared execution environment."""

    stack: str
    image: str
    required_tools: tuple[tuple[str, str], ...]  # (tool, expected major.minor prefix)
    operation_commands: tuple[tuple[str, tuple[str, ...]], ...]  # (operation, argv)
    app_port: int
    install_network: str
    #: Where the running app serves its API, on ``app_port`` (#2421): ``""`` when at the root,
    #: as the canonical stack's backend serves ``/runs``, or a path, as Next.js serves its API
    #: routes under ``/api``. A held-out scenario names the PRD's paths, and the runner prefixes
    #: this, so one suite reaches the same job on either stack (SIP-0113 §10c).
    api_prefix: str
    #: Where the running app's pages are served, for Lighthouse and axe (SIP-0113 §4.2, #2416).
    #: ``app_port`` when the app serves them itself, as Next.js does.
    ui_port: int
    #: What serves the built pages beside the started app, from the workspace root, when the app
    #: doesn't: the canonical stack's backend serves only its API, so the build its setup made is
    #: served by Vite's preview, whose proxy reaches the same backend. Empty when the app serves
    #: its own pages. The instance the scenarios read is the one measured.
    ui_serve: tuple[str, ...]
    #: Whether this stack's BUILD writes into its own pinned source (SIP-0102 §11
    #: amendment). False — the canonical stack's assumption — means the live tree must
    #: keep matching its revision through every operation, and §4.6's pin verification
    #: holds throughout. True means the toolchain legitimately rewrites source during
    #: the build, so the post-build tree cannot match the pin and verifying after a
    #: build asserts something that was never true for this stack. Declared per stack,
    #: because it is a fact about the toolchain, not a policy choice.
    build_mutates_source: bool = False

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
        if not (0 < self.ui_port < 65536):
            raise ValueError(f"invalid ui_port: {self.ui_port}")
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
            "api_prefix": self.api_prefix,
            "ui_port": self.ui_port,
            "ui_serve": list(self.ui_serve),
            "install_network": self.install_network,
            "build_mutates_source": self.build_mutates_source,
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
    image=SANDBOX_ENV_IMAGE,
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
    api_prefix="",  # the backend serves the PRD's paths at the root; the Vite proxy adds /api
    # #2416: Vite's preview serves the build the setup made (``frontend/dist``), and proxies /api
    # to the backend as the dev server does. Read live on the Spark (2026-10-18): it refuses a
    # request whose Host is a name it doesn't know, so the evaluator addresses it by IP.
    ui_port=4173,
    ui_serve=(
        "frontend/node_modules/.bin/vite",
        "preview",
        "frontend",
        "--host",
        "0.0.0.0",  # noqa: S104 — inside the container, on the app network
        "--port",
        "4173",
        "--strictPort",
    ),
    install_network="bridge",
)

# #822 stack #2. Same image family as stack #1 — the sandbox env already carries Node 20 and
# npm 10 for the frontend build, so no new language runtime enters the pipeline. What differs
# is every command: one project at the root instead of two trees, and a build step the
# application itself cannot start without.
NEXTJS_TS = EnvironmentContract(
    stack="nextjs_ts",
    image=SANDBOX_ENV_IMAGE,
    required_tools=(("node", "20"), ("npm", "10")),
    operation_commands=(
        # `npm install`, NOT `npm ci` — the same correction the probe runner's
        # `nextjs_next_start` profile already carries (roll 10, cyc_43a216d43e1e), and the
        # rule stack #1's contract states three declarations above ("no lockfile → npm
        # install"). The scaffold emits no `package-lock.json` (an offline-deterministic
        # expansion cannot produce one) and `npm ci` EUSAGE-refuses without a lockfile, so
        # this operation could never succeed on this stack: the sandbox path was
        # unreachable-green by construction. Measured 2026-08-15 auditing the SIP-0104
        # window's roll 1 (cyc_04d36309d793), whose deliverable failed install here while
        # passing every probe on the runner's `npm install` path. Fixing one surface and
        # not its sibling is the #838 shape; both now match the vitest runner too.
        (OperationName.INSTALL_DEPENDENCIES, ("npm", "install", "--no-audit", "--no-fund")),
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
    api_prefix="/api",  # App Router API routes: app/api/runs/route.ts serves /api/runs
    ui_port=8000,  # `next start` serves the pages beside its API routes
    ui_serve=(),
    install_network="bridge",
    # Measured 2026-08-15 (SIP-0104 window roll 1): `next build` GENERATES
    # `next-env.d.ts` and REWRITES the scaffold's frozen `tsconfig.json`, injecting
    # `allowJs` and `skipLibCheck`. Both are documented Next behaviors, so no tree on
    # this stack can match its pin once a build has run.
    build_mutates_source=True,
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
