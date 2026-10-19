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

The finding is evidence for a decision. It moves nothing by itself: the development baseline
advances through validation, and the Development Configuration and inherited baseline are
recorded again at the new commit before a unit relies on them (``prepare_cycle`` refuses until
they are).
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from squadops.projects.checkout import GENERATED_LOCKFILES
from squadops.projects.development_configuration import (
    INSTRUCTION_FILES,
    DevelopmentConfiguration,
)

DRIFT_SCHEMA = "source-drift/v1"

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
class SourceDrift:
    project_id: str
    from_commit: str
    to_commit: str
    changed: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def relevant(self) -> list[str]:
        """The categories, other than the product's source, that changed: each invalidates
        evidence until it is reconciled and revalidated."""
        return [c for c in CATEGORIES if c != SOURCE and self.changed.get(c)]

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": DRIFT_SCHEMA,
            "project_id": self.project_id,
            "from_commit": self.from_commit,
            "to_commit": self.to_commit,
            "changed": {c: list(self.changed[c]) for c in CATEGORIES if self.changed.get(c)},
            "relevant": self.relevant,
        }


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


def drift_between(
    project_id: str,
    from_commit: str,
    to_commit: str,
    old: Mapping[str, bytes],
    new: Mapping[str, bytes],
    configuration: DevelopmentConfiguration,
) -> SourceDrift:
    """The drift from the approved baseline's tree to the upstream one, by category."""
    instructions = {s.path for s in configuration.instruction_sources} | set(INSTRUCTION_FILES)
    inputs = command_paths(configuration, old.keys() | new.keys())
    changed: dict[str, list[str]] = {}
    for path in changed_paths(old, new):
        category = classify(path, instructions=instructions, command_inputs=inputs)
        changed.setdefault(category, []).append(path)
    return SourceDrift(
        project_id=project_id,
        from_commit=from_commit,
        to_commit=to_commit,
        changed={c: tuple(paths) for c, paths in changed.items()},
    )
