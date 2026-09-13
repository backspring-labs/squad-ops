"""The comms factory imports where the A2A SDK is not installed (deploy B, 2026-09-11).

`requirements/agent.lock` ships `a2a-sdk`; `requirements/api.lock` does not, and has no
reason to — the runtime-api binds a queue and an A2A *client*, never an A2A server. #301
put all three factories in one module and imported `A2AServerAdapter` at module scope, so
`import adapters.comms.factory` raised `ModuleNotFoundError: No module named 'a2a'` inside
the runtime-api image.

What that cost: `_init_cycle_subsystem` catches `Exception` around the whole cycle-port
block, so the failure became one ERROR line. The container passed its health check, the
API answered every route, and `POST /api/v1/cycles` returned 500 —
`RuntimeError: ProjectRegistryPort not configured` — for as long as anyone cared to try.
Deploy B's first shakeout pair died on its first call, both arms.

**Why the #637 guard did not catch it.** That job imports `squadops.api.runtime.main`
under each lock, and main imports the comms factory *lazily*, inside
`_init_cycle_subsystem`. A bare module import never reaches the line. The guard is real
and its reach stops at import time — so this test asks the question one level in: not
"does the root import", but "does what the root's startup imports, import".
"""

from __future__ import annotations

import ast
import builtins
import importlib
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_adapters]

_REPO = Path(__file__).resolve().parents[3]
_FACTORY = _REPO / "adapters/comms/factory.py"

#: The distribution that provides `a2a`, and the lock that ships it. The runtime-api's
#: lock deliberately does not — an SDK it never calls has no business in that image.
_SDK_ROOT = "a2a"
_SHIPPED_BY = _REPO / "requirements/agent.lock"
_NOT_SHIPPED_BY = _REPO / "requirements/api.lock"


def _module_level_imports(path: Path) -> set[str]:
    """Top-level import targets only — the ones that run on `import <module>`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:  # body, not walk: a function-local import is the fix
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_the_factory_does_not_pull_the_a2a_sdk_at_module_scope():
    """Bug caught: an import that only one image can satisfy sits at module scope.

    Read from the tree rather than by importing, because the dev venv has the SDK — the
    import succeeds here and fails in the image, which is exactly how this shipped.
    """
    offenders = sorted(
        name
        for name in _module_level_imports(_FACTORY)
        if name.split(".")[0] == _SDK_ROOT or name == "adapters.comms.a2a_server"
    )
    assert offenders == [], (
        f"adapters/comms/factory.py imports {offenders} at module scope. The runtime-api "
        f"needs this module for its QUEUE, and its lock does not ship the A2A SDK — the "
        f"import makes the whole factory unimportable there. Import the server inside "
        f"create_a2a_server()."
    )


def test_the_factory_imports_with_the_sdk_unavailable():
    """The property itself, not a proxy for it: hide `a2a` and import the module.

    Stronger than the AST check above because it covers a transitive pull — a new
    module-scope import of something that *itself* imports the SDK reads clean to a
    name scan and fails identically in the image.
    """
    real_import = builtins.__import__

    def _no_sdk(name, *args, **kwargs):
        if name.split(".")[0] == _SDK_ROOT:
            raise ModuleNotFoundError(f"No module named {_SDK_ROOT!r}")
        return real_import(name, *args, **kwargs)

    dropped = {k: v for k, v in sys.modules.items() if k.split(".")[0] in (_SDK_ROOT, "adapters")}
    for key in dropped:
        del sys.modules[key]
    builtins.__import__ = _no_sdk
    try:
        module = importlib.import_module("adapters.comms.factory")
        assert callable(module.create_queue_adapter)
        assert callable(module.create_a2a_client)
        assert callable(module.create_a2a_server)
    finally:
        builtins.__import__ = real_import
        for key in [k for k in sys.modules if k.split(".")[0] in (_SDK_ROOT, "adapters")]:
            del sys.modules[key]
        sys.modules.update(dropped)


def test_the_lock_split_this_rests_on_is_still_the_split():
    """Bug caught: the premise silently stops being true.

    If `api.lock` gains `a2a-sdk` the local import is merely tidy rather than load-bearing,
    and the comment above it becomes a story about a constraint that no longer exists. If
    `agent.lock` LOSES it, the agent's A2A server is dead and this file is the wrong alarm
    but still the first one to ring.
    """
    agent = _SHIPPED_BY.read_text()
    api = _NOT_SHIPPED_BY.read_text()
    assert "a2a-sdk==" in agent, f"{_SHIPPED_BY.name} no longer ships the A2A SDK"
    assert "a2a-sdk==" not in api, (
        f"{_NOT_SHIPPED_BY.name} now ships the A2A SDK — the module-scope import is no "
        f"longer fatal, so revisit whether create_a2a_server's local import is still the "
        f"right shape rather than leaving a comment about a constraint that is gone"
    )
