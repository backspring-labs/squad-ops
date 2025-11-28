#!/usr/bin/env python3
"""
SIP Migration Script
Migrates SIPs from docs/SIPs/ to new sips/ structure with standardized metadata.
"""

import os
import json
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import subprocess

REPO_ROOT = Path(__file__).parent.parent.parent.parent
ANALYSIS_FILE = REPO_ROOT / "sips" / "SIP_ANALYSIS_REPORT.json"
INVENTORY_FILE = REPO_ROOT / "sips" / "MIGRATION_INVENTORY.json"
DOCS_SIPS_DIR = REPO_ROOT / "docs" / "SIPs"
SIPS_DIR = REPO_ROOT / "sips"
PROPOSALS_DIR = SIPS_DIR / "proposals"


def generate_ulid() -> str:
    """Generate a ULID."""
    try:
        from ulid import ULID
        return str(ULID())
    except ImportError:
        # Fallback: use timestamp-based ID
        import time
        import random
        timestamp = int(time.time() * 1000)
        random_part = random.randint(1000, 9999)
        return f"{timestamp:013d}{random_part:04d}"


def extract_title_from_content(content: str, filename: str) -> Optional[str]:
    """Extract title from SIP content."""
    # Try various title patterns
    patterns = [
        r'#+\s+SIP[-\d]*[:\s]+(.+)',
        r'##\s+Title[:\s]+(.+)',
        r'Title[:\s]+(.+)',
        r'#\s+(.+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            title = match.group(1).strip()
            # Clean up title
            title = re.sub(r'[^\w\s-]', '', title)
            title = re.sub(r'\s+', '-', title)
            return title[:100]  # Limit length
    
    # Fallback: use filename
    base = Path(filename).stem
    if base.startswith('SIP-'):
        return base[4:].replace('_', '-')
    return base.replace('_', '-')


def extract_author_from_content(content: str) -> Optional[str]:
    """Extract author from SIP content."""
    patterns = [
        r'\*\*Author[:\s]+\*\*(.+)',
        r'Author[:\s]+(.+)',
        r'##\s+Author[:\s]+(.+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            author = match.group(1).strip()
            # Remove markdown formatting
            author = re.sub(r'\*\*|__|`', '', author)
            return author[:100]
    
    return None


def extract_date_from_content(content: str) -> Optional[str]:
    """Extract date from SIP content."""
    patterns = [
        r'\*\*Date[:\s]+\*\*(.+)',
        r'Date[:\s]+(.+)',
        r'created_at[:\s]+(.+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            date_str = match.group(1).strip()
            # Try to parse and format as ISO
            try:
                # Common date formats
                for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.isoformat() + 'Z'
                    except ValueError:
                        continue
                return date_str
            except Exception:
                return date_str
    
    return None


def get_file_mtime(file_path: Path) -> str:
    """Get file modification time as ISO string."""
    try:
        mtime = file_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).isoformat() + 'Z'
    except Exception:
        return datetime.now().isoformat() + 'Z'


def normalize_filename(sip_number: Optional[int], title: str, original_filename: str) -> str:
    """Generate normalized filename."""
    if sip_number is not None:
        return f"SIP-{sip_number:04d}-{title}.md"
    else:
        # For proposals, use descriptive name
        base = Path(original_filename).stem
        if base.startswith('SIP-'):
            return f"SIP-PROPOSAL-{base[4:]}.md"
        return f"SIP-PROPOSAL-{base}.md"


def add_yaml_frontmatter(content: str, metadata: Dict[str, Any]) -> str:
    """Add or update YAML frontmatter in SIP content."""
    # Check if frontmatter already exists
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.match(frontmatter_pattern, content, re.DOTALL)
    
    yaml_lines = []
    yaml_lines.append("---")
    yaml_lines.append(f"sip_uid: \"{metadata['sip_uid']}\"")
    yaml_lines.append(f"sip_number: {metadata['sip_number'] if metadata['sip_number'] is not None else 'null'}")
    yaml_lines.append(f"title: \"{metadata['title']}\"")
    yaml_lines.append(f"status: \"{metadata['status']}\"")
    yaml_lines.append(f"author: \"{metadata.get('author', 'Unknown')}\"")
    yaml_lines.append(f"approver: {metadata.get('approver', 'null')}")
    yaml_lines.append(f"created_at: \"{metadata['created_at']}\"")
    yaml_lines.append(f"updated_at: \"{metadata['updated_at']}\"")
    yaml_lines.append(f"original_filename: \"{metadata['original_filename']}\"")
    yaml_lines.append("---")
    yaml_lines.append("")
    
    yaml_block = "\n".join(yaml_lines)
    
    if match:
        # Replace existing frontmatter
        return re.sub(frontmatter_pattern, yaml_block + "\n", content, count=1, flags=re.DOTALL)
    else:
        # Add new frontmatter at the beginning
        return yaml_block + "\n" + content


def migrate_sip(sip_data: Dict[str, Any], inventory_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate a single SIP file."""
    original_path = REPO_ROOT / sip_data['original_path']
    sip_number = sip_data.get('sip_number')
    status = sip_data.get('status', 'proposed')
    target_location = sip_data.get('target_location', 'proposals')
    
    # Read original file
    try:
        with open(original_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {original_path}: {e}")
        return {'error': str(e)}
    
    # Extract metadata
    title = extract_title_from_content(content, sip_data['filename'])
    author = extract_author_from_content(content) or inventory_entry.get('metadata', {}).get('author')
    date = extract_date_from_content(content) or inventory_entry.get('metadata', {}).get('date')
    created_at = date or get_file_mtime(original_path)
    
    # Generate ULID
    sip_uid = generate_ulid()
    
    # Prepare metadata
    metadata = {
        'sip_uid': sip_uid,
        'sip_number': sip_number,
        'title': title or 'Untitled',
        'status': status,
        'author': author or 'Unknown',
        'approver': None,
        'created_at': created_at,
        'updated_at': datetime.now().isoformat() + 'Z',
        'original_filename': sip_data['filename'],
    }
    
    # Add YAML frontmatter
    content_with_frontmatter = add_yaml_frontmatter(content, metadata)
    
    # Determine target directory
    if target_location == 'sips' and sip_number is not None:
        target_dir = SIPS_DIR
    else:
        target_dir = PROPOSALS_DIR
    
    # Generate new filename
    new_filename = normalize_filename(sip_number, title or 'Untitled', sip_data['filename'])
    target_path = target_dir / new_filename
    
    # Ensure target directory exists
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Write migrated file
    try:
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content_with_frontmatter)
        print(f"  Migrated: {sip_data['filename']} -> {target_path.relative_to(REPO_ROOT)}")
    except Exception as e:
        print(f"Error writing {target_path}: {e}")
        return {'error': str(e)}
    
    return {
        'original_path': str(original_path.relative_to(REPO_ROOT)),
        'new_path': str(target_path.relative_to(REPO_ROOT)),
        'sip_uid': sip_uid,
        'sip_number': sip_number,
        'status': status,
        'metadata': metadata,
    }


def main():
    """Main entry point."""
    print("=" * 60)
    print("SIP Migration Script")
    print("=" * 60)
    
    # Load analysis report
    if not ANALYSIS_FILE.exists():
        print(f"Error: Analysis report not found: {ANALYSIS_FILE}")
        print("Run analyze_sip_status.py first.")
        return 1
    
    with open(ANALYSIS_FILE, 'r', encoding='utf-8') as f:
        analysis = json.load(f)
    
    # Load inventory for additional metadata
    inventory = {}
    if INVENTORY_FILE.exists():
        with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
            inv_data = json.load(f)
            for entry in inv_data.get('sips', []):
                inventory[entry['filename']] = entry
    
    # Ensure directories exist
    SIPS_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Migrate each SIP
    migration_results = []
    print(f"\nMigrating {len(analysis['sips'])} SIPs...\n")
    
    for sip_data in analysis['sips']:
        inventory_entry = inventory.get(sip_data['filename'], {})
        result = migrate_sip(sip_data, inventory_entry)
        migration_results.append(result)
    
    # Save migration log
    migration_log = {
        'migrated_at': datetime.now().isoformat(),
        'total_migrated': len(migration_results),
        'results': migration_results,
    }
    
    log_file = SIPS_DIR / "MIGRATION_LOG.json"
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(migration_log, f, indent=2, ensure_ascii=False)
    
    print(f"\nMigration complete!")
    print(f"Migration log saved to: {log_file}")
    print(f"Total SIPs migrated: {len(migration_results)}")
    
    # Summary
    by_location = {}
    by_status = {}
    for result in migration_results:
        if 'error' in result:
            continue
        loc = 'sips' if result.get('sip_number') else 'proposals'
        by_location[loc] = by_location.get(loc, 0) + 1
        status = result.get('status', 'unknown')
        by_status[status] = by_status.get(status, 0) + 1
    
    print("\nMigration summary:")
    print("By location:")
    for loc, count in sorted(by_location.items()):
        print(f"  {loc}: {count}")
    print("By status:")
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")
    
    return 0


if __name__ == "__main__":
    exit(main())

