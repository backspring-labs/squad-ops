#!/usr/bin/env python3
"""
SIP Reorganization Script
Reorganizes SIPs into lifecycle folders with clean naming and variant suffixes.
"""

import json
import re
import yaml
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict

REPO_ROOT = Path(__file__).parent.parent.parent.parent
SIPS_DIR = REPO_ROOT / "sips"
ANALYSIS_FILE = REPO_ROOT / "sips" / "ENHANCED_ANALYSIS_REPORT.json"
ACCEPTED_DIR = SIPS_DIR / "accepted"
IMPLEMENTED_DIR = SIPS_DIR / "implemented"
DEPRECATED_DIR = SIPS_DIR / "deprecated"
PROPOSALS_DIR = SIPS_DIR / "proposals"


def clean_title(title: str, sip_number: Optional[int]) -> str:
    """Clean title by removing SIP-XXX patterns and normalizing."""
    if not title:
        return "Untitled"
    
    # Remove leading dashes
    title = title.lstrip('-')
    
    # Remove "SIP-XXX" patterns (case insensitive)
    title = re.sub(r'SIP-[\dX]+[-:\s]*', '', title, flags=re.IGNORECASE)
    
    # Remove "SIP-00X" patterns
    title = re.sub(r'SIP-00X[-:\s]*', '', title, flags=re.IGNORECASE)
    
    # Remove redundant dashes
    title = re.sub(r'-+', '-', title)
    title = title.strip('-')
    
    # Normalize to filename-safe format
    title = re.sub(r'[^\w\s-]', '', title)
    title = re.sub(r'\s+', '-', title)
    title = title.strip('-')
    
    # Limit length
    if len(title) > 80:
        title = title[:80].rstrip('-')
    
    return title or "Untitled"


