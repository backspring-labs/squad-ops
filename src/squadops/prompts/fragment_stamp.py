"""The prompt pack's build stamp: fragment hashes taken where the pack leaves the repo (#353).

``fragments/manifest.yaml`` is a registry — which fragments exist, where, for which layer and
roles. It used to carry a ``sha256`` per fragment and a ``manifest_hash`` over them, committed
beside the files they described: a hand-kept copy of git's own content addressing. Both prompt
incidents it was meant to catch (#195, #327) were caused by those copies drifting from their
source, and three layers of machinery existed only to keep them in step. The runtime's hard
fail compared the manifest's two hash columns with each other; nothing at runtime compared a
fragment's content with its recorded hash.

A fingerprint means something where the pack crosses a boundary. Each image build runs this
module after copying ``src/`` (``python -m squadops.prompts.fragment_stamp``), which hashes
every registered fragment and writes :data:`STAMP_FILENAME` beside the manifest — the wheel
``RECORD`` pattern. The prompt repository then refuses any fragment whose content no longer
matches the stamp: a live-edited volume, a stale layer. A source checkout has no stamp, and
needs none: the files are the reference, and there is nothing shipped to verify.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from squadops.prompts.frontmatter import split_frontmatter
from squadops.prompts.models import PromptFragment

STAMP_FILENAME = "manifest.stamp.json"

#: The fragments directory this package ships, which the image build stamps.
PACKAGED_FRAGMENTS_DIR = Path(__file__).resolve().parent / "fragments"


class StampError(Exception):
    """The pack cannot be stamped: the manifest names a fragment the tree does not hold."""


def fragment_body(raw_content: str) -> str:
    """A fragment's hashable body: everything after the YAML frontmatter block, stripped (or
    the whole file, stripped, when there is no frontmatter).

    The one definition of "a fragment's content", shared by the stamp and the repository that
    verifies against it, so the two cannot disagree about what was hashed (#195).
    """
    _, body = split_frontmatter(raw_content)
    return body.strip()


def hash_fragment_file(path: Path) -> str:
    """The sha256 the stamp records for a fragment file on disk."""
    return PromptFragment.compute_hash(fragment_body(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class FragmentStamp:
    """What the build recorded: the manifest version it stamped, and each registered
    fragment's hash keyed by its path relative to the fragments directory."""

    version: str
    hashes: Mapping[str, str]

    def to_json(self) -> str:
        return json.dumps(
            {"version": self.version, "fragments": dict(sorted(self.hashes.items()))}, indent=2
        )

    @classmethod
    def from_json(cls, text: str) -> FragmentStamp:
        data = json.loads(text)
        return cls(version=str(data["version"]), hashes=dict(data["fragments"]))


def compute_stamp(fragments_dir: Path, manifest_path: Path | None = None) -> FragmentStamp:
    """Hash every fragment the manifest registers.

    Raises:
        StampError: a registered path is not a file under ``fragments_dir`` — an image built
            from that tree would ship a manifest naming a fragment it does not carry.
    """
    manifest_path = manifest_path or fragments_dir / "manifest.yaml"
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    hashes: dict[str, str] = {}
    missing: list[str] = []
    for entry in data.get("fragments", []):
        path = fragments_dir / entry["path"]
        if not path.is_file():
            missing.append(entry["path"])
            continue
        hashes[entry["path"]] = hash_fragment_file(path)
    if missing:
        raise StampError(
            f"{manifest_path} registers {len(missing)} fragment(s) with no file: {sorted(missing)}"
        )
    return FragmentStamp(version=str(data.get("version", "0.0.0")), hashes=hashes)


def read_stamp(manifest_path: Path) -> FragmentStamp | None:
    """The stamp beside ``manifest_path``, or ``None`` in a source checkout."""
    stamp_path = manifest_path.parent / STAMP_FILENAME
    if not stamp_path.is_file():
        return None
    return FragmentStamp.from_json(stamp_path.read_text(encoding="utf-8"))


def write_stamp(fragments_dir: Path) -> Path:
    """Stamp ``fragments_dir`` and write the stamp beside its manifest."""
    stamp_path = fragments_dir / STAMP_FILENAME
    stamp_path.write_text(compute_stamp(fragments_dir).to_json() + "\n", encoding="utf-8")
    return stamp_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stamp the prompt pack at image build: hash every registered fragment."
    )
    parser.add_argument(
        "fragments_dir",
        nargs="?",
        type=Path,
        default=PACKAGED_FRAGMENTS_DIR,
        help="the fragments directory to stamp (default: the one this package ships)",
    )
    args = parser.parse_args(argv)
    try:
        stamp_path = write_stamp(args.fragments_dir)
    except StampError as exc:
        print(f"prompt pack not stamped: {exc}", file=sys.stderr)
        return 1
    stamp = FragmentStamp.from_json(stamp_path.read_text(encoding="utf-8"))
    print(f"stamped {len(stamp.hashes)} fragments (pack {stamp.version}) → {stamp_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
