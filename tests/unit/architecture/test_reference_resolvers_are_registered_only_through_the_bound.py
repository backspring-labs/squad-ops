"""The runtime's resolver slot holds the bounded registry, and nothing in the runtime replaces it (#2575).

``ReferenceResolvers`` (``adapters.memory.reference_resolvers``) takes a family only through
``register``, which bounds it, and no item assignment. What it can't stop is code replacing the
whole slot: ``state.reference_resolvers = {...}`` after ``_init_memory`` would put every later
family outside the bound, and nothing would say so. The MacBook lane's G4 asked for a guard on exactly that ordering (a registration after
``_init_memory`` creates the slot).

What bug would this catch? A later init step, or #2565's registration, assigning the slot or an
item of it, so a family that hangs holds the campaign launcher's lock unbounded again. Tests build
their own worlds and are out of scope.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
#: An assignment to the slot, or to an item of it, on any object: never a keyword argument.
_ASSIGNMENT = re.compile(r"\.reference_resolvers\s*(\[[^\]]*\])?\s*=(?!=)")
#: The one assignment the runtime makes, in ``main._init_memory``.
_ALLOWED = (
    "src/squadops/api/runtime/main.py",
    "state.reference_resolvers = create_reference_resolvers(",
)


def _assignments() -> list[tuple[str, str]]:
    found = []
    for base in ("src", "adapters"):
        for path in sorted((ROOT / base).rglob("*.py")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if _ASSIGNMENT.search(line):
                    found.append((str(path.relative_to(ROOT)), line.strip()))
    return found


def test_the_only_assignment_to_the_resolver_slot_is_the_bounded_registry():
    found = _assignments()

    assert [(f, line) for f, line in found if not line.startswith(_ALLOWED[1])] == []
    assert found == [(_ALLOWED[0], f"{_ALLOWED[1]}")], found


def test_the_guard_sees_the_assignments_it_exists_to_refuse():
    """Against vacuity: the pattern matches both shapes of the bypass, and not a keyword argument."""
    assert _ASSIGNMENT.search("    state.reference_resolvers = {}")
    assert _ASSIGNMENT.search("    state.reference_resolvers[resolver.family] = resolver")
    assert not _ASSIGNMENT.search("    reference_resolvers=state.reference_resolvers,")
    assert not _ASSIGNMENT.search("    if state.reference_resolvers == other:")