def extract_clean_title_from_content(content: str, filename: str) -> str:
    """Extract clean title from SIP content."""
    # Try to find title in content
    patterns = [
        r'##\s+Title[:\s]+(.+)',
        r'#+\s+SIP[-\d]*[:\s]+(.+)',
        r'Title[:\s]+(.+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if match:
            title = match.group(1).strip()
            # Remove markdown formatting
            title = re.sub(r'[*_`]', '', title)
            return clean_title(title, None)
    
    # Fallback: use filename
    base = Path(filename).stem
    if base.startswith('SIP-'):
        return clean_title(base[4:], None)
    return clean_title(base, None)


def generate_filename(sip_number: Optional[int], title: str, variant: int = 1) -> str:
    """Generate clean filename with variant suffix if needed."""
    if sip_number is not None:
        if variant > 1:
            return f"SIP-{sip_number:04d}-v{variant}-{title}.md"
        else:
            return f"SIP-{sip_number:04d}-{title}.md"
    else:
        return f"SIP-PROPOSAL-{title}.md"


def update_frontmatter(content: str, new_path: str, new_status: str, clean_title: str) -> str:
    """Update YAML frontmatter with new path and status."""
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    
    if frontmatter_match:
        try:
            metadata = yaml.safe_load(frontmatter_match.group(1))
        except Exception:
            metadata = {}
    else:
        metadata = {}
    
    # Update metadata
    metadata['status'] = new_status
    metadata['updated_at'] = datetime.now().isoformat() + 'Z'
    if 'title' not in metadata or not metadata['title']:
        metadata['title'] = clean_title
    
    # Generate YAML frontmatter
    yaml_lines = []
    yaml_lines.append("---")
    for key, value in metadata.items():
        if value is None:
            yaml_lines.append(f"{key}: null")
        elif isinstance(value, str):
            yaml_lines.append(f'{key}: "{value}"')
        else:
            yaml_lines.append(f"{key}: {value}")
    yaml_lines.append("---")
    yaml_lines.append("")
    
    yaml_block = "\n".join(yaml_lines)
    
    if frontmatter_match:
        return re.sub(r'^---\s*\n.*?\n---\s*\n', yaml_block + "\n", content, count=1, flags=re.DOTALL)
    else:
        return yaml_block + "\n" + content


def reorganize_sips() -> Dict[str, Any]:
    """Reorganize all SIPs into lifecycle folders."""
    # Load analysis
    if not ANALYSIS_FILE.exists():
        print(f"Error: Analysis file not found: {ANALYSIS_FILE}")
        return {}
    
    with open(ANALYSIS_FILE, 'r', encoding='utf-8') as f:
        analysis = json.load(f)
    
    # Create folders
    ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)
    IMPLEMENTED_DIR.mkdir(parents=True, exist_ok=True)
    DEPRECATED_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Group by SIP number to handle duplicates
    by_number = defaultdict(list)
    for sip in analysis.get('sips', []):
        num = sip.get('sip_number')
        if num:
            by_number[num].append(sip)
        else:
            by_number[None].append(sip)
    
    results = []
    
    print("Reorganizing SIPs...\n")
    
    for sip in analysis.get('sips', []):
        current_path = REPO_ROOT / sip['path']
        if not current_path.exists():
            print(f"  ⚠️  File not found: {current_path}")
            continue
        
        # Read content
        try:
            with open(current_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  ❌ Error reading {current_path}: {e}")
            continue
        
        sip_number = sip.get('sip_number')
        status = sip.get('status', 'accepted')
        current_title = sip.get('title', '')
        
        # Extract clean title
        clean_title_text = clean_title(current_title, sip_number)
        if not clean_title_text or clean_title_text == "Untitled":
            clean_title_text = extract_clean_title_from_content(content, sip['filename'])
        
        # Determine variant number
        variants = by_number.get(sip_number, [])
        variant_num = 1
        if len(variants) > 1:
            # Find this SIP's position in the list
            for i, v in enumerate(variants, 1):
                if v['filename'] == sip['filename']:
                    variant_num = i
                    break
        
        # Determine target directory
        if status == 'implemented':
            target_dir = IMPLEMENTED_DIR
        elif status == 'deprecated':
            target_dir = DEPRECATED_DIR
        elif sip_number is None:
            target_dir = PROPOSALS_DIR
        else:
            target_dir = ACCEPTED_DIR
        
        # Generate new filename
        new_filename = generate_filename(sip_number, clean_title_text, variant_num)
        new_path = target_dir / new_filename
        
        # Update frontmatter
        new_content = update_frontmatter(content, str(new_path.relative_to(REPO_ROOT)), status, clean_title_text)
        
        # Write to new location
        try:
            with open(new_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # Remove old file
            if current_path != new_path:
                current_path.unlink()
            
            print(f"  ✅ {sip['filename']}")
            print(f"     -> {new_path.relative_to(REPO_ROOT)}")
            
            results.append({
                'original_path': str(current_path.relative_to(REPO_ROOT)),
                'new_path': str(new_path.relative_to(REPO_ROOT)),
                'sip_number': sip_number,
                'status': status,
                'variant': variant_num,
                'clean_title': clean_title_text,
            })
        except Exception as e:
            print(f"  ❌ Error writing {new_path}: {e}")
    
    return {'results': results, 'total': len(results)}


def main():
    """Main entry point."""
    print("=" * 60)
    print("SIP Reorganization Script")
    print("=" * 60)
    print()
    
    results = reorganize_sips()
    
    if not results:
        print("Reorganization failed.")
        return 1
    
    print(f"\n✅ Reorganization complete!")
    print(f"   Total SIPs reorganized: {results['total']}")
    
    # Summary by folder
    by_folder = defaultdict(int)
    by_status = defaultdict(int)
    for result in results['results']:
        folder = Path(result['new_path']).parent.name
        by_folder[folder] += 1
        by_status[result['status']] += 1
    
    print("\nBy folder:")
    for folder, count in sorted(by_folder.items()):
        print(f"  {folder}: {count}")
    
    print("\nBy status:")
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")
    
    # Save reorganization log
    log_file = SIPS_DIR / "REORGANIZATION_LOG.json"
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nReorganization log saved to: {log_file}")
    
    return 0


if __name__ == "__main__":
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML not installed. Install with: pip install pyyaml")
        exit(1)
    
    exit(main())

