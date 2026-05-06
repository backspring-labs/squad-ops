"""Regression: prompt manifest must register every fragment file on disk.

Bug it catches: PR #126 added three task_type fragment files
(`task_type.governance.establish_contract`, `task_type.governance.correction_decision`,
`task_type.data.analyze_failure`) but did not register them in
`fragments/manifest.yaml`. PR #129 then made them mandatory via
`assemble_task_only`, which failed at runtime with
`MandatoryLayerMissingError` on the first impl task of every cycle (Max's
`governance.establish_contract`).

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
    missing = [entry["path"] for entry in manifest["fragments"]
               if not (FRAGMENTS_DIR / entry["path"]).exists()]
    assert not missing, f"Manifest references missing files: {missing}"


def test_impl_handler_task_type_fragments_registered():
    """Explicit guard for the SIP-0079 impl handler fragments that PR #126/#129 missed."""
    manifest = _load_manifest()
    registered_ids = {entry["fragment_id"] for entry in manifest["fragments"]}
    required = {
        "task_type.governance.establish_contract",
        "task_type.governance.correction_decision",
        "task_type.data.analyze_failure",
    }
    missing = required - registered_ids
    assert not missing, (
        "SIP-0079 impl handler task_type fragments are not registered in manifest.yaml. "
        f"Missing: {sorted(missing)}. These are mandatory for assemble_task_only()."
    )
