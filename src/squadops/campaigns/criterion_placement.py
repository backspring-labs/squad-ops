"""Where a criterion's own test file goes on a repository-backed Project (SIP-0109 §24bv point 5).

On a sample application the stack places it (``scaffold.criterion_test_path``). A product has no
stack, so the file is placed under the product's own test runners, as the derived profile reads
them (SIP-0112 H.6, contract 8):
- **the runner** is the first, in the profile's order, whose ``covers`` holds every product path
  the criterion exercises: its own ``paths``, or the footprint's when it names none;
- **the file** lies under that runner's first root, named by its ``file_pattern``, with the
  criterion's id where the pattern's first ``*`` stands. A pattern's second ``*`` is the file's
  extension, which the product's own test files under the runner give (``*.test.*`` over
  ``harness.test.jsx`` is ``criterion_T1.test.jsx``);
- **refused, named,** when no runner covers the paths, or every runner that does can't host one:
  it can't be scoped to one file (``runner_not_scopable``), its pattern names no single file, its
  extension can't be read from any test file it holds, or the file it would place is a product
  file already.

Placement has two halves. ``runner_placements`` reads each runner's template from the profile and
the tree at the head, runtime-side, where the tree is. ``place_criterion`` places one criterion
from those templates, in the proposal's rails, which run where the change request is authored.
The placed path is stored in the change request (``criterion_files``), so every reader after the
proposal reads the one placement, never placing again.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import Any

#: The stem every placed criterion file takes, before the id: a product's own test files never
#: start with it by convention, so a placed file is told from the product's by its name.
CRITERION_STEM = "criterion_"
#: The placeholder a runner's template names the criterion by.
_CRITERION = "{criterion}"
#: The gap contract 8 names for a runner that can't be scoped to one file (H.6).
_NOT_SCOPABLE = "runner_not_scopable"


class Unplaceable(ValueError):
    """A criterion no runner of the product can host, with why."""


@dataclass(frozen=True)
class RunnerPlacement:
    """One runner, as a criterion is placed under it: its template, or why it can host none."""

    runner: str
    checks: tuple[str, ...]
    covers: tuple[str, ...]
    #: ``<root>/<file name>`` with ``{criterion}`` for the criterion's id, or ``None``.
    template: str | None
    refused: str | None = None
    #: The product's files the template would name for some id: never overwritten.
    taken: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "runner": self.runner,
            "checks": list(self.checks),
            "covers": list(self.covers),
            "template": self.template,
            "refused": self.refused,
            "taken": list(self.taken),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> RunnerPlacement:
        return cls(
            runner=str(raw["runner"]),
            checks=tuple(str(c) for c in raw.get("checks") or ()),
            covers=tuple(str(c) for c in raw.get("covers") or ()),
            template=None if raw.get("template") is None else str(raw["template"]),
            refused=None if raw.get("refused") is None else str(raw["refused"]),
            taken=tuple(str(t) for t in raw.get("taken") or ()),
        )

    def covers_all(self, paths: Iterable[str]) -> bool:
        listed = tuple(paths)
        return bool(listed) and all(_covered(p, self.covers) for p in listed)


def runner_placements(
    runners: Iterable[Any], gaps: Iterable[Any], tree_paths: Iterable[str]
) -> tuple[RunnerPlacement, ...]:
    """Each runner of a derived profile (``Runner``s, in its order) with the template a criterion
    file takes under it, read against ``tree_paths``, the head's tracked files. ``gaps`` are the
    profile's, read for ``runner_not_scopable``."""
    paths = tuple(tree_paths)
    unscopable = {g.subject for g in gaps if g.id == _NOT_SCOPABLE and g.subject}
    out = []
    for r in runners:
        base = dict(runner=r.runner, checks=tuple(r.checks), covers=tuple(r.covers))
        if r.single_file_argv is None or unscopable & {r.runner, *r.checks}:
            out.append(
                RunnerPlacement(
                    **base,
                    template=None,
                    refused=f"{r.runner} can't be run on one file ({_NOT_SCOPABLE}), so a "
                    "criterion's own test couldn't be run or frozen alone",
                )
            )
            continue
        try:
            template = _template(r, paths)
        except Unplaceable as e:
            out.append(RunnerPlacement(**base, template=None, refused=str(e)))
            continue
        taken = tuple(sorted(p for p in paths if fnmatch(p, template.replace(_CRITERION, "*"))))
        out.append(RunnerPlacement(**base, template=template, taken=taken))
    return tuple(out)


