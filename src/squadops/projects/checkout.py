"""A source-backed run's view of the product's repository (SIP-0112 E.4.3).

A Cycle that pins an external Project's source starts from that product's tree at the pinned
commit, as a campaign increment starts from its accepted tree (SIP-0109 §7.3). Each tracked
file is seeded as the run's own starting content, so whatever the squad produces for a path wins
over it, and every other file is delivered as it was.

What a task sees of it is bounded. The squad gets five things, never a silently truncated tree:
- a map of every path;
- the product's own checks, which verify the change;
- its test runners, as the derived profile reads them (SIP-0112 H.4 point 3);
- the product's own instruction files;
- the current content of the files that task names.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

#: The producing task of a file seeded from the product's repository: provenance only, never a
#: dispatched task type.
SOURCE_CHECKOUT = "source.checkout"
#: The run's record of what it seeded: its commit, every path's size, and which are binary or
#: executable. An artifact type no context filter selects, so it never reaches a prompt itself.
CHECKOUT_MANIFEST_TYPE = "source_checkout"
CHECKOUT_MANIFEST_FILENAME = "source_checkout.json"

#: Generated dependency lockfiles. No task reads one and the product's own install writes it, so
#: it is held back as a binary file is: listed in the manifest, read from the clone, never seeded.
GENERATED_LOCKFILES = frozenset(
    {
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "bun.lock",
        "uv.lock",
        "poetry.lock",
        "Pipfile.lock",
        "Cargo.lock",
        "Gemfile.lock",
        "composer.lock",
        "go.sum",
    }
)
#: The artifact types an acceptance workspace selects, whatever produced them.
WORKSPACE_TYPES = ("source", "config")

#: 2.4's limits on a product a source-backed run takes on. The workspace cap is the seeded source
#: and config text, which every acceptance workspace (one 512 KB resolution) carries whole, with
#: room left for the squad's own files, so no task works from a truncated tree.
MAX_FILES = 2000
MAX_WORKSPACE_BYTES = 384 * 1024
#: How much current file content one task is shown in full.
FOCUS_BUDGET_BYTES = 96 * 1024
#: Beyond this many paths the map lists directories, with their file counts.
MAP_PATH_LIMIT = 400


class CheckoutTooLarge(ValueError):
    """A product past 2.4's limits for a source-backed run: refused by name, never truncated."""


@dataclass(frozen=True)
class RunnerView:
    """One of the product's test runners, as a task is shown it (SIP-0112 H.4 point 3, from the
    derived profile's ``test_runners``): where a test file goes so the product's checks run it."""

    runner: str
    #: The Development Configuration's checks that run it.
    checks: tuple[str, ...]
    #: Where it discovers tests, and the file names it takes as tests (an ``fnmatch`` glob).
    roots: tuple[str, ...]
    file_pattern: str
    #: The product paths its tests exercise.
    covers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "runner": self.runner,
            "checks": list(self.checks),
            "roots": list(self.roots),
            "file_pattern": self.file_pattern,
            "covers": list(self.covers),
        }

    @classmethod
    def from_dict(cls, doc: Mapping[str, Any]) -> RunnerView:
        return cls(
            doc["runner"],
            tuple(doc["checks"]),
            tuple(doc["roots"]),
            doc["file_pattern"],
            tuple(doc["covers"]),
        )


@dataclass(frozen=True)
class CheckoutManifest:
    commit: str
    sizes: Mapping[str, int]
    binary: frozenset[str] = field(default_factory=frozenset)
    executable: frozenset[str] = field(default_factory=frozenset)
    instruction_paths: tuple[str, ...] = ()
    generated: frozenset[str] = field(default_factory=frozenset)
    #: The product's own checks at the pinned configuration revision, (id, argv): what verifies
    #: the run's change, shown to every task so a plan writes tests those checks find.
    checks: tuple[tuple[str, tuple[str, ...]], ...] = ()
    #: The product's test runners, from the derived profile at the Project's pin; empty when no
    #: profile is recorded there, or in a manifest stored before 2.5.
    runners: tuple[RunnerView, ...] = ()

    @property
    def held_back(self) -> frozenset[str]:
        """The files no task's view carries: binary files and generated lockfiles."""
        return self.binary | self.generated

    def to_json(self) -> bytes:
        return json.dumps(
            {
                "commit": self.commit,
                "sizes": dict(sorted(self.sizes.items())),
                "binary": sorted(self.binary),
                "executable": sorted(self.executable),
                "instruction_paths": list(self.instruction_paths),
                "generated": sorted(self.generated),
                "checks": [{"id": i, "argv": list(a)} for i, a in self.checks],
                "runners": [r.as_dict() for r in self.runners],
            },
            indent=1,
        ).encode()

    @classmethod
    def from_json(cls, raw: bytes) -> CheckoutManifest:
        doc = json.loads(raw)
        return cls(
            commit=doc["commit"],
            sizes=doc["sizes"],
            binary=frozenset(doc["binary"]),
            executable=frozenset(doc["executable"]),
            instruction_paths=tuple(doc["instruction_paths"]),
            generated=frozenset(doc["generated"]),
            checks=tuple((c["id"], tuple(c["argv"])) for c in doc["checks"]),
            runners=tuple(RunnerView.from_dict(r) for r in doc.get("runners", ())),
        )


