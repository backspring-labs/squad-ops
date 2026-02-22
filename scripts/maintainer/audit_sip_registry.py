#!/usr/bin/env python3
"""
SIP Registry Audit Script
Comprehensive validation of sips/registry.yaml against actual SIP files.
Identifies issues and provides cleanup recommendations.
"""

import os
import re
import sys
from collections import defaultdict
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

# Status to folder mapping
STATUS_TO_FOLDER = {
    'proposed': PROPOSED_DIR,
    'accepted': ACCEPTED_DIR,
    'implemented': IMPLEMENTED_DIR,
    'deprecated': DEPRECATED_DIR,
}

# Folder to status mapping (reverse)
FOLDER_TO_STATUS = {
    PROPOSED_DIR: 'proposed',
    ACCEPTED_DIR: 'accepted',
    IMPLEMENTED_DIR: 'implemented',
    DEPRECATED_DIR: 'deprecated',
}


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
        return None
    
    return None


def is_valid_iso_timestamp(value: Any) -> bool:
    """Check if value is a valid ISO 8601 timestamp."""
    if not isinstance(value, str):
        return False
    
    # Check for ISO 8601 format: YYYY-MM-DDTHH:MM:SS[.sss][Z]
    pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?$'
    return bool(re.match(pattern, value))


def find_all_sip_files() -> dict[str, Path]:
    """Find all SIP files in lifecycle directories."""
    files = {}
    lifecycle_dirs = [PROPOSED_DIR, ACCEPTED_DIR, IMPLEMENTED_DIR, DEPRECATED_DIR]
    
    for lifecycle_dir in lifecycle_dirs:
        if not lifecycle_dir.exists():
            continue
        
        for sip_file in lifecycle_dir.glob("*.md"):
            files[sip_file.name] = sip_file
    
    return files


