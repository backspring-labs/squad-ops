#!/usr/bin/env python3
"""
SIP Status Update Script
Updates SIP status and moves files between lifecycle folders (maintainer-only).
Handles all transitions: proposed → accepted, accepted → implemented, implemented → deprecated.
"""

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).parent.parent.parent
REGISTRY_FILE = REPO_ROOT / "sips" / "registry.yaml"
PROPOSED_DIR = REPO_ROOT / "sips" / "proposed"
ACCEPTED_DIR = REPO_ROOT / "sips" / "accepted"
IMPLEMENTED_DIR = REPO_ROOT / "sips" / "implemented"
DEPRECATED_DIR = REPO_ROOT / "sips" / "deprecated"

# Valid status transitions
VALID_TRANSITIONS = {
    'proposed': ['accepted'],
    'accepted': ['implemented', 'deprecated'],
    'implemented': ['deprecated'],
}

# Status to folder mapping
STATUS_TO_FOLDER = {
    'proposed': PROPOSED_DIR,
    'accepted': ACCEPTED_DIR,
    'implemented': IMPLEMENTED_DIR,
    'deprecated': DEPRECATED_DIR,
}


def check_maintainer_flag() -> bool:
    """Check if maintainer flag is set."""
    maintainer = os.environ.get('SQUADOPS_MAINTAINER')
    return maintainer == '1' or maintainer == 'true' or maintainer == 'True'


def load_registry() -> dict[str, Any]:
    """Load the SIP registry."""
    if not REGISTRY_FILE.exists():
        return {'last_assigned': 0, 'sips': []}
    
    try:
        with open(REGISTRY_FILE, encoding='utf-8') as f:
            return yaml.safe_load(f) or {'last_assigned': 0, 'sips': []}
    except Exception as e:
        print(f"Error loading registry: {e}")
        return {'last_assigned': 0, 'sips': []}


def save_registry(registry: dict[str, Any]) -> bool:
    """Save the registry."""
    try:
        with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(registry, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return True
    except Exception as e:
        print(f"Error saving registry: {e}")
        return False


def get_next_sip_number(registry: dict[str, Any]) -> int:
    """Get the next available SIP number."""
    last_assigned = registry.get('last_assigned', 0)
    return last_assigned + 1


def extract_metadata_from_file(file_path: Path) -> dict[str, Any] | None:
    """Extract metadata from SIP file YAML frontmatter."""
    try:
        with open(file_path, encoding='utf-8') as f:
            content = f.read()
        
        # Extract YAML frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if frontmatter_match:
            yaml_content = frontmatter_match.group(1)
            metadata = yaml.safe_load(yaml_content)
            return metadata
    except Exception as e:
        print(f"Warning: Could not extract metadata from {file_path}: {e}")
    
    return None


def update_sip_file_metadata(file_path: Path, updates: dict[str, Any]) -> bool:
    """Update SIP file metadata in YAML frontmatter."""
    try:
        with open(file_path, encoding='utf-8') as f:
            content = f.read()
        
        # Update frontmatter
        def update_frontmatter(match):
            yaml_content = match.group(1)
            metadata = yaml.safe_load(yaml_content)
            metadata.update(updates)
            metadata['updated_at'] = datetime.now().isoformat() + 'Z'
            
            # Convert back to YAML
            yaml_str = yaml.dump(metadata, default_flow_style=False, sort_keys=False, allow_unicode=True)
            return f"---\n{yaml_str}---\n"
        
        content = re.sub(r'^---\s*\n(.*?)\n---\s*\n', update_frontmatter, content, count=1, flags=re.DOTALL)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"Error updating SIP file: {e}")
        return False


def normalize_filename(sip_number: int, title: str) -> str:
    """Generate normalized filename with maximum 4 words."""
    # Clean title for filename
    clean_title = re.sub(r'[^\w\s-]', '', title)
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()
    
    # Split into words and take first 4 words
    words = clean_title.split()
    words = words[:4]  # Limit to 4 words
    
    # Join with hyphens
    clean_title = '-'.join(words)
    
    return f"SIP-{sip_number:04d}-{clean_title}.md"


