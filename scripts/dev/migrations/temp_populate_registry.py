#!/usr/bin/env python3
"""
Registry Population Script
Populates sips/registry.yaml with all numbered SIPs from migration.
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

REPO_ROOT = Path(__file__).parent.parent.parent.parent
MIGRATION_LOG = REPO_ROOT / "sips" / "MIGRATION_LOG.json"
REGISTRY_FILE = REPO_ROOT / "sips" / "registry.yaml"
SIPS_DIR = REPO_ROOT / "sips"


def load_migration_log() -> Dict[str, Any]:
    """Load migration log."""
    if not MIGRATION_LOG.exists():
        print(f"Error: Migration log not found: {MIGRATION_LOG}")
        return {}
    
    with open(MIGRATION_LOG, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_metadata_from_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Extract metadata from SIP file YAML frontmatter."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract YAML frontmatter
        import re
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if frontmatter_match:
            yaml_content = frontmatter_match.group(1)
            metadata = yaml.safe_load(yaml_content)
            return metadata
    except Exception as e:
        print(f"Warning: Could not extract metadata from {file_path}: {e}")
    
    return None


def populate_registry() -> Dict[str, Any]:
    """Populate registry with numbered SIPs."""
    migration_log = load_migration_log()
    
    if not migration_log or 'results' not in migration_log:
        print("No migration results found.")
        return {}
    
    # Collect all numbered SIPs
    numbered_sips = []
    max_number = 0
    
    for result in migration_log['results']:
        if 'error' in result:
            continue
        
        sip_number = result.get('sip_number')
        if sip_number is None:
            continue  # Skip unnumbered SIPs
        
        # Get full metadata from file
        new_path = REPO_ROOT / result['new_path']
        file_metadata = extract_metadata_from_file(new_path)
        
        if file_metadata:
            metadata = file_metadata
        else:
            # Fallback to migration result metadata
            metadata = result.get('metadata', {})
        
        # Update max number
        if sip_number > max_number:
            max_number = sip_number
        
        registry_entry = {
            'sip_uid': metadata.get('sip_uid') or result.get('sip_uid'),
            'sip_number': sip_number,
            'title': metadata.get('title') or 'Untitled',
            'path': result['new_path'],
            'status': metadata.get('status') or result.get('status', 'accepted'),
            'author': metadata.get('author', 'Unknown'),
            'approver': metadata.get('approver'),
            'created_at': metadata.get('created_at') or datetime.now().isoformat() + 'Z',
            'updated_at': metadata.get('updated_at') or datetime.now().isoformat() + 'Z',
        }
        
        numbered_sips.append(registry_entry)
    
    # Sort by SIP number
    numbered_sips.sort(key=lambda x: x['sip_number'])
    
    # Create registry structure
    registry = {
        'last_assigned': max_number,
        'sips': numbered_sips,
    }
    
    return registry


def main():
    """Main entry point."""
    print("=" * 60)
    print("Registry Population Script")
    print("=" * 60)
    
    # Populate registry
    registry = populate_registry()
    
    if not registry or 'sips' not in registry:
        print("No numbered SIPs found to register.")
        return 1
    
    # Write registry file
    try:
        with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(registry, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
        print(f"\nRegistry saved to: {REGISTRY_FILE}")
        print(f"Total numbered SIPs: {len(registry['sips'])}")
        print(f"Last assigned number: {registry['last_assigned']}")
        
        # Summary by status
        by_status = {}
        for sip in registry['sips']:
            status = sip.get('status', 'unknown')
            by_status[status] = by_status.get(status, 0) + 1
        
        print("\nStatus distribution:")
        for status, count in sorted(by_status.items()):
            print(f"  {status}: {count}")
        
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

