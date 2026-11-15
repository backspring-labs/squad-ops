"""The isolation test SIP-0117 R4.6 commits to, shipped with the Studio adapter (#3039; R5.7).

1. **A platform's or provider's name appears only where R4.6 lets it:** the skillset directories,
   the development profile's entry, the squad profiles, the adapter directory and the worker
   root's configuration section. Everywhere else in the framework's code and configuration, the
   platform is a declaration it reads, never a name it branches on.
2. **The adapter imports only its port and an allowed list.** That list is the first draft of the
   interface a capability pack's provider will be written against (R4.6), so a new import is a
   decision about that interface, made here.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]

#: The names R4.6 confines: the platform's and its provider's (Studio's own MCP server's name with
#: it). ``luau`` is a language and isn't one of them.
CONFINED = re.compile(r"roblox|studiomcp", re.IGNORECASE)

#: Where the framework's code and configuration live, and so where the names are looked for.
SCANNED = ("src", "adapters", "config")

#: R4.6's places, each with the reason it may name the platform.
ALLOWED = {
    "src/squadops/skillsets": "the skillset directories",
    "src/squadops/stacks/development_profiles.py": "the development profile's entry",
    "config/squad-profiles.yaml": "the squad profiles",
    "adapters/remote_execution/game_dev_roblox_studio": "the adapter directory",
    "src/squadops/config/schema.py": "the worker root's configuration section (WorkerConfig)",
}

ADAPTER = REPO / "adapters" / "remote_execution" / "game_dev_roblox_studio"

#: What the adapter may import beyond the standard library and itself: its port, and the types
#: and vocabulary that port speaks.
ADAPTER_IMPORTS = (
    "squadops.ports.remote_execution",
    # SIP-0116 §17n (#3042): eligibility.py's port, the authority the root registers.
    "squadops.ports.tool_authority",
    "squadops.remote_execution.models",
    # #3040: the frozen scenario's schema and the vocabulary type the provider ships its own as.
    "squadops.remote_execution.scenario",
    "squadops.remote_execution.workers",
    "squadops.runtime.models",
)


def _allowed(relative: str) -> bool:
    return any(relative == a or relative.startswith(a + "/") for a in ALLOWED)


def _files():
    for root in SCANNED:
        for path in sorted((REPO / root).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                yield path


def test_a_platforms_name_appears_only_where_r4_6_lets_it():
    """Bug caught: orchestration branching on an engine's name (``if platform == "roblox"``), or
    a platform's vocabulary written into the framework's own code, so the next platform needs
    the framework changed rather than declared."""
    found = []
    for path in _files():
        relative = path.relative_to(REPO).as_posix()
        if _allowed(relative):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # a binary asset holds no code
        found += [
            f"{relative}:{n}: {line.strip()[:100]}"
            for n, line in enumerate(text.splitlines(), start=1)
            if CONFINED.search(line)
        ]

    assert found == [], "a platform's name outside R4.6's places:\n" + "\n".join(found)


def test_the_guard_finds_a_name_outside_its_places():
    """The guard's own check. Bug caught: a scan that reads nothing (a wrong root, a pattern that
    never matches) passing every tree."""
    assert any(_files())
    assert CONFINED.search('if provider == "Roblox-Studio":')
    assert not _allowed("src/squadops/cycles/task_plan.py")
    assert _allowed("adapters/remote_execution/game_dev_roblox_studio/session.py")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module)
    return found


@pytest.mark.parametrize("path", sorted(ADAPTER.glob("*.py")), ids=lambda p: p.name)
def test_the_adapter_imports_only_its_port_and_the_allowed_list(path):
    """Bug caught: the adapter reaching into orchestration (the executor, a cycle, the registry),
    so a provider can't be written against the port alone, as a capability pack's will be."""
    own = "adapters.remote_execution.game_dev_roblox_studio"
    outside = sorted(
        module
        for module in _imports(path)
        if module.split(".")[0] not in sys.stdlib_module_names
        and module != "__future__"
        and not module.startswith(own)
        and module not in ADAPTER_IMPORTS
    )

    assert outside == [], f"{path.name} imports {outside}, which the adapter's list doesn't hold"
