"""Regression: prompt manifest must register every fragment file on disk.

Bug it catches: PR #126 added three task_type fragment files
(`task_type.governance.define_done`, `task_type.governance.correction_decision`,
`task_type.data.analyze_failure`) but did not register them in
`fragments/manifest.yaml`. PR #129 then made them mandatory via
`assemble_task_only`, which failed at runtime with
`MandatoryLayerMissingError` on the first impl task of every cycle (Max's
`governance.define_done`).

The shared-fragment lookup goes through the manifest, so an unregistered
fragment is invisible regardless of whether the file exists.
"""

from __future__ import annotations

from pathlib import Path

import yaml

FRAGMENTS_DIR = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts" / "fragments"


def _load_manifest() -> dict:
    with open(FRAGMENTS_DIR / "manifest.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _disk_fragment_paths() -> set[Path]:
    return {p for p in FRAGMENTS_DIR.rglob("*.md") if p.name != "manifest.yaml"}


def test_every_fragment_file_is_registered_in_manifest():
    """Every .md fragment under fragments/ must be referenced by the manifest."""
    manifest = _load_manifest()
    registered = {FRAGMENTS_DIR / entry["path"] for entry in manifest["fragments"]}
    on_disk = _disk_fragment_paths()

    unregistered = on_disk - registered
    assert not unregistered, (
        "Fragment files exist on disk but are not registered in manifest.yaml — "
        "shared-fragment lookups will fail with MandatoryLayerMissingError.\n"
        f"Unregistered: {sorted(str(p.relative_to(FRAGMENTS_DIR)) for p in unregistered)}"
    )


def test_every_manifest_entry_points_to_existing_file():
    """Every manifest entry's `path` must resolve to an existing file."""
    manifest = _load_manifest()
    missing = [
        entry["path"]
        for entry in manifest["fragments"]
        if not (FRAGMENTS_DIR / entry["path"]).exists()
    ]
    assert not missing, f"Manifest references missing files: {missing}"


def test_impl_handler_task_type_fragments_registered():
    """Explicit guard for the SIP-0079 impl handler fragments that PR #126/#129 missed."""
    manifest = _load_manifest()
    registered_ids = {entry["fragment_id"] for entry in manifest["fragments"]}
    required = {
        "task_type.governance.define_done",
        "task_type.governance.correction_decision",
        "task_type.data.analyze_failure",
    }
    missing = required - registered_ids
    assert not missing, (
        "SIP-0079 impl handler task_type fragments are not registered in manifest.yaml. "
        f"Missing: {sorted(missing)}. These are mandatory for assemble_task_only()."
    )


def test_manifest_hash_matches_pinned_fingerprint():
    """#327: the shipped manifest's top-level manifest_hash must match the
    hash computed over (version, fragments) — the loader now fails HARD on a
    mismatch (every agent refuses to start), so a stale fingerprint must be
    caught here, at CI time, not in the fleet. Fix:
    python scripts/dev/regen_fragment_manifest.py --write"""
    from squadops.prompts.models import ManifestFragment, PromptManifest

    manifest = _load_manifest()
    fragments = tuple(
        ManifestFragment(
            fragment_id=f["fragment_id"],
            path=f["path"],
            layer=f["layer"],
            roles=tuple(f.get("roles", ["*"])),
            sha256=f["sha256"],
        )
        for f in manifest["fragments"]
    )
    computed = PromptManifest.compute_manifest_hash(manifest.get("version", "0.0.0"), fragments)
    assert manifest.get("manifest_hash") == computed, (
        "manifest.yaml's manifest_hash is stale — agents will fail to load any "
        "prompt (ManifestValidationError at first use). Regenerate with: "
        "python scripts/dev/regen_fragment_manifest.py --write"
    )


def test_every_fragment_hash_matches_file_content():
    """#327/#195: every per-fragment sha256 in the manifest must match the
    fragment file's canonical body hash — same computation as the runtime
    integrity check and the regen tool."""
    from adapters.prompts.filesystem import FileSystemPromptRepository

    manifest = _load_manifest()
    stale = []
    for entry in manifest["fragments"]:
        path = FRAGMENTS_DIR / entry["path"]
        computed = FileSystemPromptRepository.hash_fragment_file(path)
        if computed != entry["sha256"]:
            stale.append(entry["fragment_id"])
    assert not stale, (
        f"Stale fragment hashes in manifest.yaml: {stale}. Regenerate with: "
        "python scripts/dev/regen_fragment_manifest.py --write"
    )
