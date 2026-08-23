"""Containment findings for emitted application source — #1055, reporting-only.

The sibling of ``additive_containment`` (#1052), which judges author-written TEST
files. This judges the route handlers the developer fills.

**The defect, and the correction that produced this module.** Arm A of the 2026-08-23
paired validation (`cyc_181c9572bef2`) failed every count assertion in its scaffold
shells — ``expected […] to have a length of 1 but got 2``, then ``got 3``. The lead
diagnosed *"route handlers instantiating a local shadow store instead of importing the
scaffold-provided global"*, and this module was first written to detect that. It found
nothing, because every route file in that roll imports the frozen store and holds no
module state. The diagnosis was wrong — the #968 class, an analyzer claim nobody
checked against the source.

The real defect is one line:

    const run = find(TABLES.Run, params.run_id)
    participants.push(name)
    insert(TABLES.Run, {...run, participants})   # appends a SECOND row

``insert`` is ``push``. Join adds a row and leave adds another, which is exactly the
observed drift. Same symptom the shadow-store story predicted, entirely different
cause — and a repair telling the developer to import the frozen store could never have
fixed it, because the handler already does.

**This is a scaffold gap before it is a developer defect.** The frozen store's whole
API is ``reset, all, insert, find, nextId``: there is no update seam. "Persist a change
to an existing row" has no correct form. The working answer — mutate the object
``find`` returned and never call ``insert`` — is non-obvious, and the natural-looking
answer silently duplicates. Adding an ``update`` seam is the root fix; it moves
``GENERATOR_VERSION`` and the Gate 1 fixture, so it is an owner call, not a drive-by.

**Reporting-only**, as ``additive_containment`` is, and for the same reason: #1049 was
a rejection gate whose premise had quietly stopped being true and it cost re-rolls on
every cycle before anyone noticed. Findings are banked so a gate can be argued from
what they flag on real rolls.

**Prevalence, measured rather than assumed** (three banked rolls, join/leave handlers):
arm A used ``insert``-as-update in 2 files; arm B (3.8) and the banked green roll used
in-place mutation in every handler. So this is a real trap and NOT a universal one —
worth naming when it appears, not worth blocking on.

*Follow-up worth naming:* this and ``additive_containment`` are one concern —
containment findings over emitted bytes — split across two modules only because the
second landed while the first was in review. Merging them is a cleanup, not a
behaviour change, and should happen before a third arrives.
"""

from __future__ import annotations

import re

#: A read of one row followed by an ``insert`` into the SAME table — the append-only
#: store's insert-as-update trap. Matched as a pair rather than on ``insert`` alone:
#: a handler that inserts a genuinely new row (create) is correct and must never flag,
#: and it is the ``find`` that makes the later insert a duplicate rather than a create.
_FIND_RE = re.compile(r"\bfind\s*\(\s*TABLES\.(\w+)")
_INSERT_RE = re.compile(r"\binsert\s*\(\s*TABLES\.(\w+)")

#: Route handlers only. A page or a lib file is a different question.
_ROUTE_RE = re.compile(r"(?:^|/)route\.(?:ts|tsx|js)$")


def is_route_module(path: str) -> bool:
    """Whether *path* is a route handler this pass judges."""
    return bool(_ROUTE_RE.search(path))


def assess_source_containment(files: list[dict]) -> list[str]:
    """Insert-as-update findings for the route handlers in an emission (empty = clean).

    ``files`` is the emission's artifact shape (``{"name", "content"}``). Pure, so the
    banked evidence today and any later gate read the same rule.
    """
    findings: list[str] = []
    for f in sorted(files, key=lambda a: str(a.get("name", ""))):
        path = str(f.get("name") or "")
        content = f.get("content")
        if not is_route_module(path) or not isinstance(content, str):
            continue
        read_tables = set(_FIND_RE.findall(content))
        for table in sorted(set(_INSERT_RE.findall(content)) & read_tables):
            findings.append(
                f"{path}: reads `TABLES.{table}` with find() and then calls "
                f"insert(TABLES.{table}) — insert is append-only, so this stores a "
                f"SECOND row rather than updating the one it read. Mutate the object "
                f"find() returned; the frozen store has no update seam "
                f"(arm A, cyc_181c9572bef2)."
            )
    return findings
