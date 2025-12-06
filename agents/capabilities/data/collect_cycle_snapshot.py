#!/usr/bin/env python3
"""
Cycle Snapshot Collector Capability Handler
Implements the data.collect_cycle_snapshot capability for collecting and normalizing execution cycle snapshots.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

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
    
    async def collect(self, cycle_id: str, output_dir: str | None = None) -> dict[str, Any]:
        """
        Collect and normalize execution cycle snapshot.
        
        Implements the data.collect_cycle_snapshot capability.
        
        Args:
            cycle_id: Execution cycle ID (e.g., "CYCLE-WB-001")
            output_dir: Optional output directory (auto-detected if not provided)
            
        Returns:
            Dictionary containing:
            - snapshot_path: Path to saved snapshot JSON
            - cycle_id: Execution cycle ID
            - task_count: Number of tasks collected
            - agent_count: Number of unique agents
        """
        logger.info(f"{self.name} collecting cycle snapshot for cycle_id: {cycle_id}")
        
        try:
            # Get base path for warm-boot directory
            from agents.utils.path_resolver import PathResolver
            base_path = PathResolver.get_base_path()
            warmboot_runs_dir = base_path / "warm-boot" / "runs"
            
            # Determine run directory from cycle_id
            # cycle_id format: CYCLE-WB-XXX -> run-XXX
            run_dir = self._extract_run_directory(cycle_id, warmboot_runs_dir)
            if not run_dir:
                logger.warning(f"{self.name} could not determine run directory for cycle_id: {cycle_id}")
                run_dir = warmboot_runs_dir / f"run-{cycle_id.split('-')[-1]}" if '-' in cycle_id else warmboot_runs_dir / "run-unknown"
            
            # Use provided output_dir or default to run_dir
            if output_dir:
                output_path = Path(output_dir)
            else:
                output_path = run_dir
            
            # Create directory if it doesn't exist
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Fetch data from Task API
            execution_cycle = await self._fetch_execution_cycle(cycle_id)
            tasks = await self._fetch_tasks(cycle_id)
            
            # Scan for existing artifacts in run directory
            artifacts = await self._scan_artifacts(run_dir)
            
            # Aggregate tasks by agent
            agents = self._aggregate_by_agent(tasks)
            
            # Build normalized snapshot
            snapshot = {
                "cycle_id": cycle_id,
                "execution_cycle": execution_cycle,
                "tasks": tasks,
                "agents": agents,
                "artifacts": artifacts,
                "collected_at": datetime.utcnow().isoformat() + "Z"
            }
            
            # Save snapshot using CycleDataStore (SIP-0047)
            from agents.cycle_data import CycleDataStore
            
            # Get project_id from execution cycle or default to warmboot_selftest
            project_id = "warmboot_selftest"  # Default for WarmBoot
            if execution_cycle and execution_cycle.get("project_id"):
                project_id = execution_cycle["project_id"]
            
            # Initialize CycleDataStore
            cycle_data_root = self.agent.config.get_cycle_data_root()
            cycle_store = CycleDataStore(cycle_data_root, project_id, cycle_id)
            
            # Save snapshot to meta area
            snapshot_json = json.dumps(snapshot, indent=2)
            success = cycle_store.write_text_artifact(
                'meta',
                f'cycle-snapshot-{cycle_id}.json',
                snapshot_json
            )
            
            if success:
                snapshot_path = cycle_store.get_cycle_path() / 'meta' / f'cycle-snapshot-{cycle_id}.json'
                logger.info(f"{self.name} saved cycle snapshot: {snapshot_path}")
            else:
                raise Exception("Failed to write cycle snapshot to CycleDataStore")
            
            # Record memory
            if hasattr(self.agent, 'record_memory'):
                await self.agent.record_memory(
                    kind="cycle_snapshot_collected",
                    payload={"cycle_id": cycle_id, "snapshot_path": str(snapshot_path), "task_count": len(tasks)},
                    ns="role",
                    importance=0.7
                )
            
            return {
                "snapshot_path": str(snapshot_path),
                "cycle_id": cycle_id,
                "task_count": len(tasks),
                "agent_count": len(agents)
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to collect cycle snapshot: {e}", exc_info=True)
            raise
    
    def _extract_run_directory(self, cycle_id: str, warmboot_runs_dir: Path) -> Path | None:
        """Extract run directory from ECID (e.g., ECID-WB-001 -> run-001)"""
        try:
            # ECID format: ECID-WB-XXX
            parts = cycle_id.split('-')
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
                            if cycle_id in content:
                                return run_dir
                        except Exception:
                            continue
            
            return None
        except Exception as e:
            logger.warning(f"{self.name} failed to extract run directory: {e}")
            return None
    
    async def _fetch_execution_cycle(self, cycle_id: str) -> dict[str, Any]:
        """Fetch execution cycle info from Task API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.task_api_url}/api/v1/execution-cycles/{cycle_id}") as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.warning(f"{self.name} failed to fetch execution cycle {cycle_id}: {await resp.text()}")
                        return {}
        except Exception as e:
            logger.warning(f"{self.name} error fetching execution cycle: {e}")
            return {}
    
    async def _fetch_tasks(self, cycle_id: str) -> list:
        """Fetch tasks for cycle_id from Task API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.task_api_url}/api/v1/tasks/ec/{cycle_id}") as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.warning(f"{self.name} failed to fetch tasks for cycle_id {cycle_id}: {await resp.text()}")
                        return []
        except Exception as e:
            logger.warning(f"{self.name} error fetching tasks: {e}")
            return []
    
    async def _scan_artifacts(self, run_dir: Path) -> dict[str, Any]:
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
    
    def _aggregate_by_agent(self, tasks: list) -> dict[str, Any]:
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



