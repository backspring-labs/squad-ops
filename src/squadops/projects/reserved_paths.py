"""The paths a product's owner reserves from a cycle's change (SIP-0112 H.35, #3155).

A product declares them in its Development Configuration (``technical.reserved_paths``), and they
are carried on its derived profile. A cycle writes none of them: a proposal whose footprint names
one, a plan whose task names one and a run whose change touches one are each refused, by path,
naming the entry that reserves it. The refusal is decided here, from the declaration and a path,
and never from what a model answered.

An entry is read one way everywhere:
- a **glob** (``src/Server/Data/*``, ``**/SaveConfig.luau``), matched against the whole
  repository-relative path, case kept. ``*`` is the one wildcard and crosses ``/``, as it does
  in a footprint and in every glob the derived profile holds. ``**/`` also stands for no folder
  at all, so ``**/SaveConfig.luau`` reserves that file at the root too. ``[`` and ``?`` are
  literal, so a bracketed directory is itself (#2512);
- a **path with no ``*``:** a file, or a directory and everything beneath it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from fnmatch import fnmatchcase

#: The one wildcard. Every other character of an entry is itself.
_WILDCARD = "*"
#: Entries that would reserve every file: a product no cycle may write is one no cycle runs on.
EVERYTHING = frozenset({"*", "**", "**/*", "*/**", ".", "./"})


def reserving(path: str, reserved: Sequence[str]) -> str | None:
    """The first entry of ``reserved`` that reserves repository-relative ``path``, or ``None``."""
    for entry in reserved:
        if _WILDCARD in entry:
            if any(fnmatchcase(path, glob) for glob in _globs(entry)):
                return entry
            continue
        directory = entry.rstrip("/")
        if path == directory or path.startswith(directory + "/"):
            return entry
    return None


def _globs(entry: str) -> tuple[str, ...]:
    """``entry`` as ``fnmatch`` reads it, with every character but ``*`` made literal: as
    written, and with each ``**/`` standing for no folder."""
    literal = entry.replace("[", "[[]").replace("?", "[?]")
    return tuple(dict.fromkeys((literal, literal.replace("**/", ""))))


def reached_by(footprint: Iterable[str], reserved: Sequence[str]) -> list[tuple[str, str]]:
    """Each entry of a change request's ``footprint`` (path globs) that reaches a reserved path,
    with the reserved entry it reaches, in the footprint's order. An entry reaches one when:
    - read as a path, it is reserved: a file an entry reserves, or a glob inside a reserved
      directory (``src/Server/Data/**`` under ``src/Server/Data``);
    - or a reserved entry with no wildcard lies inside it: ``src/**`` reaches
      ``src/Server/Data/ProfileSchema.luau``.

    A reserved glob and a footprint glob that only might share a file are not decided here: no
    tree is read. The plan's named files and the run's changed files are (``reserved_among``)."""
    found = []
    for entry in footprint:
        hit = reserving(entry, reserved)
        if hit is None:
            hit = next(
                (
                    r
                    for r in reserved
                    if _WILDCARD not in r and reserving(r.rstrip("/"), (entry,)) is not None
                ),
                None,
            )
        if hit is not None:
            found.append((entry, hit))
    return found


def reserved_among(paths: Iterable[str], reserved: Sequence[str]) -> list[tuple[str, str]]:
    """Each of ``paths`` an entry reserves, with that entry, in the paths' order."""
    found = []
    for path in paths:
        entry = reserving(path, reserved)
        if entry is not None:
            found.append((path, entry))
    return found


def naming(found: Sequence[tuple[str, str]]) -> str:
    """The reserved paths ``found``, each with the entry that reserves it, for a refusal."""
    return ", ".join(f"{path} ({entry})" if entry != path else path for path, entry in found)


def matches_none(reserved: Sequence[str], files: Iterable[str]) -> list[tuple[int, str]]:
    """Each entry of ``reserved`` that reserves no file of ``files``, with its index: an entry a
    typo would make, which would protect nothing."""
    listed = tuple(files)
    return [
        (i, entry)
        for i, entry in enumerate(reserved)
        if not any(reserving(path, (entry,)) for path in listed)
    ]
