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

#: The limits on a product a source-backed run takes on (2.4's, the workspace cap raised by #3118,
#: SIP-0112 H.32). The workspace cap is the seeded source and config text, which every acceptance
#: workspace carries whole in one resolution (``context_assembly.ARTIFACT_CONTENTS_LIMIT_BYTES``,
#: 4 MiB), with 1 MiB left for the squad's own files. A test holds the two apart by that room.
MAX_FILES = 2000
MAX_WORKSPACE_BYTES = 3 * 1024 * 1024
#: How much current file content one task is shown in full.
FOCUS_BUDGET_BYTES = 96 * 1024
#: The most lines the map lists. A tree with more paths folds the files no task's view carries
#: first, so the paths a task can change stay listed (#3178), and only a tree still past it then
#: shows directories with their file counts.
MAP_PATH_LIMIT = 400
#: What a map past its limit says before its directories, so no reader takes it for every path.
MAP_FOLDED_NOTE = (
    f"The product holds more than the {MAP_PATH_LIMIT} paths this map lists, so each directory "
    "is shown with its file count and its files are not listed:"
)


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


def repository_map(manifest: CheckoutManifest, deleted: Iterable[str] = ()) -> str:
    """Every path with its size. A path the run has removed (#2612) is named as removed.

    Past the path limit the files no task's view carries (binary, generated) fold first, by
    directory, with their count, and every other path stays listed (#3178). A game's tree held
    619 files, 385 of them art and documents; folded to its top-level directories it read
    ``src/ (137 files)``, and the proposal named a source file the product doesn't hold. Only a
    tree still past the limit then shows every directory with its count, and says so."""
    paths = sorted(manifest.sizes)
    removed = frozenset(deleted)
    if len(paths) <= MAP_PATH_LIMIT:
        return "\n".join(_path_line(manifest, p, removed) for p in paths)
    folded = _held_back_folded(manifest, paths, removed)
    if len(folded) <= MAP_PATH_LIMIT:
        return "\n".join(folded)
    counts: dict[str, int] = {}
    for p in paths:
        top = p.split("/", 1)[0] + ("/" if "/" in p else "")
        counts[top] = counts.get(top, 0) + 1
    return "\n".join(
        [MAP_FOLDED_NOTE]
        + [
            f"- `{d}` ({n} files)" if d.endswith("/") else f"- `{d}`"
            for d, n in sorted(counts.items())
        ]
    )


def _path_line(manifest: CheckoutManifest, path: str, removed: frozenset[str]) -> str:
    if path in removed:
        return f"- `{path}` (removed by this run)"
    return f"- `{path}` ({manifest.sizes[path]} bytes{_held_back_note(manifest, path)})"


def _held_back_folded(
    manifest: CheckoutManifest, paths: list[str], removed: frozenset[str]
) -> list[str]:
    """The map with its held-back files folded: one line for a directory whose every file is
    held back, at the shallowest such directory, and one for the held-back files that sit
    beside listed ones. A root-level file and a removed one are listed as themselves."""
    listed = [p for p in paths if p not in manifest.held_back or p in removed or "/" not in p]
    beside_listed = {
        "/".join(parts[:depth])
        for parts in (p.split("/")[:-1] for p in listed)
        for depth in range(1, len(parts) + 1)
    }
    whole: dict[str, int] = {}
    among: dict[str, int] = {}
    for path in sorted(set(paths) - set(listed)):
        parts = path.split("/")[:-1]
        ancestors = ["/".join(parts[:depth]) for depth in range(1, len(parts) + 1)]
        all_held_back = next((d for d in ancestors if d not in beside_listed), None)
        if all_held_back is not None:
            whole[all_held_back] = whole.get(all_held_back, 0) + 1
        else:
            among[ancestors[-1]] = among.get(ancestors[-1], 0) + 1
    lines = [(p, _path_line(manifest, p, removed)) for p in listed]
    lines += [(f"{d}/", f"- `{d}/` ({n} binary or generated files)") for d, n in whole.items()]
    lines += [
        (f"{d}/", f"- `{d}/` ({n} binary or generated files, beside the files listed)")
        for d, n in among.items()
    ]
    return [line for _key, line in sorted(lines)]


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
    *,
    deleted: Iterable[str] = (),
) -> dict[str, Any]:
    """The task's ``source_repository`` input: the map, the product's checks and test runners, its
    instruction files and the current content of the files it names. ``current`` holds each path's latest content: the
    squad's own when it has changed the file, the checkout's otherwise.

    It also carries, as data no prompt renders, what a removal is judged against (#2612): every
    path at the commit (the map collapses past its limit), the ones no task changes (binary
    files, generated lockfiles), and the ones the run has already removed."""
    named = list(named)
    removed = sorted(set(deleted) & manifest.sizes.keys())
    focus = [p for p in focus_paths(manifest, named) if p not in removed]
    return {
        "commit": manifest.commit,
        "map": repository_map(manifest, removed),
        "paths": sorted(manifest.sizes),
        "held_back": sorted(manifest.held_back),
        "deleted": removed,
        "checks": [{"id": i, "argv": list(a)} for i, a in manifest.checks],
        "runners": [r.as_dict() for r in manifest.runners],
        "instructions": {p: current[p] for p in manifest.instruction_paths if p in current},
        "existing_files": {p: current[p] for p in focus if p in current},
        # #3178: the files it names that neither the product nor this run holds, so a task
        # shown no content for one is told why.
        "new_files": [
            p for p in dict.fromkeys(named) if p not in manifest.sizes and p not in current
        ],
    }
