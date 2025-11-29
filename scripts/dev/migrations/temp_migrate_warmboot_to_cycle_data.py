#!/usr/bin/env python3
"""
Migration Script: Move WarmBoot runs to cycle_data/ (SIP-0047)

This script migrates existing WarmBoot runs from warm-boot/runs/ to
the new cycle_data/warmboot_selftest/<ECID>/ structure.

Usage:
    python scripts/dev/migrations/temp_migrate_warmboot_to_cycle_data.py [--dry-run]
"""

import argparse
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_ecid_from_run(run_dir: Path) -> Optional[str]:
    """
    Extract ECID from a WarmBoot run directory.
    
    Tries multiple strategies:
    1. Look for ECID in wrapup files
    2. Look for ECID in summary files
    3. Extract from run number if format is known
    """
    # Strategy 1: Check wrapup files
    for wrapup_file in run_dir.glob('*wrapup*.md'):
        try:
            content = wrapup_file.read_text(encoding='utf-8')
            # Look for ECID pattern: ECID-WB-XXX
            match = re.search(r'ECID-WB-(\d+)', content)
            if match:
                return f"ECID-WB-{match.group(1)}"
        except Exception as e:
            logger.debug(f"Error reading wrapup file {wrapup_file}: {e}")
    
    # Strategy 2: Check summary files
    for summary_file in run_dir.glob('*summary*.md'):
        try:
            content = summary_file.read_text(encoding='utf-8')
            match = re.search(r'ECID-WB-(\d+)', content)
            if match:
                return f"ECID-WB-{match.group(1)}"
        except Exception as e:
            logger.debug(f"Error reading summary file {summary_file}: {e}")
    
    # Strategy 3: Extract from run directory name (run-XXX -> ECID-WB-XXX)
    run_match = re.match(r'run-(\d+)', run_dir.name)
    if run_match:
        run_number = run_match.group(1)
        return f"ECID-WB-{run_number.zfill(3)}"
    
    return None


def categorize_artifact(file_path: Path) -> tuple[str, str]:
    """
    Categorize an artifact file into area and relative path.
    
    Returns:
        (area, relative_path) tuple
    """
    filename = file_path.name.lower()
    
    # Meta files
    if 'summary' in filename or 'snapshot' in filename or 'metrics' in filename:
        if filename.endswith('.json'):
            return ('meta', file_path.name)
        elif filename.endswith('.md'):
            return ('meta', file_path.name)
    
    # Artifacts
    if 'wrapup' in filename or 'wrap-up' in filename:
        return ('artifacts', file_path.name)
    
    if filename.endswith('.md') and ('milestone' in filename or 'run-' in filename):
        return ('artifacts', file_path.name)
    
    # Telemetry
    if filename.endswith('.jsonl') or 'log' in filename:
        return ('telemetry', file_path.name)
    
    # Default to artifacts
    return ('artifacts', file_path.name)


