#!/usr/bin/env python3
"""
SIP Number Assignment Script
Assigns SIP numbers to proposals (maintainer-only).
"""

import os
import sys
import yaml
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

REPO_ROOT = Path(__file__).parent.parent.parent
REGISTRY_FILE = REPO_ROOT / "sips" / "registry.yaml"
PROPOSALS_DIR = REPO_ROOT / "sips" / "proposals"
SIPS_DIR = REPO_ROOT / "sips"


def check_maintainer_flag() -> bool:
    """Check if maintainer flag is set."""
    maintainer = os.environ.get('SQUADOPS_MAINTAINER')
    return maintainer == '1' or maintainer == 'true' or maintainer == 'True'


def load_registry() -> Dict[str, Any]:
    """Load the SIP registry."""
    if not REGISTRY_FILE.exists():
        return {'last_assigned': 0, 'sips': []}
    
    try:
        with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {'last_assigned': 0, 'sips': []}
    except Exception as e:
        print(f"Error loading registry: {e}")
        return {'last_assigned': 0, 'sips': []}


def save_registry(registry: Dict[str, Any]) -> bool:
    """Save the registry."""
    try:
        # Backup registry first
        if REGISTRY_FILE.exists():
            backup_file = REGISTRY_FILE.with_suffix('.yaml.backup')
            import shutil
            shutil.copy2(REGISTRY_FILE, backup_file)
            print(f"Registry backed up to: {backup_file}")
        
        with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(registry, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return True
    except Exception as e:
        print(f"Error saving registry: {e}")
        return False


def get_next_sip_number(registry: Dict[str, Any]) -> int:
    """Get the next available SIP number."""
    last_assigned = registry.get('last_assigned', 0)
    return last_assigned + 1


def extract_metadata_from_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Extract metadata from SIP file YAML frontmatter."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
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


def update_sip_file(file_path: Path, sip_number: int, status: str = 'accepted') -> bool:
    """Update SIP file with new number and status."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update frontmatter
        def update_frontmatter(match):
            yaml_content = match.group(1)
            metadata = yaml.safe_load(yaml_content)
            metadata['sip_number'] = sip_number
            metadata['status'] = status
            metadata['updated_at'] = datetime.now().isoformat() + 'Z'
            
            # Convert back to YAML
            import io
            yaml_str = yaml.dump(metadata, default_flow_style=False, sort_keys=False, allow_unicode=True)
            return f"---\n{yaml_str}---\n"
        
        content = re.sub(r'^---\s*\n(.*?)\n---\s*\n', update_frontmatter, content, count=1, flags=re.DOTALL)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"Error updating SIP file: {e}")
        return False


def normalize_filename(sip_number: int, title: str, original_filename: str) -> str:
    """Generate normalized filename."""
    # Clean title for filename
    clean_title = re.sub(r'[^\w\s-]', '', title)
    clean_title = re.sub(r'\s+', '-', clean_title)
    clean_title = clean_title[:80]  # Limit length
    
    return f"SIP-{sip_number:04d}-{clean_title}.md"


def assign_number(sip_file: Path) -> bool:
    """Assign a SIP number to a proposal."""
    if not sip_file.exists():
        print(f"Error: File not found: {sip_file}")
        return False
    
    # Check maintainer flag
    if not check_maintainer_flag():
        print("Error: SQUADOPS_MAINTAINER environment variable not set.")
        print("This script can only be run by maintainers.")
        print("Set SQUADOPS_MAINTAINER=1 to proceed.")
        return False
    
    # Load registry
    registry = load_registry()
    
    # Get next number
    sip_number = get_next_sip_number(registry)
    
    # Extract metadata
    metadata = extract_metadata_from_file(sip_file)
    if not metadata:
        print(f"Error: Could not extract metadata from {sip_file}")
        return False
    
    title = metadata.get('title', 'Untitled')
    sip_uid = metadata.get('sip_uid')
    author = metadata.get('author', 'Unknown')
    created_at = metadata.get('created_at', datetime.now().isoformat() + 'Z')
    
    # Update file with new number
    if not update_sip_file(sip_file, sip_number, 'accepted'):
        return False
    
    # Generate new filename
    new_filename = normalize_filename(sip_number, title, sip_file.name)
    new_path = SIPS_DIR / new_filename
    
    # Move file
    try:
        import shutil
        shutil.move(str(sip_file), str(new_path))
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
        'status': 'accepted',
        'author': author,
        'approver': os.environ.get('USER', 'maintainer'),
        'created_at': created_at,
        'updated_at': datetime.now().isoformat() + 'Z',
    }
    
    registry['sips'].append(registry_entry)
    registry['last_assigned'] = sip_number
    
    # Sort registry by SIP number
    registry['sips'].sort(key=lambda x: x['sip_number'])
    
    # Save registry
    if not save_registry(registry):
        return False
    
    print(f"\n✅ SIP-{sip_number:04d} assigned successfully!")
    print(f"   Title: {title}")
    print(f"   Path: {new_path.relative_to(REPO_ROOT)}")
    
    return True


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: assign_sip_number.py <sip_file>")
        print("\nExample:")
        print("  export SQUADOPS_MAINTAINER=1")
        print("  python3 assign_sip_number.py sips/proposals/SIP-PROPOSAL-My-Idea.md")
        return 1
    
    sip_file = Path(sys.argv[1])
    if not sip_file.is_absolute():
        sip_file = REPO_ROOT / sip_file
    
    if not sip_file.exists():
        print(f"Error: File not found: {sip_file}")
        return 1
    
    if assign_number(sip_file):
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

