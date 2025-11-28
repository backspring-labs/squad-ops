#!/usr/bin/env python3
"""
SIP Inventory Script
Creates a complete inventory of all SIPs in docs/SIPs/ before migration.
"""

import os
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

REPO_ROOT = Path(__file__).parent.parent.parent.parent
DOCS_SIPS_DIR = REPO_ROOT / "docs" / "SIPs"
OUTPUT_FILE = REPO_ROOT / "sips" / "MIGRATION_INVENTORY.json"


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_sip_number(filename: str) -> Optional[int]:
    """Extract SIP number from filename."""
    match = re.search(r'SIP-(\d+)', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def extract_metadata(file_path: Path) -> Dict[str, Any]:
    """Extract metadata from SIP file."""
    metadata = {
        'status': None,
        'title': None,
        'author': None,
        'date': None,
        'sip_number': None,
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            
            # Extract SIP number from filename
            sip_num = extract_sip_number(file_path.name)
            if sip_num:
                metadata['sip_number'] = sip_num
            
            # Look for metadata in first 50 lines
            for i, line in enumerate(lines[:50]):
                # Status patterns
                if re.search(r'Status[:\s]+', line, re.IGNORECASE):
                    status_match = re.search(r'Status[:\s]+([^\n]+)', line, re.IGNORECASE)
                    if status_match:
                        metadata['status'] = status_match.group(1).strip()
                
                # Title patterns
                if re.search(r'Title[:\s]+|#+\s+SIP[-\d]*[:\s]+', line, re.IGNORECASE):
                    title_match = re.search(r'(?:Title[:\s]+|#+\s+SIP[-\d]*[:\s]+)([^\n]+)', line, re.IGNORECASE)
                    if title_match:
                        metadata['title'] = title_match.group(1).strip()
                
                # Author patterns
                if re.search(r'Author[:\s]+', line, re.IGNORECASE):
                    author_match = re.search(r'Author[:\s]+([^\n]+)', line, re.IGNORECASE)
                    if author_match:
                        metadata['author'] = author_match.group(1).strip()
                
                # Date patterns
                if re.search(r'Date[:\s]+', line, re.IGNORECASE):
                    date_match = re.search(r'Date[:\s]+([^\n]+)', line, re.IGNORECASE)
                    if date_match:
                        metadata['date'] = date_match.group(1).strip()
    
    except Exception as e:
        print(f"Warning: Could not extract metadata from {file_path}: {e}")
    
    return metadata


def inventory_sips() -> List[Dict[str, Any]]:
    """Create inventory of all SIPs."""
    if not DOCS_SIPS_DIR.exists():
        print(f"Error: {DOCS_SIPS_DIR} does not exist")
        return []
    
    inventory = []
    sip_files = sorted(DOCS_SIPS_DIR.glob("*.md"))
    
    print(f"Found {len(sip_files)} SIP files in {DOCS_SIPS_DIR}")
    
    for sip_file in sip_files:
        file_stat = sip_file.stat()
        checksum = calculate_checksum(sip_file)
        metadata = extract_metadata(sip_file)
        
        # Determine initial target location guess
        target_location = "proposals"
        if metadata.get('sip_number'):
            target_location = "sips"
        
        entry = {
            'original_path': str(sip_file.relative_to(REPO_ROOT)),
            'filename': sip_file.name,
            'size_bytes': file_stat.st_size,
            'checksum_sha256': checksum,
            'modified_time': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
            'metadata': metadata,
            'target_location_guess': target_location,
        }
        
        inventory.append(entry)
        print(f"  - {sip_file.name} (SIP-{metadata.get('sip_number', '?')}, {file_stat.st_size} bytes)")
    
    return inventory


def main():
    """Main entry point."""
    print("=" * 60)
    print("SIP Inventory Script")
    print("=" * 60)
    
    # Create output directory if it doesn't exist
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate inventory
    inventory = inventory_sips()
    
    if not inventory:
        print("No SIPs found. Exiting.")
        return 1
    
    # Create inventory structure
    inventory_data = {
        'generated_at': datetime.now().isoformat(),
        'source_directory': str(DOCS_SIPS_DIR.relative_to(REPO_ROOT)),
        'total_sips': len(inventory),
        'sips': inventory,
    }
    
    # Write inventory file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(inventory_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nInventory saved to: {OUTPUT_FILE}")
    print(f"Total SIPs inventoried: {len(inventory)}")
    
    # Summary by target location
    by_location = {}
    for sip in inventory:
        loc = sip['target_location_guess']
        by_location[loc] = by_location.get(loc, 0) + 1
    
    print("\nInitial target location distribution:")
    for loc, count in sorted(by_location.items()):
        print(f"  {loc}: {count}")
    
    return 0


if __name__ == "__main__":
    exit(main())

