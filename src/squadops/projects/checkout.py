"""A source-backed run's view of the product's repository (SIP-0112 E.4.3).

A Cycle that pins an external Project's source starts from that product's tree at the pinned
commit, as a campaign increment starts from its accepted tree (SIP-0109 §7.3). Each tracked
file is seeded as the run's own starting content, so whatever the squad produces for a path wins
over it, and every other file is delivered as it was.

What a task sees of it is bounded. The squad gets three things, never a silently truncated tree:
- a map of every path;
- the product's own instruction files;
- the current content of the files that task names.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

#: The producing task of a file seeded from the product's repository: provenance only, never a
#: dispatched task type.
SOURCE_CHECKOUT = "source.checkout"
#: The run's record of what it seeded: its commit, every path's size, and which are binary or
#: executable. An artifact type no context filter selects, so it never reaches a prompt itself.
CHECKOUT_MANIFEST_TYPE = "source_checkout"
CHECKOUT_MANIFEST_FILENAME = "source_checkout.json"

#: 2.4's limits on a product a source-backed run takes on. The text cap keeps every one of the
#: run's context resolutions (512 KB each) whole, so no task works from a truncated tree.
MAX_FILES = 2000
MAX_TEXT_BYTES = 384 * 1024
#: How much current file content one task is shown in full.
FOCUS_BUDGET_BYTES = 96 * 1024
#: Beyond this many paths the map lists directories, with their file counts.
MAP_PATH_LIMIT = 400


class CheckoutTooLarge(ValueError):
    """A product past 2.4's limits for a source-backed run: refused by name, never truncated."""


@dataclass(frozen=True)
class CheckoutManifest:
    commit: str
    sizes: Mapping[str, int]
    binary: frozenset[str] = field(default_factory=frozenset)
    executable: frozenset[str] = field(default_factory=frozenset)
    instruction_paths: tuple[str, ...] = ()

    def to_json(self) -> bytes:
        return json.dumps(
            {
                "commit": self.commit,
                "sizes": dict(sorted(self.sizes.items())),
                "binary": sorted(self.binary),
                "executable": sorted(self.executable),
                "instruction_paths": list(self.instruction_paths),
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
        )


def manifest_of(
    commit: str,
    files: Mapping[str, bytes],
    executable: Iterable[str],
    instruction_paths: Iterable[str],
) -> CheckoutManifest:
    """The checkout's manifest, refused past 2.4's limits."""
    binary = set()
    text_bytes = 0
    for path, content in files.items():
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            binary.add(path)
        else:
            text_bytes += len(content)
    if len(files) > MAX_FILES:
        raise CheckoutTooLarge(f"{len(files)} files, past the {MAX_FILES} a run takes on")
    if text_bytes > MAX_TEXT_BYTES:
        raise CheckoutTooLarge(
            f"{text_bytes // 1024} KB of text, past the {MAX_TEXT_BYTES // 1024} KB a run takes on"
        )
    return CheckoutManifest(
        commit=commit,
        sizes={p: len(c) for p, c in files.items()},
        binary=frozenset(binary),
        executable=frozenset(executable),
        instruction_paths=tuple(p for p in instruction_paths if p in files),
    )


def repository_map(manifest: CheckoutManifest) -> str:
    """Every path with its size, or, past the path limit, every directory with its count."""
    paths = sorted(manifest.sizes)
    if len(paths) <= MAP_PATH_LIMIT:
        return "\n".join(
            f"- `{p}` ({manifest.sizes[p]} bytes{', binary' if p in manifest.binary else ''})"
            for p in paths
        )
    counts: dict[str, int] = {}
    for p in paths:
        top = p.split("/", 1)[0] + ("/" if "/" in p else "")
        counts[top] = counts.get(top, 0) + 1
    return "\n".join(
        f"- `{d}` ({n} files)" if d.endswith("/") else f"- `{d}`" for d, n in sorted(counts.items())
    )


def focus_paths(manifest: CheckoutManifest, named: Iterable[str]) -> list[str]:
    """The existing text files a task names, in its order, within the focus budget."""
    chosen, used = [], 0
    for path in named:
        if path not in manifest.sizes or path in manifest.binary or path in chosen:
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
    """The task's ``source_repository`` input: the map, the product's instruction files and the
    current content of the files it names. ``current`` holds each path's latest content: the
    squad's own when it has changed the file, the checkout's otherwise."""
    focus = focus_paths(manifest, named)
    return {
        "commit": manifest.commit,
        "map": repository_map(manifest),
        "instructions": {p: current[p] for p in manifest.instruction_paths if p in current},
        "existing_files": {p: current[p] for p in focus if p in current},
    }
