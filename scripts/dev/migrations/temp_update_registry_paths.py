#!/usr/bin/env python3
"""
Update Registry Paths Script
Updates registry.yaml with new paths after reorganization.
"""

import yaml
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

REPO_ROOT = Path(__file__).parent.parent.parent.parent
REGISTRY_FILE = REPO_ROOT / "sips" / "registry.yaml"
ACCEPTED_DIR = REPO_ROOT / "sips" / "accepted"
IMPLEMENTED_DIR = REPO_ROOT / "sips" / "implemented"
DEPRECATED_DIR = REPO_ROOT / "sips" / "deprecated"
PROPOSALS_DIR = REPO_ROOT / "sips" / "proposals"


def extract_metadata_from_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Extract metadata from SIP file YAML frontmatter."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if frontmatter_match:
            metadata = yaml.safe_load(frontmatter_match.group(1))
            return metadata
    except Exception as e:
        print(f"Warning: Could not extract metadata from {file_path}: {e}")
    
    return None


def scan_sip_directories() -> List[Dict[str, Any]]:
    """Scan all SIP directories and collect SIP information."""
    sips = []
    
    directories = [
        (ACCEPTED_DIR, 'accepted'),
        (IMPLEMENTED_DIR, 'implemented'),
        (DEPRECATED_DIR, 'deprecated'),
        (PROPOSALS_DIR, 'proposed'),
    ]
    
    for directory, status in directories:
        if not directory.exists():
            continue
        
        for sip_file in directory.glob("SIP-*.md"):
            metadata = extract_metadata_from_file(sip_file)
            if not metadata:
                # Try to extract from filename
                match = re.search(r'SIP-(\d+)', sip_file.name)
                if match:
                    metadata = {'sip_number': int(match.group(1))}
                else:
                    continue
            
            sip_number = metadata.get('sip_number')
            if sip_number is None and status != 'proposed':
                continue  # Skip unnumbered SIPs outside proposals
            
            # Determine variant from filename
            variant_match = re.search(r'-v(\d+)-', sip_file.name)
            variant = int(variant_match.group(1)) if variant_match else 1
            
            registry_entry = {
                'sip_uid': metadata.get('sip_uid', ''),
                'sip_number': sip_number,
                'title': metadata.get('title', Path(sip_file).stem),
                'path': str(sip_file.relative_to(REPO_ROOT)),
                'status': metadata.get('status', status),
                'author': metadata.get('author', 'Unknown'),
                'approver': metadata.get('approver'),
                'created_at': metadata.get('created_at', datetime.now().isoformat() + 'Z'),
                'updated_at': metadata.get('updated_at', datetime.now().isoformat() + 'Z'),
                'variant': variant if variant > 1 else None,
            }
            
            sips.append(registry_entry)
    
    return sips


def update_registry() -> Dict[str, Any]:
    """Update registry with new paths."""
    # Load existing registry if it exists
    existing_registry = {'last_assigned': 0, 'sips': []}
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
                existing_registry = yaml.safe_load(f) or existing_registry
        except Exception as e:
            print(f"Warning: Could not load existing registry: {e}")
    
    # Scan directories
    sips = scan_sip_directories()
    
    # Filter to only numbered SIPs for registry
    numbered_sips = [sip for sip in sips if sip['sip_number'] is not None]
    
    # Sort by SIP number, then variant
    numbered_sips.sort(key=lambda x: (x['sip_number'], x.get('variant') or 1))
    
    # Find max number
    max_number = max([sip['sip_number'] for sip in numbered_sips], default=0)
    
    # Create new registry
    registry = {
        'last_assigned': max_number,
        'sips': numbered_sips,
    }
    
    return registry


def main():
    """Main entry point."""
    print("=" * 60)
    print("Update Registry Paths Script")
    print("=" * 60)
    print()
    
    # Update registry
    registry = update_registry()
    
    # Backup existing registry
    if REGISTRY_FILE.exists():
        backup_file = REGISTRY_FILE.with_suffix('.yaml.backup')
        import shutil
        shutil.copy2(REGISTRY_FILE, backup_file)
        print(f"Backed up existing registry to: {backup_file}")
    
    # Write new registry
    try:
        with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(registry, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        print(f"\nRegistry updated: {REGISTRY_FILE}")
        print(f"Total numbered SIPs: {len(registry['sips'])}")
        print(f"Last assigned number: {registry['last_assigned']}")
        
        # Summary by status
        by_status = {}
        by_folder = {}
        for sip in registry['sips']:
            status = sip.get('status', 'unknown')
            by_status[status] = by_status.get(status, 0) + 1
            
            folder = Path(sip['path']).parent.name
            by_folder[folder] = by_folder.get(folder, 0) + 1
        
        print("\nBy status:")
        for status, count in sorted(by_status.items()):
            print(f"  {status}: {count}")
        
        print("\nBy folder:")
        for folder, count in sorted(by_folder.items()):
            print(f"  {folder}: {count}")
        
    except Exception as e:
        print(f"Error writing registry: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML not installed. Install with: pip install pyyaml")
        exit(1)
    
    exit(main())