def validate_transition(current_status: str, new_status: str) -> tuple[bool, str]:
    """Validate that the status transition is allowed."""
    if current_status not in VALID_TRANSITIONS:
        return False, f"Invalid current status: {current_status}"
    
    if new_status not in VALID_TRANSITIONS[current_status]:
        return False, f"Invalid transition: {current_status} → {new_status}. Allowed: {VALID_TRANSITIONS[current_status]}"
    
    return True, ""


def find_sip_in_registry(registry: dict[str, Any], sip_number: int | None = None, sip_uid: str | None = None) -> dict[str, Any] | None:
    """Find SIP in registry by sip_number or sip_uid."""
    if sip_number is not None:
        for sip in registry.get('sips', []):
            if sip.get('sip_number') == sip_number:
                return sip
    elif sip_uid is not None:
        for sip in registry.get('sips', []):
            if sip.get('sip_uid') == sip_uid:
                return sip
    return None


def normalize_title(title: str) -> str:
    """Normalize title for comparison (lowercase, strip whitespace)."""
    if not title:
        return ""
    return title.lower().strip()


def find_duplicate_sip_files(
    sip_uid: str | None,
    sip_number: int | None,
    canonical_file: Path,
    registry: dict[str, Any]
) -> list[Path]:
    """
    Find duplicate SIP files with the same sip_uid, sip_number, original_filename, or title.
    
    Scans all lifecycle directories and identifies files that match the given
    sip_uid (preferred), sip_number, original_filename, or title. Excludes the canonical file.
    
    IMPORTANT: Excludes legitimate SIPs that are in the registry and in different lifecycle states.
    A file with the same sip_number in a different lifecycle state is NOT a duplicate - it's a
    legitimate SIP variant or progression.
    
    Args:
        sip_uid: SIP UID to match (preferred identifier)
        sip_number: SIP number to match (fallback identifier)
        canonical_file: The canonical file to exclude from duplicates
        registry: The SIP registry dictionary
        
    Returns:
        List of duplicate file paths
    """
    duplicates = []
    canonical_file = canonical_file.resolve()
    
    # Extract metadata from canonical file to get original_filename and title
    canonical_metadata = extract_metadata_from_file(canonical_file)
    canonical_original_filename = canonical_metadata.get('original_filename') if canonical_metadata else None
    canonical_title = normalize_title(canonical_metadata.get('title', '')) if canonical_metadata else None
    canonical_status = canonical_metadata.get('status') if canonical_metadata else None
    
    # Build a set of legitimate SIP numbers from registry (to exclude from duplicates)
    # A SIP number in the registry with a different status is legitimate, not a duplicate
    legitimate_sip_numbers = set()
    if sip_number is not None:
        for sip_entry in registry.get('sips', []):
            reg_sip_number = sip_entry.get('sip_number')
            reg_status = sip_entry.get('status')
            # If same number but different status, it's legitimate (not a duplicate)
            if reg_sip_number == sip_number and reg_status != canonical_status:
                legitimate_sip_numbers.add(reg_sip_number)
    
    # All lifecycle directories to scan
    lifecycle_dirs = [PROPOSED_DIR, ACCEPTED_DIR, IMPLEMENTED_DIR, DEPRECATED_DIR]
    
    for lifecycle_dir in lifecycle_dirs:
        if not lifecycle_dir.exists():
            continue
            
        # Find all .md files in this directory
        for sip_file in lifecycle_dir.glob("*.md"):
            # Skip the canonical file
            if sip_file.resolve() == canonical_file:
                continue
            
            # Extract metadata from file
            metadata = extract_metadata_from_file(sip_file)
            if not metadata:
                # Skip files without metadata
                continue
            
            file_sip_number = metadata.get('sip_number')
            file_status = metadata.get('status')
            file_sip_uid = metadata.get('sip_uid')
            
            # CRITICAL FIX: If this file has a sip_number that's in the registry with a different
            # status, it's a legitimate SIP (not a duplicate). Check registry to confirm.
            is_legitimate_sip = False
            if file_sip_number is not None:
                for sip_entry in registry.get('sips', []):
                    reg_sip_number = sip_entry.get('sip_number')
                    reg_status = sip_entry.get('status')
                    reg_path_str = sip_entry.get('path', '')
                    
                    # If same number but different status, it's a legitimate SIP variant
                    if reg_sip_number == file_sip_number and reg_status != canonical_status:
                        # Verify this is the same SIP by checking path or sip_uid
                        if reg_path_str:
                            reg_path = REPO_ROOT / reg_path_str
                            if reg_path.exists() and reg_path.resolve() == sip_file.resolve():
                                is_legitimate_sip = True
                                break
                        # Also check by sip_uid if available
                        if file_sip_uid and sip_entry.get('sip_uid') == file_sip_uid:
                            is_legitimate_sip = True
                            break
            
            # Skip legitimate SIPs - they are not duplicates
            if is_legitimate_sip:
                continue
            
            # Match by sip_uid (preferred), sip_number, original_filename, or title
            is_duplicate = False
            
            # Match by sip_uid (preferred) - but only if not in registry with different status
            if sip_uid and metadata.get('sip_uid') == sip_uid:
                # Double-check: if this sip_uid is in registry with different status, it's legitimate
                is_legitimate = False
                for sip_entry in registry.get('sips', []):
                    if (sip_entry.get('sip_uid') == sip_uid and 
                        sip_entry.get('status') != canonical_status):
                        is_legitimate = True
                        break
                if not is_legitimate:
                    is_duplicate = True
            # Match by sip_number (fallback) - but exclude if it's a legitimate SIP
            elif sip_number is not None and file_sip_number == sip_number:
                # Already checked above - if it's in legitimate_sip_numbers, we skip it
                if file_sip_number not in legitimate_sip_numbers:
                    is_duplicate = True
            # Match by original_filename
            elif canonical_original_filename and metadata.get('original_filename') == canonical_original_filename:
                is_duplicate = True
            # Match by title (normalized)
            elif canonical_title:
                file_title = normalize_title(metadata.get('title', ''))
                if file_title and file_title == canonical_title:
                    is_duplicate = True
            
            if is_duplicate:
                duplicates.append(sip_file)
    
    return duplicates