def _template(runner: Any, paths: tuple[str, ...]) -> str:
    pattern = str(runner.file_pattern)
    if any(c in pattern for c in "?[]") or not 1 <= pattern.count("*") <= 2:
        raise Unplaceable(
            f"{runner.runner}'s file pattern {pattern!r} names no single file a criterion's test "
            "could take"
        )
    head, _, rest = pattern.partition("*")
    name = f"{head}{CRITERION_STEM}{_CRITERION}{rest}"
    if "*" in rest:
        extension = _extension(runner, pattern, paths)
        name = name.replace("*", extension, 1)
    root = str(runner.roots[0]) if runner.roots else "."
    return name if root in (".", "") else f"{root.rstrip('/')}/{name}"


def _extension(runner: Any, pattern: str, paths: tuple[str, ...]) -> str:
    """The extension the runner's own test files take, where its pattern leaves it open: the most
    common among the files it holds, the first by name on a tie."""
    shape = re.compile(
        "^" + "(.+)".join(re.escape(part) for part in pattern.split("*")) + "$", re.DOTALL
    )
    seen = Counter(
        match.group(2)
        for p in paths
        if runner.holds(p) and (match := shape.match(PurePosixPath(p).name))
    )
    if not seen:
        raise Unplaceable(
            f"{runner.runner} holds no test file of the product's to read a criterion test's "
            f"extension from (its pattern {pattern!r} leaves it open)"
        )
    count = max(seen.values())
    return sorted(e for e, n in seen.items() if n == count)[0]


def place_criterion(
    criterion_id: str, paths: Iterable[str], placements: Iterable[RunnerPlacement]
) -> str:
    """The criterion's own test file: under the first runner that covers every one of ``paths``
    and can host one. Raises ``Unplaceable`` naming why, never placing by guess."""
    listed = tuple(paths)
    if not listed:
        raise Unplaceable(
            f"criterion {criterion_id} exercises no product path: name its paths, or the "
            "footprint's, so the runner that tests them can be chosen"
        )
    candidates = [p for p in placements if p.covers_all(listed)]
    if not candidates:
        covers = "; ".join(f"{p.runner} tests {', '.join(p.covers)}" for p in placements)
        raise Unplaceable(
            f"criterion {criterion_id}: no runner's tests cover {', '.join(listed)} "
            f"({covers or 'the product declares no runner'})"
        )
    reasons = []
    for p in candidates:
        if p.template is None:
            reasons.append(str(p.refused))
            continue
        path = p.template.replace(_CRITERION, _module_safe(criterion_id))
        if path in p.taken:
            reasons.append(f"{path} is a file of the product's already, never overwritten")
            continue
        return path
    raise Unplaceable(f"criterion {criterion_id}: " + "; ".join(reasons))


def _module_safe(criterion_id: str) -> str:
    """The id kept to letters, digits and ``_``, as ``scaffold.criterion_test_path`` keeps it, so
    the file is a valid module name on every runner."""
    return re.sub(r"[^A-Za-z0-9_]", "_", criterion_id)


def _covered(path: str, covers: Iterable[str]) -> bool:
    """Whether product path (or glob) ``path`` lies inside one of ``covers``: its literal part,
    before any wildcard, is the cover or under it. A cover of ``.`` holds the whole tree."""
    literal = re.split(r"[*?\[]", path, maxsplit=1)[0].rstrip("/")
    for cover in covers:
        c = cover.rstrip("/")
        if c in (".", ""):
            return True
        if literal == c or literal.startswith(c + "/"):
            return True
    return False
