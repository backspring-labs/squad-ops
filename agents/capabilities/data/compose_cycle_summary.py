#!/usr/bin/env python3
"""
Cycle Summary Composer Capability Handler
Implements the data.compose_cycle_summary capability for composing compact cycle summaries.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

logger = logging.getLogger(__name__)


class CycleSummaryComposer:
    """
    Cycle Summary Composer - Implements data.compose_cycle_summary capability
    
    Composes compact JSON summaries with health flags and timeline.
    """
    
    def __init__(self, agent):
        """
        Initialize CycleSummaryComposer with agent instance.
        
        Args:
            agent: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent
        self.name = agent.name if hasattr(agent, 'name') else 'unknown'
    
    async def compose(self, cycle_id: str, snapshot_path: str | None = None, metrics_path: str | None = None) -> dict[str, Any]:
        """
        Compose compact cycle summary.
        
        Implements the data.compose_cycle_summary capability.
        
        Args:
            cycle_id: Execution cycle ID
            snapshot_path: Optional path to snapshot JSON (auto-detected if not provided)
            metrics_path: Optional path to metrics JSON (auto-detected if not provided)
            
        Returns:
            Dictionary containing:
            - summary_path: Path to summary JSON file
            - cycle_id: Execution cycle ID
            - health: Health flag (green/yellow/red)
            - agent_summary: Summary of agent metrics
        """
        logger.info(f"{self.name} composing cycle summary for cycle_id: {cycle_id}")
        
        try:
            # Load snapshot and metrics
            snapshot = await self._load_snapshot(cycle_id, snapshot_path)
            metrics = await self._load_metrics(cycle_id, metrics_path)
            
            if not snapshot:
                raise ValueError(f"Could not load snapshot for cycle_id: {cycle_id}")
            
            # Determine health flag
            health = self._determine_health(snapshot, metrics)
            
            # Build agent summary
            agent_summary = self._build_agent_summary(snapshot, metrics)
            
            # Build timeline (if available)
            timeline = self._build_timeline(snapshot, metrics)
            
            # Compose summary
            summary = {
                "cycle_id": cycle_id,
                "health": health,
                "agents": agent_summary,
                "timeline": timeline,
                "summary_generated_at": datetime.utcnow().isoformat() + "Z"
            }
            
            # Save summary using CycleDataStore (SIP-0047)
            from agents.cycle_data import CycleDataStore
            
            # Get project_id from execution cycle or default to warmboot_selftest
            project_id = "warmboot_selftest"  # Default for WarmBoot
            try:
                from agents.tasks.registry import get_tasks_adapter
                adapter = await get_tasks_adapter()
                flow = await adapter.get_flow(cycle_id)
                if flow and flow.project_id:
                    project_id = flow.project_id
            except Exception as e:
                logger.debug(f"Could not retrieve project_id from execution cycle, using default: {e}")
            
            # Initialize CycleDataStore
            cycle_data_root = self.agent.config.get_cycle_data_root()
            cycle_store = CycleDataStore(cycle_data_root, project_id, cycle_id)
            
            # Save summary to meta area
            summary_json = json.dumps(summary, indent=2)
            success = cycle_store.write_text_artifact(
                'meta',
                f'cycle-summary-{cycle_id}.json',
                summary_json
            )
            
            if success:
                summary_path = cycle_store.get_cycle_path() / 'meta' / f'cycle-summary-{cycle_id}.json'
                logger.info(f"{self.name} saved cycle summary: {summary_path}")
            else:
                raise Exception("Failed to write cycle summary to CycleDataStore")
            
            # Record memory
            if hasattr(self.agent, 'record_memory'):
                await self.agent.record_memory(
                    kind="cycle_summary_composed",
                    payload={
                        "cycle_id": cycle_id,
                        "summary_path": str(summary_path),
                        "health": health
                    },
                    ns="role",
                    importance=0.8
                )
            
            return {
                "summary_path": str(summary_path),
                "cycle_id": cycle_id,
                "health": health,
                "agent_summary": agent_summary
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to compose cycle summary: {e}", exc_info=True)
            raise
    
    async def _load_snapshot(self, cycle_id: str, snapshot_path: str | None = None) -> dict[str, Any] | None:
        """Load snapshot JSON file"""
        try:
            if snapshot_path:
                path = Path(snapshot_path)
            else:
                from agents.utils.path_resolver import PathResolver
                base_path = PathResolver.get_base_path()
                warmboot_runs_dir = base_path / "warm-boot" / "runs"
                run_dir = self._extract_run_directory(cycle_id, warmboot_runs_dir)
                if not run_dir:
                    return None
                path = run_dir / f"cycle-snapshot-{cycle_id}.json"
            
            if not path.exists():
                return None
            
            async with aiofiles.open(path) as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.warning(f"{self.name} error loading snapshot: {e}")
            return None
    
    async def _load_metrics(self, cycle_id: str, metrics_path: str | None = None) -> dict[str, Any] | None:
        """Load metrics JSON file"""
        try:
            if metrics_path:
                path = Path(metrics_path)
            else:
                from agents.utils.path_resolver import PathResolver
                base_path = PathResolver.get_base_path()
                warmboot_runs_dir = base_path / "warm-boot" / "runs"
                run_dir = self._extract_run_directory(cycle_id, warmboot_runs_dir)
                if not run_dir:
                    return None
                path = run_dir / f"cycle-metrics-{cycle_id}.json"
            
            if not path.exists():
                return None
            
            async with aiofiles.open(path) as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.warning(f"{self.name} error loading metrics: {e}")
            return None
    
    def _extract_run_directory(self, cycle_id: str, warmboot_runs_dir: Path) -> Path | None:
        """Extract run directory from ECID"""
        try:
            parts = cycle_id.split('-')
            if len(parts) >= 3:
                run_number = parts[-1]
                run_number = run_number.zfill(3) if run_number.isdigit() else run_number
                run_dir = warmboot_runs_dir / f"run-{run_number}"
                if run_dir.exists():
                    return run_dir
            return None
        except Exception:
            return None
    
    def _determine_health(self, snapshot: dict[str, Any], metrics: dict[str, Any] | None) -> str:
        """
        Determine health flag based on failure rate.
        
        - Green: All tasks succeeded or failure rate < 5%
        - Yellow: Failure rate 5-20% or some tasks incomplete
        - Red: Failure rate > 20% or critical failures
        """
        if metrics:
            summary = metrics.get("summary", {})
            failure_rate = summary.get("failure_rate", 0.0)
            total_tasks = summary.get("total_tasks", 0)
            
            if total_tasks == 0:
                return "yellow"  # No tasks yet
            
            if failure_rate < 0.05:  # < 5%
                return "green"
            elif failure_rate <= 0.20:  # 5-20%
                return "yellow"
            else:  # > 20%
                return "red"
        
        # Fallback: analyze from snapshot
        tasks = snapshot.get("tasks", [])
        if not tasks:
            return "yellow"
        
        failure_count = sum(1 for t in tasks if (t.get('status') or t.get('state') or '').lower() in ['failed', 'error'])
        failure_rate = failure_count / len(tasks) if tasks else 0.0
        
        if failure_rate < 0.05:
            return "green"
        elif failure_rate <= 0.20:
            return "yellow"
        else:
            return "red"
    
    def _build_agent_summary(self, snapshot: dict[str, Any], metrics: dict[str, Any] | None) -> dict[str, Any]:
        """Build compact agent summary"""
        agent_summary = {}
        
        if metrics and "agent_metrics" in metrics:
            # Use metrics if available
            for agent_name, agent_data in metrics["agent_metrics"].items():
                agent_summary[agent_name] = {
                    "task_count": agent_data.get("task_count", 0),
                    "failures": agent_data.get("failure_count", 0),
                    "success_rate": agent_data.get("success_rate", 0.0)
                }
        else:
            # Fallback: compute from snapshot
            agents = snapshot.get("agents", {})
            for agent_name, agent_data in agents.items():
                tasks = agent_data.get("tasks", [])
                failure_count = sum(1 for t in tasks if (t.get('status') or t.get('state') or '').lower() in ['failed', 'error'])
                success_count = sum(1 for t in tasks if (t.get('status') or t.get('state') or '').lower() in ['completed', 'success'])
                total_count = len(tasks)
                
                agent_summary[agent_name] = {
                    "task_count": total_count,
                    "failures": failure_count,
                    "success_rate": round(success_count / total_count, 3) if total_count > 0 else 0.0
                }
        
        return agent_summary
    
    def _build_timeline(self, snapshot: dict[str, Any], metrics: dict[str, Any] | None) -> list:
        """Build ordered timeline if available"""
        if metrics and "timeline" in metrics:
            return metrics["timeline"][:20]  # Limit to first 20 events
        
        # Fallback: build from snapshot tasks
        tasks = snapshot.get("tasks", [])
        timeline = []
        
        for task in tasks:
            event = {
                "task_id": task.get('task_id') or task.get('id'),
                "agent": task.get('agent') or task.get('agent_name'),
                "status": task.get('status') or task.get('state'),
                "timestamp": task.get('created_at') or task.get('started_at') or task.get('updated_at')
            }
            if event["timestamp"]:
                timeline.append(event)
        
        timeline.sort(key=lambda x: x.get("timestamp", ""))
        return timeline[:20]  # Limit to first 20 events



