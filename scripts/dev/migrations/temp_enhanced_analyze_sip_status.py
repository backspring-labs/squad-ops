#!/usr/bin/env python3
"""
Enhanced SIP Status Analysis Script
Properly analyzes SIPs using context handoff baseline and comprehensive codebase search.
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent.parent.parent
SIPS_DIR = REPO_ROOT / "sips"
CONTEXT_HANDOFF = REPO_ROOT / "docs" / "SQUADOPS_CONTEXT_HANDOFF.md"
OUTPUT_FILE = REPO_ROOT / "sips" / "ENHANCED_ANALYSIS_REPORT.json"

# Known implemented SIPs from context handoff
KNOWN_IMPLEMENTED = {
    24: "Execution Cycle Protocol",
    25: "Phased Task Management and Orchestration API Strategy",
    27: "WarmBoot Telemetry & Orchestration Protocol",
    31: "A2A Envelope Standard",
    41: "Naming & Correlation Protocol",
    42: "LanceDB Memory Protocol",
}

# Search directories
SEARCH_DIRS = [
    REPO_ROOT / "agents",
    REPO_ROOT / "infra",
    REPO_ROOT / "config",
    REPO_ROOT / "tests",
    REPO_ROOT / "scripts",
]


def extract_key_terms_from_sip(content: str) -> Dict[str, List[str]]:
    """Extract key terms from SIP content that indicate implementation."""
    terms = {
        'tables': [],
        'classes': [],
        'apis': [],
        'concepts': [],
    }
    
    # Extract database tables
    table_matches = re.findall(r'CREATE TABLE\s+(\w+)', content, re.IGNORECASE)
    terms['tables'] = list(set(table_matches))
    
    # Extract class names
    class_matches = re.findall(r'class\s+(\w+)', content, re.IGNORECASE)
    terms['classes'] = list(set(class_matches))
    
    # Extract API endpoints
    api_matches = re.findall(r'/(?:api|v\d+)/[^\s\)\n]+', content, re.IGNORECASE)
    terms['apis'] = list(set(api_matches))
    
    # Extract key concepts (capitalized terms that might be classes/concepts)
    concept_matches = re.findall(r'\b([A-Z][a-zA-Z]+(?:[A-Z][a-zA-Z]+)*)\b', content)
    # Filter out common words
    common_words = {'The', 'This', 'That', 'These', 'Those', 'SIP', 'SquadOps', 'Agent', 'Agents'}
    terms['concepts'] = [c for c in set(concept_matches) if c not in common_words and len(c) > 3]
    
    return terms


def search_codebase_for_terms(terms: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Search entire codebase for evidence of SIP implementation."""
    evidence = {
        'table_matches': [],
        'class_matches': [],
        'api_matches': [],
        'concept_matches': [],
    }
    
    for search_dir in SEARCH_DIRS:
        if not search_dir.exists():
            continue
        
        for py_file in search_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    file_content = f.read()
                    rel_path = str(py_file.relative_to(REPO_ROOT))
                    
                    # Check for table names
                    for table in terms['tables']:
                        if table.lower() in file_content.lower():
                            evidence['table_matches'].append(f"{rel_path}:{table}")
                    
                    # Check for class names
                    for cls in terms['classes']:
                        if f"class {cls}" in file_content or f"class {cls}(" in file_content:
                            evidence['class_matches'].append(f"{rel_path}:{cls}")
                    
                    # Check for API endpoints
                    for api in terms['apis']:
                        if api in file_content:
                            evidence['api_matches'].append(f"{rel_path}:{api}")
                    
                    # Check for concepts (less strict)
                    for concept in terms['concepts'][:10]:  # Limit to top 10
                        if concept in file_content:
                            evidence['concept_matches'].append(f"{rel_path}:{concept}")
            except Exception:
                continue
    
    # Also search SQL files
    for sql_file in (REPO_ROOT / "infra").rglob("*.sql"):
        try:
            with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
                file_content = f.read()
                rel_path = str(sql_file.relative_to(REPO_ROOT))
                
                for table in terms['tables']:
                    if table.lower() in file_content.lower():
                        evidence['table_matches'].append(f"{rel_path}:{table}")
        except Exception:
            continue
    
    return evidence


def check_context_handoff(sip_number: Optional[int]) -> bool:
    """Check if SIP is listed as implemented in context handoff."""
    return sip_number is not None and sip_number in KNOWN_IMPLEMENTED