def migrate_run(run_dir: Path, cycle_data_root: Path, project_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Migrate a single WarmBoot run to cycle_data structure.
    
    Returns:
        Dictionary with migration results
    """
    ecid = extract_ecid_from_run(run_dir)
    if not ecid:
        logger.warning(f"Could not extract ECID from {run_dir}, skipping")
        return {"status": "skipped", "reason": "no_ecid", "run_dir": str(run_dir)}
    
    logger.info(f"Migrating run {run_dir.name} -> ECID: {ecid}")
    
    # Create target directory structure
    target_dir = cycle_data_root / project_id / ecid
    target_meta = target_dir / 'meta'
    target_artifacts = target_dir / 'artifacts'
    target_telemetry = target_dir / 'telemetry'
    
    if not dry_run:
        target_meta.mkdir(parents=True, exist_ok=True)
        target_artifacts.mkdir(parents=True, exist_ok=True)
        target_telemetry.mkdir(parents=True, exist_ok=True)
    
    # Migrate files
    migrated_files = []
    skipped_files = []
    
    for file_path in run_dir.rglob('*'):
        if file_path.is_dir():
            continue
        
        if file_path.name.startswith('.'):
            continue
        
        area, relative_path = categorize_artifact(file_path)
        target_path = target_dir / area / relative_path
        
        # Handle conflicts (if file already exists)
        if target_path.exists() and not dry_run:
            logger.warning(f"Target file already exists: {target_path}, skipping")
            skipped_files.append(str(file_path))
            continue
        
        if dry_run:
            logger.info(f"  Would copy: {file_path} -> {target_path}")
        else:
            try:
                # Ensure parent directory exists
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, target_path)
                logger.debug(f"  Copied: {file_path.name} -> {area}/{relative_path}")
            except Exception as e:
                logger.error(f"  Failed to copy {file_path}: {e}")
                skipped_files.append(str(file_path))
                continue
        
        migrated_files.append({
            "source": str(file_path),
            "target": str(target_path),
            "area": area
        })
    
    result = {
        "status": "success" if migrated_files else "partial",
        "ecid": ecid,
        "run_dir": str(run_dir),
        "target_dir": str(target_dir),
        "migrated_count": len(migrated_files),
        "skipped_count": len(skipped_files),
        "migrated_files": migrated_files,
        "skipped_files": skipped_files
    }
    
    if dry_run:
        result["status"] = "dry_run"
    
    return result


def main():
    parser = argparse.ArgumentParser(description='Migrate WarmBoot runs to cycle_data/')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated without actually copying files')
    parser.add_argument('--warmboot-runs-dir', type=str, help='Path to warm-boot/runs directory (default: auto-detect)')
    parser.add_argument('--cycle-data-root', type=str, help='Path to cycle_data root (default: auto-detect)')
    args = parser.parse_args()
    
    # Detect paths
    script_dir = Path(__file__).parent.parent.parent.parent
    warmboot_runs_dir = Path(args.warmboot_runs_dir) if args.warmboot_runs_dir else script_dir / 'warm-boot' / 'runs'
    cycle_data_root = Path(args.cycle_data_root) if args.cycle_data_root else script_dir / 'cycle_data'
    
    project_id = "warmboot_selftest"
    
    logger.info(f"WarmBoot runs directory: {warmboot_runs_dir}")
    logger.info(f"Cycle data root: {cycle_data_root}")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    
    if not warmboot_runs_dir.exists():
        logger.error(f"WarmBoot runs directory does not exist: {warmboot_runs_dir}")
        return 1
    
    # Find all run directories
    run_dirs = [d for d in warmboot_runs_dir.iterdir() if d.is_dir() and d.name.startswith('run-')]
    run_dirs.sort(key=lambda x: x.name)
    
    logger.info(f"Found {len(run_dirs)} run directories to migrate")
    
    if not run_dirs:
        logger.info("No run directories found, nothing to migrate")
        return 0
    
    # Migrate each run
    results = []
    for run_dir in run_dirs:
        result = migrate_run(run_dir, cycle_data_root, project_id, dry_run=args.dry_run)
        results.append(result)
    
    # Summary
    successful = sum(1 for r in results if r.get("status") == "success")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    total_files = sum(r.get("migrated_count", 0) for r in results)
    
    logger.info("=" * 60)
    logger.info("Migration Summary:")
    logger.info(f"  Total runs processed: {len(results)}")
    logger.info(f"  Successful: {successful}")
    logger.info(f"  Skipped: {skipped}")
    logger.info(f"  Total files migrated: {total_files}")
    logger.info("=" * 60)
    
    # Save migration log
    if not args.dry_run:
        log_file = cycle_data_root / 'migration_log.json'
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, 'w') as f:
            json.dump({
                "migration_date": str(Path(__file__).stat().st_mtime),
                "results": results,
                "summary": {
                    "total_runs": len(results),
                    "successful": successful,
                    "skipped": skipped,
                    "total_files": total_files
                }
            }, f, indent=2)
        logger.info(f"Migration log saved to: {log_file}")
    
    return 0 if successful > 0 else 1


if __name__ == '__main__':
    exit(main())

