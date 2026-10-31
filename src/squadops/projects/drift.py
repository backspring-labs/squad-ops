"""What changed upstream since a Project's approved development baseline (SIP-0112 FR-21, §B.5.1
drift detection; E.4.4).

An outside developer advances the product's repository. The next unit must not rely on a
Development Configuration or an inherited baseline validated against the older tree, so drift
detection names, path by path, what changed in the inputs that evidence depends on:
- the repository's instruction sources (SIP-0110 binds them; this SIP finds them);
- the declared commands' own inputs: a file a check, install, build or start argv names;
- dependency manifests and lockfiles;
- toolchain pins;
- the contribution policy (the files that say how a change is offered);
- everything else, the product's source.

Paths SquadOps's own integrated contributions account for are listed under each contribution, apart
from what changed outside it (#2606): a path a contribution changed, whose upstream content is still
what it wrote. One an outside developer changed again after it is outside drift. Both invalidate
evidence alike, so ``relevant`` reads both.

The finding is evidence for a decision. It moves nothing by itself: the development baseline
advances through validation, and the Development Configuration and inherited baseline are
recorded again at the new commit before a unit relies on them (``prepare_cycle`` refuses until
they are).
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from squadops.projects.checkout import GENERATED_LOCKFILES
from squadops.projects.development_configuration import (
    INSTRUCTION_FILES,
    DevelopmentConfiguration,
)

#: v2 (#2606): ``changed`` is what changed outside SquadOps; ``integrated`` lists its contributions'.
DRIFT_SCHEMA = "source-drift/v2"

INSTRUCTIONS = "instructions"
COMMAND_INPUTS = "command_inputs"
DEPENDENCIES = "dependencies"
TOOLCHAIN = "toolchain"
CONTRIBUTION_POLICY = "contribution_policy"
SOURCE = "source"
#: In the order a reader reconciles them: what the squad is told, how the product is checked,
#: what it is built from, how a change reaches it, then the product itself.
CATEGORIES = (INSTRUCTIONS, COMMAND_INPUTS, DEPENDENCIES, TOOLCHAIN, CONTRIBUTION_POLICY, SOURCE)

_DEPENDENCY_NAMES = (
    frozenset(
        {
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "Pipfile",
            "package.json",
            "Cargo.toml",
            "go.mod",
            "Gemfile",
            "composer.json",
        }
    )
    | GENERATED_LOCKFILES
)
_DEPENDENCY_PATTERNS = ("requirements*.txt", "requirements*.in", "constraints*.txt")
_TOOLCHAIN_NAMES = frozenset(
    {
        ".python-version",
        ".nvmrc",
        ".node-version",
        ".tool-versions",
        "runtime.txt",
        "rust-toolchain",
        "rust-toolchain.toml",
        "Dockerfile",
    }
)
_POLICY_NAMES = frozenset({"CONTRIBUTING.md", "CODEOWNERS", "PULL_REQUEST_TEMPLATE.md"})


@dataclass(frozen=True)
class ContributedChange:
    """An integrated contribution's change: its commit's tree and its parent's."""

    cycle_id: str
    run_id: str
    commit: str
    before: Mapping[str, bytes]
    after: Mapping[str, bytes]


@dataclass(frozen=True)
class IntegratedDrift:
    """The upstream paths one integrated contribution accounts for, by category."""

    cycle_id: str
    run_id: str
    commit: str
    changed: Mapping[str, tuple[str, ...]]

    def to_document(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "run_id": self.run_id,
            "commit": self.commit,
            "changed": _by_category(self.changed),
        }


@dataclass(frozen=True)
class SourceDrift:
    project_id: str
    from_commit: str
    to_commit: str
    #: What changed outside SquadOps, by category.
    changed: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: What SquadOps's integrated contributions account for, each apart.
    integrated: tuple[IntegratedDrift, ...] = ()

    @property
    def relevant(self) -> list[str]:
        """The categories, other than the product's source, that changed, outside SquadOps or
        through its contributions: each invalidates evidence until it is reconciled and
        revalidated."""
        changed = [self.changed, *(i.changed for i in self.integrated)]
        return [c for c in CATEGORIES if c != SOURCE and any(m.get(c) for m in changed)]

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": DRIFT_SCHEMA,
            "project_id": self.project_id,
            "from_commit": self.from_commit,
            "to_commit": self.to_commit,
            "changed": _by_category(self.changed),
            "integrated": [i.to_document() for i in self.integrated],
            "relevant": self.relevant,
        }