def audit_registry() -> dict[str, Any]:
    """Perform comprehensive audit of SIP registry."""
    registry = load_registry()
    all_files = find_all_sip_files()
    
    issues = {
        'critical': [],
        'data_quality': [],
        'informational': [],
    }
    
    # Track duplicates
    sip_numbers: dict[int, list[dict[str, Any]]] = defaultdict(list)
    sip_uids: dict[str, list[dict[str, Any]]] = defaultdict(list)
    
    # Track registry paths
    registry_paths = set()
    registry_files = set()
    
    # Validate each registry entry
    for sip in registry.get('sips', []):
        sip_number = sip.get('sip_number')
        sip_uid = sip.get('sip_uid')
        path = sip.get('path')
        status = sip.get('status')
        title = sip.get('title', 'Unknown')
        
        # Track for duplicate detection
        if sip_number is not None:
            sip_numbers[sip_number].append(sip)
        if sip_uid:
            sip_uids[sip_uid].append(sip)
        
        # Check 1: File existence
        if path:
            registry_paths.add(path)
            file_path = REPO_ROOT / path
            registry_files.add(file_path.name)
            
            if not file_path.exists():
                issues['critical'].append({
                    'type': 'missing_file',
                    'sip_number': sip_number,
                    'sip_uid': sip_uid,
                    'title': title,
                    'registry_path': path,
                    'message': f"Registry path does not exist: {path}",
                })
                continue
            
            # Check 2: Status/folder match
            expected_folder = STATUS_TO_FOLDER.get(status)
            if expected_folder and file_path.parent != expected_folder:
                issues['critical'].append({
                    'type': 'status_folder_mismatch',
                    'sip_number': sip_number,
                    'sip_uid': sip_uid,
                    'title': title,
                    'registry_status': status,
                    'registry_path': path,
                    'actual_folder': str(file_path.parent.relative_to(REPO_ROOT)),
                    'expected_folder': str(expected_folder.relative_to(REPO_ROOT)),
                    'message': f"Status '{status}' doesn't match folder location",
                })
            
            # Check 3: Metadata consistency
            file_metadata = extract_metadata_from_file(file_path)
            if file_metadata:
                # Check sip_number match
                file_sip_number = file_metadata.get('sip_number')
                if file_sip_number != sip_number:
                    issues['data_quality'].append({
                        'type': 'metadata_mismatch',
                        'sip_number': sip_number,
                        'sip_uid': sip_uid,
                        'title': title,
                        'field': 'sip_number',
                        'registry_value': sip_number,
                        'file_value': file_sip_number,
                        'message': f"sip_number mismatch: registry={sip_number}, file={file_sip_number}",
                    })
                
                # Check sip_uid match
                file_sip_uid = file_metadata.get('sip_uid')
                if file_sip_uid and file_sip_uid != sip_uid:
                    issues['data_quality'].append({
                        'type': 'metadata_mismatch',
                        'sip_number': sip_number,
                        'sip_uid': sip_uid,
                        'title': title,
                        'field': 'sip_uid',
                        'registry_value': sip_uid,
                        'file_value': file_sip_uid,
                        'message': f"sip_uid mismatch: registry={sip_uid}, file={file_sip_uid}",
                    })
                
                # Check status match
                file_status = file_metadata.get('status')
                if file_status and file_status != status:
                    issues['data_quality'].append({
                        'type': 'metadata_mismatch',
                        'sip_number': sip_number,
                        'sip_uid': sip_uid,
                        'title': title,
                        'field': 'status',
                        'registry_value': status,
                        'file_value': file_status,
                        'message': f"status mismatch: registry={status}, file={file_status}",
                    })
        
        # Check 4: Invalid timestamps
        created_at = sip.get('created_at')
        if created_at and not is_valid_iso_timestamp(created_at):
            issues['data_quality'].append({
                'type': 'invalid_timestamp',
                'sip_number': sip_number,
                'sip_uid': sip_uid,
                'title': title,
                'field': 'created_at',
                'value': str(created_at),
                'message': f"Invalid created_at format: {created_at}",
            })
        
        updated_at = sip.get('updated_at')
        if updated_at and not is_valid_iso_timestamp(updated_at):
            issues['data_quality'].append({
                'type': 'invalid_timestamp',
                'sip_number': sip_number,
                'sip_uid': sip_uid,
                'title': title,
                'field': 'updated_at',
                'value': str(updated_at),
                'message': f"Invalid updated_at format: {updated_at}",
            })
        
        # Check 5: Inconsistent approver field
        approver = sip.get('approver')
        if approver is not None and approver != 'null' and approver != 'None':
            # This is fine, just checking for None vs null inconsistency
            pass
    
    # Check 6: Duplicate detection
    for sip_number, entries in sip_numbers.items():
        if len(entries) > 1:
            # Check if variants are set
            variants = [e.get('variant') for e in entries]
            if None in variants or not all(v is not None for v in variants):
                issues['data_quality'].append({
                    'type': 'duplicate_number_missing_variant',
                    'sip_number': sip_number,
                    'entries': [{'title': e.get('title'), 'variant': e.get('variant')} for e in entries],
                    'message': f"Multiple SIPs with number {sip_number} but missing variant fields",
                })
    
    for sip_uid, entries in sip_uids.items():
        if len(entries) > 1:
            issues['critical'].append({
                'type': 'duplicate_uid',
                'sip_uid': sip_uid,
                'entries': [{'sip_number': e.get('sip_number'), 'title': e.get('title')} for e in entries],
                'message': f"Duplicate sip_uid: {sip_uid}",
            })
    
    # Check 7: Orphaned files (not in registry)
    for filename, file_path in all_files.items():
        if filename not in registry_files:
            metadata = extract_metadata_from_file(file_path)
            if metadata:
                sip_number = metadata.get('sip_number')
                if sip_number is None:
                    # Proposals are expected to not be in registry
                    issues['informational'].append({
                        'type': 'orphaned_proposal',
                        'file': str(file_path.relative_to(REPO_ROOT)),
                        'sip_uid': metadata.get('sip_uid'),
                        'title': metadata.get('title'),
                        'message': f"Proposal file not in registry: {filename}",
                    })
                else:
                    issues['critical'].append({
                        'type': 'orphaned_numbered_file',
                        'file': str(file_path.relative_to(REPO_ROOT)),
                        'sip_number': sip_number,
                        'sip_uid': metadata.get('sip_uid'),
                        'title': metadata.get('title'),
                        'message': f"Numbered SIP file not in registry: {filename} (SIP-{sip_number:04d})",
                    })
            else:
                issues['data_quality'].append({
                    'type': 'orphaned_file_no_metadata',
                    'file': str(file_path.relative_to(REPO_ROOT)),
                    'message': f"File not in registry and has no metadata: {filename}",
                })
    
    # Check 8: Missing SIP numbers (informational only)
    last_assigned = registry.get('last_assigned', 0)
    all_numbers = {sip.get('sip_number') for sip in registry.get('sips', []) if sip.get('sip_number') is not None}
    expected = set(range(1, last_assigned + 1))
    missing = sorted(expected - all_numbers)
    
    if missing:
        issues['informational'].append({
            'type': 'missing_numbers',
            'missing': missing,
            'last_assigned': last_assigned,
            'message': f"Missing SIP numbers: {missing} (acceptable gaps, no action needed)",
        })
    
    return {
        'registry': registry,
        'all_files': all_files,
        'issues': issues,
        'stats': {
            'total_registry_entries': len(registry.get('sips', [])),
            'total_files': len(all_files),
            'critical_count': len(issues['critical']),
            'data_quality_count': len(issues['data_quality']),
            'informational_count': len(issues['informational']),
        },
    }