def manifest_of(
    commit: str,
    files: Mapping[str, bytes],
    executable: Iterable[str],
    instruction_paths: Iterable[str],
    *,
    classify: Callable[[str], str],
    checks: Iterable[tuple[str, tuple[str, ...]]] = (),
    runners: Iterable[RunnerView] = (),
) -> CheckoutManifest:
    """The checkout's manifest, refused past 2.4's limits. ``classify`` names a path's artifact
    type, as the run's storage will."""
    binary, generated = set(), set()
    workspace_bytes = 0
    for path, content in files.items():
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            binary.add(path)
            continue
        if PurePosixPath(path).name in GENERATED_LOCKFILES:
            generated.add(path)
        elif classify(path) in WORKSPACE_TYPES:
            workspace_bytes += len(content)
    if len(files) > MAX_FILES:
        raise CheckoutTooLarge(f"{len(files)} files, past the {MAX_FILES} a run takes on")
    if workspace_bytes > MAX_WORKSPACE_BYTES:
        raise CheckoutTooLarge(
            f"{workspace_bytes // 1024} KB of source and config, past the "
            f"{MAX_WORKSPACE_BYTES // 1024} KB every task's workspace carries whole"
        )
    return CheckoutManifest(
        commit=commit,
        sizes={p: len(c) for p, c in files.items()},
        binary=frozenset(binary),
        executable=frozenset(executable),
        instruction_paths=tuple(p for p in instruction_paths if p in files),
        generated=frozenset(generated),
        checks=tuple(checks),
        runners=tuple(runners),
    )


def repository_map(manifest: CheckoutManifest) -> str:
    """Every path with its size, or, past the path limit, every directory with its count."""
    paths = sorted(manifest.sizes)
    if len(paths) <= MAP_PATH_LIMIT:
        return "\n".join(
            f"- `{p}` ({manifest.sizes[p]} bytes{_held_back_note(manifest, p)})" for p in paths
        )
    counts: dict[str, int] = {}
    for p in paths:
        top = p.split("/", 1)[0] + ("/" if "/" in p else "")
        counts[top] = counts.get(top, 0) + 1
    return "\n".join(
        f"- `{d}` ({n} files)" if d.endswith("/") else f"- `{d}`" for d, n in sorted(counts.items())
    )


def _held_back_note(manifest: CheckoutManifest, path: str) -> str:
    if path in manifest.binary:
        return ", binary"
    return ", generated" if path in manifest.generated else ""


def focus_paths(manifest: CheckoutManifest, named: Iterable[str]) -> list[str]:
    """The existing text files a task names, in its order, within the focus budget."""
    chosen, used = [], 0
    for path in named:
        if path not in manifest.sizes or path in manifest.held_back or path in chosen:
            continue
        if used + manifest.sizes[path] > FOCUS_BUDGET_BYTES:
            break
        chosen.append(path)
        used += manifest.sizes[path]
    return chosen


def source_repository_input(
    manifest: CheckoutManifest,
    current: Mapping[str, str],
    named: Iterable[str],
) -> dict[str, Any]:
    """The task's ``source_repository`` input: the map, the product's checks and test runners, its
    instruction files and the current content of the files it names. ``current`` holds each path's latest content: the
    squad's own when it has changed the file, the checkout's otherwise."""
    focus = focus_paths(manifest, named)
    return {
        "commit": manifest.commit,
        "map": repository_map(manifest),
        "checks": [{"id": i, "argv": list(a)} for i, a in manifest.checks],
        "runners": [r.as_dict() for r in manifest.runners],
        "instructions": {p: current[p] for p in manifest.instruction_paths if p in current},
        "existing_files": {p: current[p] for p in focus if p in current},
    }