def determine_status(sip_number: Optional[int], evidence: Dict[str, List[str]], 
                    status_text: str, filename: str) -> str:
    """Determine SIP status based on evidence."""
    status_lower = status_text.lower() if status_text else ''
    
    # Check if explicitly deprecated
    if any(word in status_lower for word in ['deprecated', 'superseded', 'replaced', 'future enhancement']):
        return 'deprecated'
    
    # Check if superseded by newer version (e.g., SIP-040 -> SIP-040-REV2)
    if 'REV2' in filename or 'REV3' in filename:
        # Check if original exists
        base_num = re.search(r'SIP-(\d+)', filename)
        if base_num:
            return 'deprecated'  # Revisions are typically newer versions
    
    # Check implementation evidence
    has_strong_evidence = (
        len(evidence['table_matches']) > 0 or
        len(evidence['class_matches']) > 0 or
        len(evidence['api_matches']) > 0
    )
    
    # Check context handoff
    in_context_handoff = check_context_handoff(sip_number)
    
    # Determine status
    if in_context_handoff or has_strong_evidence:
        return 'implemented'
    
    # If numbered but not implemented
    if sip_number is not None:
        return 'accepted'
    
    # Default to proposed
    return 'proposed'


def analyze_all_sips() -> Dict[str, Any]:
    """Analyze all SIPs in sips/ directory."""
    sip_files = list(SIPS_DIR.glob("SIP-*.md"))
    
    analysis = {
        'analyzed_at': datetime.now().isoformat(),
        'total_sips': len(sip_files),
        'sips': [],
    }
    
    print("Analyzing SIPs with enhanced codebase search...")
    print(f"Found {len(sip_files)} SIP files\n")
    
    for sip_file in sorted(sip_files):
        print(f"  Analyzing {sip_file.name}...")
        
        # Extract metadata from file
        try:
            with open(sip_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"    Error reading file: {e}")
            continue
        
        # Extract YAML frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if frontmatter_match:
            try:
                import yaml
                metadata = yaml.safe_load(frontmatter_match.group(1))
            except Exception:
                metadata = {}
        else:
            metadata = {}
        
        sip_number = metadata.get('sip_number')
        status_text = metadata.get('status', '')
        title = metadata.get('title', '')
        
        # Extract key terms from SIP
        key_terms = extract_key_terms_from_sip(content)
        
        # Search codebase for evidence
        evidence = search_codebase_for_terms(key_terms)
        
        # Determine status
        status = determine_status(sip_number, evidence, status_text, sip_file.name)
        
        # Count evidence strength
        evidence_count = (
            len(evidence['table_matches']) +
            len(evidence['class_matches']) +
            len(evidence['api_matches'])
        )
        
        analysis_entry = {
            'filename': sip_file.name,
            'path': str(sip_file.relative_to(REPO_ROOT)),
            'sip_number': sip_number,
            'title': title,
            'status': status,
            'in_context_handoff': check_context_handoff(sip_number),
            'evidence_count': evidence_count,
            'evidence': {
                'tables_found': len(evidence['table_matches']),
                'classes_found': len(evidence['class_matches']),
                'apis_found': len(evidence['api_matches']),
                'table_matches': evidence['table_matches'][:5],  # Limit for report
                'class_matches': evidence['class_matches'][:5],
                'api_matches': evidence['api_matches'][:5],
            },
            'key_terms': {
                'tables': key_terms['tables'],
                'classes': key_terms['classes'][:10],
                'apis': key_terms['apis'],
            },
        }
        
        analysis['sips'].append(analysis_entry)
        
        status_icon = "✅" if status == "implemented" else "📋" if status == "accepted" else "🗑️" if status == "deprecated" else "📝"
        print(f"    {status_icon} {status.upper()} (evidence: {evidence_count} matches)")
    
    return analysis


def generate_summary(analysis: Dict[str, Any]) -> None:
    """Generate summary statistics."""
    if not analysis or 'sips' not in analysis:
        return
    
    status_counts = {}
    by_number = {}
    
    for sip in analysis['sips']:
        status = sip.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
        
        num = sip.get('sip_number')
        if num:
            if num not in by_number:
                by_number[num] = []
            by_number[num].append(sip)
    
    print("\n" + "=" * 60)
    print("Enhanced Analysis Summary")
    print("=" * 60)
    print(f"Total SIPs analyzed: {len(analysis['sips'])}")
    print("\nStatus distribution:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    
    print("\nDuplicate SIP numbers:")
    for num, sips in sorted(by_number.items()):
        if len(sips) > 1:
            print(f"  SIP-{num:04d}: {len(sips)} variants")
            for sip in sips:
                print(f"    - {sip['filename']}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Enhanced SIP Status Analysis Script")
    print("=" * 60)
    print()
    
    # Analyze all SIPs
    analysis = analyze_all_sips()
    
    if not analysis:
        print("Analysis failed. Exiting.")
        return 1
    
    # Write analysis report
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    
    print(f"\nAnalysis report saved to: {OUTPUT_FILE}")
    
    # Generate summary
    generate_summary(analysis)
    
    return 0


if __name__ == "__main__":
    exit(main())

