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
PROPOSALS_DIR = REPO_ROOT / "sips" / "proposals"
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
    'proposed': PROPOSALS_DIR,
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
        if PROPOSALS_DIR not in sip_file.parents and sip_file.parent != PROPOSALS_DIR:
            print(f"Error: Proposed SIP must be in {PROPOSALS_DIR}")
            return False
        
        # Assign SIP number
        sip_number = get_next_sip_number(registry)
        title = metadata.get('title', 'Untitled')
        sip_uid = metadata.get('sip_uid')
        author = metadata.get('author', 'Unknown')
        created_at = metadata.get('created_at', datetime.now().isoformat() + 'Z')
        
        # Update file metadata
        if not update_sip_file_metadata(sip_file, {'sip_number': sip_number, 'status': new_status}):
            return False
        
        # Generate new filename
        new_filename = normalize_filename(sip_number, title)
        target_dir = STATUS_TO_FOLDER[new_status]
        new_path = target_dir / new_filename
        
        # Move file
        try:
            shutil.move(str(sip_file), str(new_path))
            # Verify move succeeded
            if sip_file.exists():
                print(f"Warning: Source file still exists after move. Attempting to remove...")
                try:
                    sip_file.unlink()
                    print(f"Removed duplicate source file: {sip_file.name}")
                except Exception as e2:
                    print(f"Error removing duplicate source file: {e2}")
                    return False
            if not new_path.exists():
                print(f"Error: Destination file not found after move: {new_path}")
                return False
            print(f"Moved: {sip_file.name} -> {new_path.name}")
        except Exception as e:
            print(f"Error moving file: {e}")
            return False
        
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
        
        # Sort registry by SIP number (handle None values)
        registry['sips'].sort(key=lambda x: (x.get('sip_number') or 0, x.get('variant') or 1))
        
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
        
        # Verify current file location matches current status
        expected_dir = STATUS_TO_FOLDER.get(current_status)
        if expected_dir and expected_dir not in sip_file.parents and sip_file.parent != expected_dir:
            print(f"Warning: SIP file location ({sip_file.parent}) doesn't match current status ({current_status})")
            print(f"Expected location: {expected_dir}")
        
        # Update file metadata
        if not update_sip_file_metadata(sip_file, {'status': new_status}):
            return False
        
        # Move file to new lifecycle folder
        target_dir = STATUS_TO_FOLDER[new_status]
        new_path = target_dir / sip_file.name
        
        try:
            # Ensure target directory exists
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(sip_file), str(new_path))
            # Verify move succeeded
            if sip_file.exists():
                print(f"Warning: Source file still exists after move. Attempting to remove...")
                try:
                    sip_file.unlink()
                    print(f"Removed duplicate source file: {sip_file.name}")
                except Exception as e2:
                    print(f"Error removing duplicate source file: {e2}")
                    return False
            if not new_path.exists():
                print(f"Error: Destination file not found after move: {new_path}")
                return False
            print(f"Moved: {sip_file.name} -> {new_path.name}")
        except Exception as e:
            print(f"Error moving file: {e}")
            return False
        
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
        print("  python3 update_sip_status.py sips/proposals/SIP-PROPOSAL-My-Idea.md accepted")
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


