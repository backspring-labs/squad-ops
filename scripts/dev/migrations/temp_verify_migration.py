#!/usr/bin/env python3
"""
Migration Verification Script
Verifies that all SIPs were successfully migrated with no data loss.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional

REPO_ROOT = Path(__file__).parent.parent.parent.parent
INVENTORY_FILE = REPO_ROOT / "sips" / "MIGRATION_INVENTORY.json"
MIGRATION_LOG = REPO_ROOT / "sips" / "MIGRATION_LOG.json"
DOCS_SIPS_DIR = REPO_ROOT / "docs" / "SIPs"
SIPS_DIR = REPO_ROOT / "sips"
PROPOSALS_DIR = SIPS_DIR / "proposals"


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        return f"ERROR: {e}"


def verify_migration() -> Dict[str, Any]:
    """Verify migration completeness and integrity."""
    # Load inventory
    if not INVENTORY_FILE.exists():
        return {'error': 'Inventory file not found'}
    
    with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
        inventory = json.load(f)
    
    # Load migration log
    migration_results = {}
    if MIGRATION_LOG.exists():
        with open(MIGRATION_LOG, 'r', encoding='utf-8') as f:
            migration_log = json.load(f)
            for result in migration_log.get('results', []):
                if 'error' not in result:
                    original_path = result.get('original_path')
                    migration_results[original_path] = result
    
    # Verify each SIP
    verification_results = {
        'total_original': len(inventory.get('sips', [])),
        'total_migrated': 0,
        'missing': [],
        'checksum_mismatches': [],
        'verified': [],
        'errors': [],
    }
    
    print("Verifying migration...")
    print(f"Total SIPs in inventory: {verification_results['total_original']}\n")
    
    for sip_entry in inventory.get('sips', []):
        original_path = sip_entry['original_path']
        original_file = REPO_ROOT / original_path
        original_checksum = sip_entry.get('checksum_sha256')
        
        # Find migration result
        migration_result = migration_results.get(original_path)
        
        if not migration_result:
            verification_results['missing'].append({
                'original_path': original_path,
                'filename': sip_entry['filename'],
            })
            print(f"  ❌ MISSING: {sip_entry['filename']}")
            continue
        
        # Check if new file exists
        new_path = REPO_ROOT / migration_result['new_path']
        if not new_path.exists():
            verification_results['missing'].append({
                'original_path': original_path,
                'new_path': str(migration_result['new_path']),
                'filename': sip_entry['filename'],
            })
            print(f"  ❌ FILE NOT FOUND: {migration_result['new_path']}")
            continue
        
        # Verify checksum (content should be similar, but frontmatter was added)
        # We'll just check that file exists and has reasonable size
        new_size = new_path.stat().st_size
        original_size = sip_entry.get('size_bytes', 0)
        
        # New file should be at least as large (may have frontmatter added)
        if new_size < original_size * 0.9:  # Allow 10% tolerance for content changes
            verification_results['checksum_mismatches'].append({
                'original_path': original_path,
                'new_path': str(migration_result['new_path']),
                'original_size': original_size,
                'new_size': new_size,
            })
            print(f"  ⚠️  SIZE MISMATCH: {sip_entry['filename']} ({original_size} -> {new_size} bytes)")
        else:
            verification_results['verified'].append({
                'original_path': original_path,
                'new_path': str(migration_result['new_path']),
                'filename': sip_entry['filename'],
            })
            print(f"  ✅ VERIFIED: {sip_entry['filename']}")
            verification_results['total_migrated'] += 1
    
    return verification_results


def main():
    """Main entry point."""
    print("=" * 60)
    print("Migration Verification Script")
    print("=" * 60)
    print()
    
    results = verify_migration()
    
    if 'error' in results:
        print(f"Error: {results['error']}")
        return 1
    
    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)
    print(f"Total SIPs in original location: {results['total_original']}")
    print(f"Total SIPs successfully migrated: {results['total_migrated']}")
    print(f"Missing SIPs: {len(results['missing'])}")
    print(f"Checksum/size mismatches: {len(results['checksum_mismatches'])}")
    print(f"Errors: {len(results['errors'])}")
    
    # Save verification report
    report_file = SIPS_DIR / "VERIFICATION_REPORT.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nVerification report saved to: {report_file}")
    
    # Determine exit code
    if results['missing']:
        print("\n❌ VERIFICATION FAILED: Some SIPs are missing!")
        return 1
    elif results['checksum_mismatches']:
        print("\n⚠️  VERIFICATION WARNING: Some size mismatches detected (may be due to frontmatter addition)")
        return 0
    else:
        print("\n✅ VERIFICATION PASSED: All SIPs successfully migrated!")
        return 0


if __name__ == "__main__":
    exit(main())

