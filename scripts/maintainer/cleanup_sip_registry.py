#!/usr/bin/env python3
"""
SIP Registry Cleanup Script
Automatically fixes issues identified by audit_sip_registry.py
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Import audit functions
sys.path.insert(0, str(Path(__file__).parent))
from audit_sip_registry import (
    REGISTRY_FILE,
    REPO_ROOT,
    extract_metadata_from_file,
    find_all_sip_files,
    is_valid_iso_timestamp,
    load_registry,
)


def save_registry(registry: dict[str, Any]) -> bool:
    """Save the registry."""
    try:
        with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
            yaml.dump(registry, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return True
    except Exception as e:
        print(f"Error saving registry: {e}")
        return False


def parse_timestamp(value: str) -> str | None:
    """Try to parse various timestamp formats and convert to ISO 8601."""
    if not isinstance(value, str):
        return None

    # Already valid ISO format
    if is_valid_iso_timestamp(value):
        return value

    # Try to extract date from text
    # Look for patterns like "2025-01-XX" or "January 2025"
    date_patterns = [
        r"(\d{4}-\d{2}-\d{2})",  # YYYY-MM-DD
        r"(\d{4}-\d{2})",  # YYYY-MM
        r"(\d{4})",  # YYYY
    ]

    for pattern in date_patterns:
        match = re.search(pattern, value)
        if match:
            date_str = match.group(1)
            # If we only have year-month, use first day
            if len(date_str) == 7:  # YYYY-MM
                date_str = f"{date_str}-01"
            # If we only have year, use January 1st
            elif len(date_str) == 4:  # YYYY
                date_str = f"{date_str}-01-01"
            # Convert to ISO format
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return dt.strftime("%Y-%m-%dT00:00:00Z")
            except ValueError:
                pass

    return None


def fix_missing_files(registry: dict[str, Any], dry_run: bool = False) -> int:
    """Remove registry entries for non-existent files."""
    fixed = 0
    sips = registry.get("sips", [])
    to_remove = []

    for sip in sips:
        path = sip.get("path")
        if path:
            file_path = REPO_ROOT / path
            if not file_path.exists():
                to_remove.append(sip)

    if to_remove:
        if not dry_run:
            for sip in to_remove:
                sips.remove(sip)
                fixed += 1
        else:
            fixed = len(to_remove)

    return fixed


def fix_invalid_timestamps(registry: dict[str, Any], dry_run: bool = False) -> int:
    """Fix invalid timestamp formats in registry."""
    fixed = 0

    for sip in registry.get("sips", []):
        # Fix created_at
        created_at = sip.get("created_at")
        if created_at and not is_valid_iso_timestamp(created_at):
            parsed = parse_timestamp(str(created_at))
            if parsed:
                if not dry_run:
                    sip["created_at"] = parsed
                fixed += 1

        # Fix updated_at
        updated_at = sip.get("updated_at")
        if updated_at and not is_valid_iso_timestamp(updated_at):
            parsed = parse_timestamp(str(updated_at))
            if parsed:
                if not dry_run:
                    sip["updated_at"] = parsed
                fixed += 1

    return fixed


def fix_corrupted_timestamps(registry: dict[str, Any], dry_run: bool = False) -> int:
    """Fix corrupted created_at timestamps by syncing from file metadata or using fallback dates."""
    fixed = 0
    default_date = "2025-10-03T00:00:00Z"

    for sip in registry.get("sips", []):
        created_at = sip.get("created_at")

        # Only fix if created_at is invalid (not ISO format)
        if created_at and not is_valid_iso_timestamp(created_at):
            # Strategy 1: Try to get valid timestamp from file metadata
            path = sip.get("path")
            file_timestamp = None

            if path:
                file_path = REPO_ROOT / path
                if file_path.exists():
                    metadata = extract_metadata_from_file(file_path)
                    if metadata:
                        file_created_at = metadata.get("created_at")
                        if file_created_at and is_valid_iso_timestamp(file_created_at):
                            file_timestamp = file_created_at

            # Strategy 2: Use updated_at as fallback
            if not file_timestamp:
                updated_at = sip.get("updated_at")
                if updated_at and is_valid_iso_timestamp(updated_at):
                    file_timestamp = updated_at

            # Strategy 3: Use default date
            if not file_timestamp:
                file_timestamp = default_date

            # Update registry
            if not dry_run:
                sip["created_at"] = file_timestamp
            fixed += 1

    return fixed


def fix_duplicate_variants(registry: dict[str, Any], dry_run: bool = False) -> int:
    """Add variant fields to duplicate SIP numbers."""
    from collections import defaultdict

    fixed = 0
    sip_numbers: dict[int, list[dict[str, Any]]] = defaultdict(list)

    # Group by sip_number
    for sip in registry.get("sips", []):
        sip_number = sip.get("sip_number")
        if sip_number is not None:
            sip_numbers[sip_number].append(sip)

    # For each duplicate group, assign variants
    for sip_number, entries in sip_numbers.items():
        if len(entries) > 1:
            # Check which entries already have variants
            entries_with_variants = [e for e in entries if e.get("variant")]
            entries_without_variants = [e for e in entries if not e.get("variant")]

            if entries_without_variants:
                # Find the highest variant number
                max_variant = 0
                for entry in entries_with_variants:
                    variant = entry.get("variant", "")
                    if variant:
                        # Extract number from variant like "v1", "v2", etc.
                        variant_str = str(variant)
                        match = re.match(r"v(\d+)", variant_str)
                        if match:
                            max_variant = max(max_variant, int(match.group(1)))

                # Assign variants to entries without them
                for i, entry in enumerate(entries_without_variants, 1):
                    if not dry_run:
                        entry["variant"] = f"v{max_variant + i}"
                    fixed += 1

    return fixed


def fix_duplicate_uids(registry: dict[str, Any], dry_run: bool = False) -> int:
    """Fix duplicate sip_uids by updating registry to match file metadata."""
    fixed = 0

    for sip in registry.get("sips", []):
        path = sip.get("path")
        if path:
            file_path = REPO_ROOT / path
            if file_path.exists():
                metadata = extract_metadata_from_file(file_path)
                if metadata:
                    file_sip_uid = metadata.get("sip_uid")
                    registry_sip_uid = sip.get("sip_uid")

                    # If file has sip_uid and it differs from registry, update registry
                    if file_sip_uid and file_sip_uid != registry_sip_uid:
                        if not dry_run:
                            sip["sip_uid"] = file_sip_uid
                        fixed += 1

    return fixed


def add_orphaned_files(registry: dict[str, Any], dry_run: bool = False) -> int:
    """Add orphaned numbered files to registry."""
    fixed = 0
    all_files = find_all_sip_files()

    # Get existing registry files
    registry_files = set()
    for sip in registry.get("sips", []):
        path = sip.get("path")
        if path:
            registry_files.add(Path(path).name)

    # Find orphaned numbered files
    for filename, file_path in all_files.items():
        if filename not in registry_files:
            metadata = extract_metadata_from_file(file_path)
            if metadata and metadata.get("sip_number") is not None:
                # This is a numbered file not in registry
                sip_number = metadata.get("sip_number")
                sip_uid = metadata.get("sip_uid")
                status = metadata.get("status", "accepted")  # Default to accepted

                # Determine folder from file location
                folder_status = None
                for folder, folder_stat in [
                    (REPO_ROOT / "sips" / "proposals", "proposed"),
                    (REPO_ROOT / "sips" / "accepted", "accepted"),
                    (REPO_ROOT / "sips" / "implemented", "implemented"),
                    (REPO_ROOT / "sips" / "deprecated", "deprecated"),
                ]:
                    if file_path.parent == folder:
                        folder_status = folder_stat
                        break

                if folder_status:
                    # Use sip_uid from file metadata (not generate new one)
                    if not sip_uid:
                        sip_uid = f"orphaned_{sip_number}_{datetime.now().timestamp()}"

                    # Create registry entry
                    registry_path = f"sips/{folder_status}/{filename}"
                    entry = {
                        "sip_number": sip_number,
                        "sip_uid": sip_uid,
                        "title": metadata.get("title", "Unknown"),
                        "status": folder_status,
                        "path": registry_path,
                        "created_at": metadata.get("created_at")
                        or datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }

                    # Add variant if needed (check for duplicates)
                    existing_with_number = [
                        s for s in registry.get("sips", []) if s.get("sip_number") == sip_number
                    ]
                    if existing_with_number:
                        # Find max variant number
                        max_variant = 0
                        for existing in existing_with_number:
                            variant = existing.get("variant", "")
                            match = re.match(r"v(\d+)", variant)
                            if match:
                                max_variant = max(max_variant, int(match.group(1)))
                        entry["variant"] = f"v{max_variant + 1}"

                    if not dry_run:
                        registry.setdefault("sips", []).append(entry)
                    fixed += 1

    return fixed


def main():
    """Main cleanup function."""
    import argparse

    parser = argparse.ArgumentParser(description="Clean up SIP registry issues")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be fixed without making changes"
    )
    parser.add_argument(
        "--fix-missing", action="store_true", help="Remove registry entries for non-existent files"
    )
    parser.add_argument(
        "--fix-timestamps", action="store_true", help="Fix invalid timestamp formats"
    )
    parser.add_argument(
        "--fix-corrupted-timestamps",
        action="store_true",
        help="Fix corrupted created_at timestamps by syncing from file metadata or using fallback dates",
    )
    parser.add_argument(
        "--fix-variants", action="store_true", help="Add variant fields to duplicate numbers"
    )
    parser.add_argument(
        "--fix-uids",
        action="store_true",
        help="Fix duplicate sip_uids by syncing with file metadata",
    )
    parser.add_argument(
        "--add-orphaned", action="store_true", help="Add orphaned numbered files to registry"
    )
    parser.add_argument("--all", action="store_true", help="Fix all issues")

    args = parser.parse_args()

    if not any(
        [
            args.fix_missing,
            args.fix_timestamps,
            args.fix_corrupted_timestamps,
            args.fix_variants,
            args.fix_uids,
            args.add_orphaned,
            args.all,
        ]
    ):
        print(
            "No cleanup actions specified. Use --all to fix everything, or specify individual fixes."
        )
        print("\nAvailable fixes:")
        print("  --fix-missing              Remove registry entries for non-existent files")
        print("  --fix-timestamps           Fix invalid timestamp formats")
        print(
            "  --fix-corrupted-timestamps Fix corrupted created_at timestamps by syncing from file metadata"
        )
        print("  --fix-variants             Add variant fields to duplicate numbers")
        print("  --fix-uids                 Fix duplicate sip_uids by syncing with file metadata")
        print("  --add-orphaned             Add orphaned numbered files to registry")
        print("  --all                      Apply all fixes")
        print("\nUse --dry-run to preview changes without applying them")
        return 1

    dry_run = args.dry_run
    fix_all = args.all

    print("🧹 SIP Registry Cleanup")
    print("=" * 60)
    if dry_run:
        print("DRY RUN MODE - No changes will be made")
        print()

    registry = load_registry()
    total_fixed = 0

    # Fix missing files
    if fix_all or args.fix_missing:
        print("📁 Removing registry entries for non-existent files...")
        fixed = fix_missing_files(registry, dry_run)
        print(f"   {'Would remove' if dry_run else 'Removed'}: {fixed} entries")
        total_fixed += fixed

    # Fix invalid timestamps
    if fix_all or args.fix_timestamps:
        print("🕐 Fixing invalid timestamp formats...")
        fixed = fix_invalid_timestamps(registry, dry_run)
        print(f"   {'Would fix' if dry_run else 'Fixed'}: {fixed} timestamps")
        total_fixed += fixed

    # Fix corrupted timestamps (created_at with descriptive text)
    if fix_all or args.fix_corrupted_timestamps:
        print("🔧 Fixing corrupted created_at timestamps...")
        fixed = fix_corrupted_timestamps(registry, dry_run)
        print(f"   {'Would fix' if dry_run else 'Fixed'}: {fixed} corrupted timestamps")
        total_fixed += fixed

    # Fix duplicate UIDs (sync registry with file metadata)
    if fix_all or args.fix_uids:
        print("🆔 Fixing duplicate sip_uids by syncing with file metadata...")
        fixed = fix_duplicate_uids(registry, dry_run)
        print(f"   {'Would fix' if dry_run else 'Fixed'}: {fixed} sip_uids")
        total_fixed += fixed

    # Fix duplicate variants
    if fix_all or args.fix_variants:
        print("🔢 Adding variant fields to duplicate numbers...")
        fixed = fix_duplicate_variants(registry, dry_run)
        print(f"   {'Would add' if dry_run else 'Added'}: {fixed} variant fields")
        total_fixed += fixed

    # Add orphaned files
    if fix_all or args.add_orphaned:
        print("➕ Adding orphaned numbered files to registry...")
        fixed = add_orphaned_files(registry, dry_run)
        print(f"   {'Would add' if dry_run else 'Added'}: {fixed} files")
        total_fixed += fixed

    # Save registry if not dry run
    if not dry_run and total_fixed > 0:
        print("\n💾 Saving registry...")
        if save_registry(registry):
            print("✅ Registry saved successfully")
        else:
            print("❌ Failed to save registry")
            return 1

    print()
    print("=" * 60)
    if dry_run:
        print(f"DRY RUN: Would fix {total_fixed} issues")
        print("Run without --dry-run to apply changes")
    else:
        print(f"✅ Cleanup complete: {total_fixed} issues fixed")

    return 0


if __name__ == "__main__":
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML not installed. Install with: pip install pyyaml")
        sys.exit(1)

    sys.exit(main())