def cleanup_duplicate_files(duplicate_files: list[Path]) -> int:
    """
    Safely remove duplicate SIP files.
    
    Args:
        duplicate_files: List of file paths to remove
        
    Returns:
        Number of files successfully removed
    """
    if not duplicate_files:
        return 0
    
    removed_count = 0
    failed_files = []
    
    print(f"\n🧹 Cleaning up duplicates...")
    
    for dup_file in duplicate_files:
        try:
            rel_path = dup_file.relative_to(REPO_ROOT)
            dup_file.unlink()
            print(f"   ✅ Removed: {rel_path}")
            removed_count += 1
        except Exception as e:
            failed_files.append((dup_file, str(e)))
            rel_path = dup_file.relative_to(REPO_ROOT) if dup_file.exists() else str(dup_file)
            print(f"   ❌ Failed to remove: {rel_path} ({e})")
    
    if failed_files:
        print(f"\n⚠️  Warning: {len(failed_files)} file(s) could not be removed")
    
    return removed_count


def update_sip_status(sip_file: Path, new_status: str) -> bool:
    """Update SIP status and move to appropriate lifecycle folder."""
    if not sip_file.exists():
        print(f"Error: File not found: {sip_file}")
        return False
    
    # Check maintainer flag
    if not check_maintainer_flag():
        print("Error: SQUADOPS_MAINTAINER environment variable not set.")
        print("This script can only be run by maintainers.")
        print("Set SQUADOPS_MAINTAINER=1 to proceed.")
        return False
    
    # Extract metadata
    metadata = extract_metadata_from_file(sip_file)
    if not metadata:
        print(f"Error: Could not extract metadata from {sip_file}")
        return False
    
    current_status = metadata.get('status')
    if not current_status:
        print("Error: SIP file does not have a status field")
        return False
    
    # Validate transition
    is_valid, error_msg = validate_transition(current_status, new_status)
    if not is_valid:
        print(f"Error: {error_msg}")
        return False
    
    # Load registry
    registry = load_registry()
    
    # Special handling for proposed → accepted
    if current_status == 'proposed' and new_status == 'accepted':
        # Verify file is in proposals directory
        if PROPOSED_DIR not in sip_file.parents and sip_file.parent != PROPOSED_DIR:
            print(f"Error: Proposed SIP must be in {PROPOSED_DIR}")
            return False
        
        # Assign SIP number
        sip_number = get_next_sip_number(registry)
        title = metadata.get('title', 'Untitled')
        sip_uid = metadata.get('sip_uid')
        author = metadata.get('author', 'Unknown')
        created_at = metadata.get('created_at', datetime.now().isoformat() + 'Z')
        
        # Check for and clean up duplicate files
        print(f"\n🔍 Checking for duplicate SIP files...")
        duplicates = find_duplicate_sip_files(
            sip_uid=sip_uid,
            sip_number=None,  # Not assigned yet for proposed SIPs
            canonical_file=sip_file,
            registry=registry
        )
        
        if duplicates:
            sip_identifier = f"sip_uid: {sip_uid}" if sip_uid else "proposed SIP"
            print(f"   Found {len(duplicates)} duplicate(s) for {sip_identifier}:")
            for dup in duplicates:
                print(f"   - {dup.relative_to(REPO_ROOT)}")
            
            removed_count = cleanup_duplicate_files(duplicates)
            if removed_count > 0:
                print(f"\n✅ Cleanup complete: {removed_count} duplicate file(s) removed")
        else:
            print("   No duplicates found.")
        
        # Store original file info BEFORE any modifications
        original_file_path = sip_file.resolve()
        original_file_name = sip_file.name
        original_file_dir = sip_file.parent

        # Update file metadata
        if not update_sip_file_metadata(sip_file, {'sip_number': sip_number, 'status': new_status}):
            return False

        # Generate new filename
        new_filename = normalize_filename(sip_number, title)
        target_dir = STATUS_TO_FOLDER[new_status]
        new_path = target_dir / new_filename

        # Move file using explicit copy+delete for reliability
        # (shutil.move can leave orphaned files on some filesystems)
        try:
            # Ensure target directory exists
            target_dir.mkdir(parents=True, exist_ok=True)

            # Copy to destination first
            shutil.copy2(str(sip_file), str(new_path))

            # Verify copy succeeded
            if not new_path.exists():
                print(f"Error: Destination file not found after copy: {new_path}")
                return False

            # Explicitly delete source
            try:
                sip_file.unlink()
                print(f"Moved: {original_file_name} -> {new_path.name}")
            except Exception as e_del:
                print(f"Warning: Could not delete source file after copy: {e_del}")
                print(f"   Source: {sip_file}")
                print(f"   Destination exists and is valid, continuing...")
                # Don't fail - destination is good, we'll clean up source later

        except Exception as e:
            print(f"Error copying file: {e}")
            return False

        # HARDENED: Explicit check for orphaned source file by original path
        if original_file_path.exists():
            print(f"Warning: Original file still exists at {original_file_path}")
            try:
                original_file_path.unlink()
                print(f"   ✅ Removed orphaned source file")
            except Exception as e3:
                print(f"   ❌ Failed to remove orphaned source: {e3}")
                # Continue anyway - file can be manually cleaned
        
        # Post-move cleanup: Check for residual files in source directory
        print(f"\n🔍 Checking for residual files in source directory...")
        residual_duplicates = find_duplicate_sip_files(
            sip_uid=sip_uid,
            sip_number=sip_number,  # Now assigned
            canonical_file=new_path,  # The moved file
            registry=registry
        )
        if residual_duplicates:
            print(f"   Found {len(residual_duplicates)} residual file(s):")
            for dup in residual_duplicates:
                print(f"   - {dup.relative_to(REPO_ROOT)}")
            removed_count = cleanup_duplicate_files(residual_duplicates)
            if removed_count > 0:
                print(f"\n✅ Residual cleanup complete: {removed_count} file(s) removed")
        else:
            print("   No residual files found.")

        # HARDENED: Final verification - check original directory for any file with original name
        print(f"\n🔍 Final verification: checking for orphaned files by filename...")
        orphaned_by_name = original_file_dir / original_file_name
        if orphaned_by_name.exists() and orphaned_by_name.resolve() != new_path.resolve():
            print(f"   Found orphaned file by original name: {orphaned_by_name.relative_to(REPO_ROOT)}")
            try:
                orphaned_by_name.unlink()
                print(f"   ✅ Removed orphaned file: {original_file_name}")
            except Exception as e_orphan:
                print(f"   ❌ Failed to remove orphaned file: {e_orphan}")
        else:
            print("   No orphaned files found by filename.")
        
        # Add to registry
        registry_entry = {
            'sip_uid': sip_uid,
            'sip_number': sip_number,
            'title': title,
            'path': str(new_path.relative_to(REPO_ROOT)),
            'status': new_status,
            'author': author,
            'approver': os.environ.get('USER', 'maintainer'),
            'created_at': created_at,
            'updated_at': datetime.now().isoformat() + 'Z',
        }
        
        registry['sips'].append(registry_entry)
        registry['last_assigned'] = sip_number
        
        # Sort registry by SIP number (handle None values and variant types)
        def sort_key(x):
            sip_num = x.get('sip_number') or 0
            variant = x.get('variant')
            # Handle variant: None/1 -> 0, string variants -> parse number if possible, else 999
            if variant is None or variant == 1:
                variant_sort = 0
            elif isinstance(variant, str) and variant.startswith('v'):
                try:
                    variant_sort = int(variant[1:])
                except ValueError:
                    variant_sort = 999
            else:
                variant_sort = 999
            return (sip_num, variant_sort)
        registry['sips'].sort(key=sort_key)
        
        print(f"\n✅ SIP-{sip_number:04d} status updated: {current_status} → {new_status}")
        print(f"   Title: {title}")
        print(f"   Path: {new_path.relative_to(REPO_ROOT)}")
    
    else:
        # For other transitions, SIP must be numbered
        sip_number = metadata.get('sip_number')
        if sip_number is None:
            print(f"Error: SIP must have a number to transition from {current_status} to {new_status}")
            return False
        
        # Find SIP in registry
        registry_entry = find_sip_in_registry(registry, sip_number=sip_number, sip_uid=metadata.get('sip_uid'))
        if not registry_entry:
            print(f"Error: SIP-{sip_number:04d} not found in registry")
            return False
        
        # Check for and clean up duplicate files
        print(f"\n🔍 Checking for duplicate SIP files...")
        duplicates = find_duplicate_sip_files(
            sip_uid=metadata.get('sip_uid'),
            sip_number=sip_number,
            canonical_file=sip_file,
            registry=registry
        )
        
        if duplicates:
            print(f"   Found {len(duplicates)} duplicate(s) for SIP-{sip_number:04d} (sip_uid: {metadata.get('sip_uid', 'N/A')}):")
            for dup in duplicates:
                print(f"   - {dup.relative_to(REPO_ROOT)}")
            
            # Check for registry path mismatch
            registry_path = REPO_ROOT / registry_entry.get('path', '')
            if registry_path.exists() and registry_path.resolve() != sip_file.resolve():
                if registry_path not in duplicates:
                    print(f"\n⚠️  Warning: Registry path ({registry_entry.get('path')}) doesn't match canonical file")
                    print(f"   Registry points to: {registry_path.relative_to(REPO_ROOT)}")
                    print(f"   Canonical file is: {sip_file.relative_to(REPO_ROOT)}")
            
            removed_count = cleanup_duplicate_files(duplicates)
            if removed_count > 0:
                print(f"\n✅ Cleanup complete: {removed_count} duplicate file(s) removed")
        else:
            print("   No duplicates found.")
        
        # Verify current file location matches current status
        expected_dir = STATUS_TO_FOLDER.get(current_status)
        if expected_dir and expected_dir not in sip_file.parents and sip_file.parent != expected_dir:
            print(f"Warning: SIP file location ({sip_file.parent}) doesn't match current status ({current_status})")
            print(f"Expected location: {expected_dir}")

        # Store original file info BEFORE any modifications
        original_file_path = sip_file.resolve()
        original_file_name = sip_file.name
        original_file_dir = sip_file.parent

        # Update file metadata
        if not update_sip_file_metadata(sip_file, {'status': new_status}):
            return False

        # Move file to new lifecycle folder using explicit copy+delete for reliability
        target_dir = STATUS_TO_FOLDER[new_status]
        new_path = target_dir / sip_file.name

        try:
            # Ensure target directory exists
            target_dir.mkdir(parents=True, exist_ok=True)

            # Copy to destination first
            shutil.copy2(str(sip_file), str(new_path))

            # Verify copy succeeded
            if not new_path.exists():
                print(f"Error: Destination file not found after copy: {new_path}")
                return False

            # Explicitly delete source
            try:
                sip_file.unlink()
                print(f"Moved: {original_file_name} -> {new_path.name}")
            except Exception as e_del:
                print(f"Warning: Could not delete source file after copy: {e_del}")
                print(f"   Source: {sip_file}")
                print(f"   Destination exists and is valid, continuing...")

        except Exception as e:
            print(f"Error copying file: {e}")
            return False

        # HARDENED: Explicit check for orphaned source file by original path
        if original_file_path.exists():
            print(f"Warning: Original file still exists at {original_file_path}")
            try:
                original_file_path.unlink()
                print(f"   ✅ Removed orphaned source file")
            except Exception as e3:
                print(f"   ❌ Failed to remove orphaned source: {e3}")
        
        # Update registry
        registry_entry['status'] = new_status
        registry_entry['path'] = str(new_path.relative_to(REPO_ROOT))
        registry_entry['updated_at'] = datetime.now().isoformat() + 'Z'
        
        print(f"\n✅ SIP-{sip_number:04d} status updated: {current_status} → {new_status}")
        print(f"   Path: {new_path.relative_to(REPO_ROOT)}")
    
    # Save registry
    if not save_registry(registry):
        return False
    
    return True


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: update_sip_status.py <sip_file> <new_status>")
        print("\nValid status transitions:")
        print("  proposed → accepted")
        print("  accepted → implemented")
        print("  implemented → deprecated")
        print("\nExample:")
        print("  export SQUADOPS_MAINTAINER=1")
        print("  python3 update_sip_status.py sips/proposed/SIP-PROPOSAL-My-Idea.md accepted")
        print("  python3 update_sip_status.py sips/accepted/SIP-0046-Title.md implemented")
        return 1
    
    sip_file = Path(sys.argv[1])
    new_status = sys.argv[2].lower()
    
    if not sip_file.is_absolute():
        sip_file = REPO_ROOT / sip_file
    
    if not sip_file.exists():
        print(f"Error: File not found: {sip_file}")
        return 1
    
    if new_status not in ['accepted', 'implemented', 'deprecated']:
        print(f"Error: Invalid status: {new_status}")
        print("Valid statuses: accepted, implemented, deprecated")
        return 1
    
    if update_sip_status(sip_file, new_status):
        return 0
    else:
        return 1


if __name__ == "__main__":
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML not installed. Install with: pip install pyyaml")
        exit(1)
    
    exit(main())


