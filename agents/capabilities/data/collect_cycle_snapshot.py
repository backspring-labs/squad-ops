#!/usr/bin/env python3
"""
Cycle Snapshot Collector Capability Handler
Implements the data.collect_cycle_snapshot capability for collecting and normalizing execution cycle snapshots.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles
import aiohttp

logger = logging.getLogger(__name__)


class CycleSnapshotCollector:
    """
    Cycle Snapshot Collector - Implements data.collect_cycle_snapshot capability
    
    Collects and normalizes execution cycle data from:
    - Task API (tasks and execution cycle info)
    - WarmBoot run artifacts (wrapup files, logs)
    """
    
    def __init__(self, agent):
        """
        Initialize CycleSnapshotCollector with agent instance.
        
        Args:
            agent: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent
        self.name = agent.name if hasattr(agent, 'name') else 'unknown'
        self.task_api_url = agent.task_api_url if hasattr(agent, 'task_api_url') else 'http://localhost:8001'
    
    async def collect(self, ecid: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Collect and normalize execution cycle snapshot.
        
        Implements the data.collect_cycle_snapshot capability.
        
        Args:
            ecid: Execution cycle ID (e.g., "ECID-WB-001")
            output_dir: Optional output directory (auto-detected if not provided)
            
        Returns:
            Dictionary containing:
            - snapshot_path: Path to saved snapshot JSON
            - ecid: Execution cycle ID
            - task_count: Number of tasks collected
            - agent_count: Number of unique agents
        """
        logger.info(f"{self.name} collecting cycle snapshot for ECID: {ecid}")
        
        try:
            # Get base path for warm-boot directory
            from agents.utils.path_resolver import PathResolver
            base_path = PathResolver.get_base_path()
            warmboot_runs_dir = base_path / "warm-boot" / "runs"
            
            # Determine run directory from ECID
            # ECID format: ECID-WB-XXX -> run-XXX
            run_dir = self._extract_run_directory(ecid, warmboot_runs_dir)
            if not run_dir:
                logger.warning(f"{self.name} could not determine run directory for ECID: {ecid}")
                run_dir = warmboot_runs_dir / f"run-{ecid.split('-')[-1]}" if '-' in ecid else warmboot_runs_dir / "run-unknown"
            
            # Use provided output_dir or default to run_dir
            if output_dir:
                output_path = Path(output_dir)
            else:
                output_path = run_dir
            
            # Create directory if it doesn't exist
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Fetch data from Task API
            execution_cycle = await self._fetch_execution_cycle(ecid)
            tasks = await self._fetch_tasks(ecid)
            
            # Scan for existing artifacts in run directory
            artifacts = await self._scan_artifacts(run_dir)
            
            # Aggregate tasks by agent
            agents = self._aggregate_by_agent(tasks)
            
            # Build normalized snapshot
            snapshot = {
                "ecid": ecid,
                "execution_cycle": execution_cycle,
                "tasks": tasks,
                "agents": agents,
                "artifacts": artifacts,
                "collected_at": datetime.utcnow().isoformat() + "Z"
            }
            
            # Save snapshot
            snapshot_filename = f"cycle-snapshot-{ecid}.json"
            snapshot_path = output_path / snapshot_filename
            
            async with aiofiles.open(snapshot_path, 'w') as f:
                await f.write(json.dumps(snapshot, indent=2))
            
            logger.info(f"{self.name} saved cycle snapshot: {snapshot_path}")
            
            # Record memory
            if hasattr(self.agent, 'record_memory'):
                await self.agent.record_memory(
                    kind="cycle_snapshot_collected",
                    payload={"ecid": ecid, "snapshot_path": str(snapshot_path), "task_count": len(tasks)},
                    ns="role",
                    importance=0.7
                )
            
            return {
                "snapshot_path": str(snapshot_path),
                "ecid": ecid,
                "task_count": len(tasks),
                "agent_count": len(agents)
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to collect cycle snapshot: {e}", exc_info=True)
            raise
    
    def _extract_run_directory(self, ecid: str, warmboot_runs_dir: Path) -> Optional[Path]:
        """Extract run directory from ECID (e.g., ECID-WB-001 -> run-001)"""
        try:
            # ECID format: ECID-WB-XXX
            parts = ecid.split('-')
            if len(parts) >= 3:
                run_number = parts[-1]
                # Handle both "001" and "1" formats
                run_number = run_number.zfill(3) if run_number.isdigit() else run_number
                run_dir = warmboot_runs_dir / f"run-{run_number}"
                if run_dir.exists():
                    return run_dir
            
            # Fallback: scan for matching ECID in existing runs
            for run_dir in warmboot_runs_dir.iterdir():
                if run_dir.is_dir() and run_dir.name.startswith('run-'):
                    # Check wrapup files for ECID
                    for wrapup_file in run_dir.glob('*wrapup*.md'):
                        try:
                            content = wrapup_file.read_text()
                            if ecid in content:
                                return run_dir
                        except Exception:
                            continue
            
            return None
        except Exception as e:
            logger.warning(f"{self.name} failed to extract run directory: {e}")
            return None
    
    async def _fetch_execution_cycle(self, ecid: str) -> Dict[str, Any]:
        """Fetch execution cycle info from Task API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.task_api_url}/api/v1/execution-cycles/{ecid}") as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.warning(f"{self.name} failed to fetch execution cycle {ecid}: {await resp.text()}")
                        return {}
        except Exception as e:
            logger.warning(f"{self.name} error fetching execution cycle: {e}")
            return {}
    
    async def _fetch_tasks(self, ecid: str) -> list:
        """Fetch tasks for ECID from Task API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.task_api_url}/api/v1/tasks/ec/{ecid}") as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.warning(f"{self.name} failed to fetch tasks for ECID {ecid}: {await resp.text()}")
                        return []
        except Exception as e:
            logger.warning(f"{self.name} error fetching tasks: {e}")
            return []
    
    async def _scan_artifacts(self, run_dir: Path) -> Dict[str, Any]:
        """Scan run directory for existing artifacts"""
        artifacts = {
            "wrapup_files": [],
            "log_files": [],
            "summary_files": [],
            "other_files": []
        }
        
        if not run_dir.exists():
            return artifacts
        
        try:
            for file_path in run_dir.iterdir():
                if not file_path.is_file():
                    continue
                
                filename = file_path.name
                if 'wrapup' in filename.lower():
                    artifacts["wrapup_files"].append({
                        "filename": filename,
                        "path": str(file_path),
                        "size": file_path.stat().st_size
                    })
                elif 'log' in filename.lower() or filename.endswith('.json'):
                    artifacts["log_files"].append({
                        "filename": filename,
                        "path": str(file_path),
                        "size": file_path.stat().st_size
                    })
                elif 'summary' in filename.lower():
                    artifacts["summary_files"].append({
                        "filename": filename,
                        "path": str(file_path),
                        "size": file_path.stat().st_size
                    })
                else:
                    artifacts["other_files"].append({
                        "filename": filename,
                        "path": str(file_path),
                        "size": file_path.stat().st_size
                    })
        except Exception as e:
            logger.warning(f"{self.name} error scanning artifacts: {e}")
        
        return artifacts
    
    def _aggregate_by_agent(self, tasks: list) -> Dict[str, Any]:
        """Aggregate tasks by agent name"""
        agents = {}
        
        for task in tasks:
            agent_name = task.get('agent') or task.get('agent_name') or 'unknown'
            
            if agent_name not in agents:
                agents[agent_name] = {
                    "task_count": 0,
                    "tasks": [],
                    "statuses": {}
                }
            
            agents[agent_name]["task_count"] += 1
            agents[agent_name]["tasks"].append(task)
            
            status = task.get('status') or task.get('state') or 'unknown'
            agents[agent_name]["statuses"][status] = agents[agent_name]["statuses"].get(status, 0) + 1
        
        return agents



