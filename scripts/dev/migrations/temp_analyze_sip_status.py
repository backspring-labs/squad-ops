#!/usr/bin/env python3
"""
SIP Status Analysis Script
Analyzes SIPs to determine their implementation status using hybrid approach.
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Set, Optional, Union
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent.parent.parent
INVENTORY_FILE = REPO_ROOT / "sips" / "MIGRATION_INVENTORY.json"
CONTEXT_HANDOFF = REPO_ROOT / "docs" / "SQUADOPS_CONTEXT_HANDOFF.md"
OUTPUT_FILE = REPO_ROOT / "sips" / "SIP_ANALYSIS_REPORT.json"


# Known implemented SIPs from context handoff
KNOWN_IMPLEMENTED = {
    24: "Execution Cycle Protocol",
    25: "Phased Task Management and Orchestration API Strategy",
    27: "WarmBoot Telemetry & Orchestration Protocol",
    31: "A2A Envelope Standard",
    41: "Naming & Correlation Protocol",
    42: "LanceDB Memory Protocol",
}

# Known superseded/deprecated patterns
SUPERSEDED_PATTERNS = [
    (r'SIP-040', r'SIP-040-REV2'),  # SIP-040 superseded by REV2
]


def load_inventory() -> Dict[str, Any]:
    """Load the SIP inventory."""
    if not INVENTORY_FILE.exists():
        print(f"Error: Inventory file not found: {INVENTORY_FILE}")
        print("Run inventory_sips.py first.")
        return {}
    
    with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_context_handoff(sip_number: Optional[int]) -> Optional[str]:
    """Check if SIP is listed as implemented in context handoff."""
    if sip_number and sip_number in KNOWN_IMPLEMENTED:
        return "implemented"
    return None


def check_codebase_evidence(sip_file: Path, sip_number: Optional[int]) -> Dict[str, Any]:
    """Search codebase for evidence of SIP implementation."""
    evidence = {
        'found_schemas': [],
        'found_classes': [],
        'found_apis': [],
        'found_configs': [],
    }
    
    if not sip_file.exists():
        return evidence
    
    # Read SIP content to extract key terms
    try:
        with open(sip_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return evidence
    
    # Extract potential database table names
    schema_matches = re.findall(r'CREATE TABLE\s+(\w+)', content, re.IGNORECASE)
    evidence['found_schemas'] = list(set(schema_matches))
    
    # Extract class names
    class_matches = re.findall(r'class\s+(\w+)', content, re.IGNORECASE)
    evidence['found_classes'] = list(set(class_matches))
    
    # Extract API endpoints
    api_matches = re.findall(r'/(?:api|v\d+)/[^\s\)]+', content, re.IGNORECASE)
    evidence['found_apis'] = list(set(api_matches))
    
    # Search codebase for these terms
    codebase_evidence = {
        'schema_matches': [],
        'class_matches': [],
        'api_matches': [],
    }
    
    # Search in key directories
    search_dirs = [
        REPO_ROOT / "agents",
        REPO_ROOT / "infra",
        REPO_ROOT / "config",
    ]
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        
        for py_file in search_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    
                    # Check for schema matches
                    for schema in evidence['found_schemas']:
                        if schema.lower() in file_content.lower():
                            codebase_evidence['schema_matches'].append(str(py_file.relative_to(REPO_ROOT)))
                    
                    # Check for class matches
                    for cls in evidence['found_classes']:
                        if cls in file_content:
                            codebase_evidence['class_matches'].append(str(py_file.relative_to(REPO_ROOT)))
            except Exception:
                continue
    
    return {
        **evidence,
        **codebase_evidence,
    }


def determine_status(sip: Dict[str, Any], evidence: Dict[str, Any]) -> str:
    """Determine SIP status based on evidence."""
    metadata = sip.get('metadata', {})
    sip_number = metadata.get('sip_number')
    status_text = metadata.get('status', '').lower() if metadata.get('status') else ''
    filename = sip.get('filename', '')
    
    # Check if explicitly deprecated
    if any(word in status_text for word in ['deprecated', 'superseded', 'replaced']):
        return 'deprecated'
    
    # Check if superseded by newer version
    for pattern, replacement in SUPERSEDED_PATTERNS:
        if re.search(pattern, filename):
            # Check if newer version exists
            if re.search(replacement, str(REPO_ROOT / "docs" / "SIPs"), re.IGNORECASE):
                return 'deprecated'
    
    # Check if implemented
    context_status = check_context_handoff(sip_number)
    if context_status == 'implemented':
        return 'implemented'
    
    # Check codebase evidence
    if evidence.get('schema_matches') or evidence.get('class_matches') or evidence.get('api_matches'):
        # Strong evidence of implementation
        return 'implemented'
    
    # Check if has number and approved status
    if sip_number and any(word in status_text for word in ['approved', 'accepted', 'implemented']):
        return 'accepted'
    
    # Check if has number but unclear status
    if sip_number:
        return 'accepted'  # Numbered but not clearly implemented
    
    # Default to proposed
    return 'proposed'


def analyze_sips() -> Dict[str, Any]:
    """Analyze all SIPs and determine their status."""
    inventory = load_inventory()
    
    if not inventory or 'sips' not in inventory:
        print("No inventory data found.")
        return {}
    
    analysis = {
        'analyzed_at': datetime.now().isoformat(),
        'total_sips': len(inventory['sips']),
        'sips': [],
    }
    
    print("Analyzing SIPs...")
    
    for sip in inventory['sips']:
        original_path = sip['original_path']
        sip_file = REPO_ROOT / original_path
        metadata = sip.get('metadata', {})
        sip_number = metadata.get('sip_number')
        
        print(f"  Analyzing {sip['filename']} (SIP-{sip_number or '?'})...")
        
        # Check codebase evidence
        evidence = check_codebase_evidence(sip_file, sip_number)
        
        # Determine status
        status = determine_status(sip, evidence)
        
        # Determine target location
        if status in ['implemented', 'accepted', 'deprecated']:
            target_location = 'sips'
        else:
            target_location = 'proposals'
        
        analysis_entry = {
            'filename': sip['filename'],
            'original_path': original_path,
            'sip_number': sip_number,
            'metadata': metadata,
            'status': status,
            'target_location': target_location,
            'evidence': evidence,
            'reasoning': f"Status: {status}, Target: {target_location}",
        }
        
        analysis['sips'].append(analysis_entry)
        print(f"    -> {status} -> {target_location}")
    
    return analysis


def generate_summary(analysis: Dict[str, Any]) -> None:
    """Generate summary statistics."""
    if not analysis or 'sips' not in analysis:
        return
    
    status_counts = {}
    location_counts = {}
    
    for sip in analysis['sips']:
        status = sip.get('status', 'unknown')
        location = sip.get('target_location', 'unknown')
        
        status_counts[status] = status_counts.get(status, 0) + 1
        location_counts[location] = location_counts.get(location, 0) + 1
    
    print("\n" + "=" * 60)
    print("Analysis Summary")
    print("=" * 60)
    print(f"Total SIPs analyzed: {len(analysis['sips'])}")
    print("\nStatus distribution:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    print("\nTarget location distribution:")
    for location, count in sorted(location_counts.items()):
        print(f"  {location}: {count}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("SIP Status Analysis Script")
    print("=" * 60)
    
    # Analyze SIPs
    analysis = analyze_sips()
    
    if not analysis:
        print("Analysis failed. Exiting.")
        return 1
    
    # Write analysis report
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    
    print(f"\nAnalysis report saved to: {OUTPUT_FILE}")
    
    # Generate summary
    generate_summary(analysis)
    
    return 0


if __name__ == "__main__":
    exit(main())