def _by_category(changed: Mapping[str, tuple[str, ...]]) -> dict[str, list[str]]:
    return {c: list(changed[c]) for c in CATEGORIES if changed.get(c)}


def changed_paths(old: Mapping[str, bytes], new: Mapping[str, bytes]) -> list[str]:
    """Every path added, removed or changed between two trees."""
    return sorted(p for p in old.keys() | new.keys() if old.get(p) != new.get(p))


def command_paths(configuration: DevelopmentConfiguration, files: Iterable[str]) -> set[str]:
    """The files the declared commands run or read by name: every argv element (or ``--flag=``
    value) that names a file in ``files``. A directory a command operates on (``tests``,
    ``src``) is the product, never a command input, so it doesn't count."""
    commands = configuration.commands
    argvs: list[tuple[str, ...]] = [c.argv for c in commands.checks]
    argvs += [*commands.install, *commands.build]
    if commands.start is not None:
        start = commands.start
        argvs += [start.start, *start.install, *start.build]
    tracked = set(files)
    named = set()
    for argv in argvs:
        for token in argv:
            value = token.split("=", 1)[-1] if token.startswith("-") else token
            normalized = str(PurePosixPath(value)) if value else ""
            if normalized in tracked:
                named.add(normalized)
    return named


def classify(path: str, *, instructions: Iterable[str], command_inputs: Iterable[str]) -> str:
    """The category a changed path falls in, first match in ``CATEGORIES`` order."""
    name = PurePosixPath(path).name
    if path in set(instructions):
        return INSTRUCTIONS
    if path in set(command_inputs):
        return COMMAND_INPUTS
    if name in _DEPENDENCY_NAMES or any(fnmatch.fnmatch(name, p) for p in _DEPENDENCY_PATTERNS):
        return DEPENDENCIES
    if name in _TOOLCHAIN_NAMES:
        return TOOLCHAIN
    if name in _POLICY_NAMES or path.startswith(".github/"):
        return CONTRIBUTION_POLICY
    return SOURCE


def accounted_for(
    new: Mapping[str, bytes], contributed: Sequence[ContributedChange]
) -> dict[str, ContributedChange]:
    """Each upstream path an integrated contribution accounts for: one it changed, whose upstream
    content is still what it wrote. A later contribution's claim on a path replaces an earlier
    one's; a path changed again since is nobody's here."""
    claims: dict[str, ContributedChange] = {}
    for change in contributed:
        for path in changed_paths(change.before, change.after):
            if new.get(path) == change.after.get(path):
                claims[path] = change
    return claims


def drift_between(
    project_id: str,
    from_commit: str,
    to_commit: str,
    old: Mapping[str, bytes],
    new: Mapping[str, bytes],
    configuration: DevelopmentConfiguration,
    *,
    contributed: Sequence[ContributedChange] = (),
) -> SourceDrift:
    """The drift from the approved baseline's tree to the upstream one, by category: what changed
    outside SquadOps, and what each of its integrated contributions (``contributed``, oldest
    first) accounts for."""
    instructions = {s.path for s in configuration.instruction_sources} | set(INSTRUCTION_FILES)
    inputs = command_paths(configuration, old.keys() | new.keys())
    claims = accounted_for(new, contributed)
    outside: dict[str, list[str]] = {}
    integrated: dict[str, dict[str, list[str]]] = {}
    for path in changed_paths(old, new):
        category = classify(path, instructions=instructions, command_inputs=inputs)
        claim = claims.get(path)
        into = outside if claim is None else integrated.setdefault(claim.commit, {})
        into.setdefault(category, []).append(path)
    return SourceDrift(
        project_id=project_id,
        from_commit=from_commit,
        to_commit=to_commit,
        changed={c: tuple(paths) for c, paths in outside.items()},
        integrated=tuple(
            IntegratedDrift(
                change.cycle_id,
                change.run_id,
                change.commit,
                {c: tuple(paths) for c, paths in integrated[change.commit].items()},
            )
            for change in contributed
            if change.commit in integrated
        ),
    )