def print_audit_report(audit_results: dict[str, Any]) -> None:
    """Print comprehensive audit report."""
    issues = audit_results['issues']
    stats = audit_results['stats']
    
    print("=" * 60)
    print("SIP Registry Audit Report")
    print("=" * 60)
    print()
    
    print("Summary:")
    print(f"  - Total registry entries: {stats['total_registry_entries']}")
    print(f"  - Total SIP files: {stats['total_files']}")
    print(f"  - Critical issues: {stats['critical_count']}")
    print(f"  - Data quality issues: {stats['data_quality_count']}")
    print(f"  - Informational items: {stats['informational_count']}")
    print()
    
    # Critical Issues
    if issues['critical']:
        print("=" * 60)
        print(f"CRITICAL ISSUES ({len(issues['critical'])}):")
        print("=" * 60)
        for i, issue in enumerate(issues['critical'], 1):
            sip_num = issue.get('sip_number')
            sip_uid = issue.get('sip_uid', 'N/A')
            title = issue.get('title', 'Unknown')
            print(f"\n{i}. {issue['type'].upper().replace('_', ' ')}")
            if sip_num is not None:
                print(f"   SIP-{sip_num:04d}: {title}")
            else:
                print(f"   Title: {title}")
            print(f"   sip_uid: {sip_uid}")
            print(f"   {issue['message']}")
            if 'registry_path' in issue:
                print(f"   Registry path: {issue['registry_path']}")
            if 'actual_folder' in issue:
                print(f"   Actual folder: {issue['actual_folder']}")
                print(f"   Expected folder: {issue['expected_folder']}")
        print()
    
    # Data Quality Issues
    if issues['data_quality']:
        print("=" * 60)
        print(f"DATA QUALITY ISSUES ({len(issues['data_quality'])}):")
        print("=" * 60)
        for i, issue in enumerate(issues['data_quality'], 1):
            sip_num = issue.get('sip_number')
            title = issue.get('title', 'Unknown')
            print(f"\n{i}. {issue['type'].upper().replace('_', ' ')}")
            if sip_num is not None:
                print(f"   SIP-{sip_num:04d}: {title}")
            else:
                print(f"   Title: {title}")
            print(f"   {issue['message']}")
            if 'field' in issue:
                print(f"   Field: {issue['field']}")
                if 'registry_value' in issue:
                    print(f"   Registry: {issue['registry_value']}")
                    print(f"   File: {issue['file_value']}")
            if 'value' in issue:
                print(f"   Value: {issue['value']}")
        print()
    
    # Informational
    if issues['informational']:
        print("=" * 60)
        print(f"INFORMATIONAL ({len(issues['informational'])}):")
        print("=" * 60)
        for i, issue in enumerate(issues['informational'], 1):
            print(f"\n{i}. {issue['type'].upper().replace('_', ' ')}")
            print(f"   {issue['message']}")
            if 'missing' in issue:
                print(f"   Missing numbers: {issue['missing']}")
            if 'file' in issue:
                print(f"   File: {issue['file']}")
        print()
    
    # Recommendations
    print("=" * 60)
    print("RECOMMENDATIONS:")
    print("=" * 60)
    
    recommendations = []
    
    missing_file_count = sum(1 for i in issues['critical'] if i['type'] == 'missing_file')
    if missing_file_count > 0:
        recommendations.append(f"Remove {missing_file_count} registry entry/entries for non-existent files")
    
    invalid_timestamp_count = sum(1 for i in issues['data_quality'] if i['type'] == 'invalid_timestamp')
    if invalid_timestamp_count > 0:
        recommendations.append(f"Fix {invalid_timestamp_count} invalid timestamp format(s)")
    
    mismatch_count = sum(1 for i in issues['critical'] if i['type'] == 'status_folder_mismatch')
    if mismatch_count > 0:
        recommendations.append(f"Fix {mismatch_count} status/folder mismatch(es)")
    
    duplicate_variant_count = sum(1 for i in issues['data_quality'] if i['type'] == 'duplicate_number_missing_variant')
    if duplicate_variant_count > 0:
        recommendations.append(f"Add variant fields for {duplicate_variant_count} duplicate number group(s)")
    
    orphaned_count = sum(1 for i in issues['critical'] if i['type'] == 'orphaned_numbered_file')
    if orphaned_count > 0:
        recommendations.append(f"Add {orphaned_count} orphaned numbered file(s) to registry")
    
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")
    else:
        print("  No critical issues found requiring action.")
    
    print()


def main():
    """Main entry point."""
    print("🔍 Auditing SIP registry...")
    print()
    
    audit_results = audit_registry()
    print_audit_report(audit_results)
    
    # Exit code based on critical issues
    if audit_results['issues']['critical']:
        return 1
    return 0


if __name__ == "__main__":
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML not installed. Install with: pip install pyyaml")
        sys.exit(1)
    
    sys.exit(main())
