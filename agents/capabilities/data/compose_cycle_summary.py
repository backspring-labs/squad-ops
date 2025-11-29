#!/usr/bin/env python3
"""
Cycle Summary Composer Capability Handler
Implements the data.compose_cycle_summary capability for composing compact cycle summaries.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    
    async def compose(self, ecid: str, snapshot_path: Optional[str] = None, metrics_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Compose compact cycle summary.
        
        Implements the data.compose_cycle_summary capability.
        
        Args:
            ecid: Execution cycle ID
            snapshot_path: Optional path to snapshot JSON (auto-detected if not provided)
            metrics_path: Optional path to metrics JSON (auto-detected if not provided)
            
        Returns:
            Dictionary containing:
            - summary_path: Path to summary JSON file
            - ecid: Execution cycle ID
            - health: Health flag (green/yellow/red)
            - agent_summary: Summary of agent metrics
        """
        logger.info(f"{self.name} composing cycle summary for ECID: {ecid}")
        
        try:
            # Load snapshot and metrics
            snapshot = await self._load_snapshot(ecid, snapshot_path)
            metrics = await self._load_metrics(ecid, metrics_path)
            
            if not snapshot:
                raise ValueError(f"Could not load snapshot for ECID: {ecid}")
            
            # Determine health flag
            health = self._determine_health(snapshot, metrics)
            
            # Build agent summary
            agent_summary = self._build_agent_summary(snapshot, metrics)
            
            # Build timeline (if available)
            timeline = self._build_timeline(snapshot, metrics)
            
            # Compose summary
            summary = {
                "ecid": ecid,
                "health": health,
                "agents": agent_summary,
                "timeline": timeline,
                "summary_generated_at": datetime.utcnow().isoformat() + "Z"
            }
            
            # Determine output directory
            from agents.utils.path_resolver import PathResolver
            base_path = PathResolver.get_base_path()
            warmboot_runs_dir = base_path / "warm-boot" / "runs"
            
            if snapshot_path:
                output_dir = Path(snapshot_path).parent
            else:
                run_dir = self._extract_run_directory(ecid, warmboot_runs_dir)
                output_dir = run_dir if run_dir else warmboot_runs_dir / f"run-{ecid.split('-')[-1]}"
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save summary
            summary_path = output_dir / f"cycle-summary-{ecid}.json"
            async with aiofiles.open(summary_path, 'w') as f:
                await f.write(json.dumps(summary, indent=2))
            
            logger.info(f"{self.name} saved cycle summary: {summary_path}")
            
            # Record memory
            if hasattr(self.agent, 'record_memory'):
                await self.agent.record_memory(
                    kind="cycle_summary_composed",
                    payload={
                        "ecid": ecid,
                        "summary_path": str(summary_path),
                        "health": health
                    },
                    ns="role",
                    importance=0.8
                )
            
            return {
                "summary_path": str(summary_path),
                "ecid": ecid,
                "health": health,
                "agent_summary": agent_summary
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to compose cycle summary: {e}", exc_info=True)
            raise
    
    async def _load_snapshot(self, ecid: str, snapshot_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load snapshot JSON file"""
        try:
            if snapshot_path:
                path = Path(snapshot_path)
            else:
                from agents.utils.path_resolver import PathResolver
                base_path = PathResolver.get_base_path()
                warmboot_runs_dir = base_path / "warm-boot" / "runs"
                run_dir = self._extract_run_directory(ecid, warmboot_runs_dir)
                if not run_dir:
                    return None
                path = run_dir / f"cycle-snapshot-{ecid}.json"
            
            if not path.exists():
                return None
            
            async with aiofiles.open(path) as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.warning(f"{self.name} error loading snapshot: {e}")
            return None
    
    async def _load_metrics(self, ecid: str, metrics_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load metrics JSON file"""
        try:
            if metrics_path:
                path = Path(metrics_path)
            else:
                from agents.utils.path_resolver import PathResolver
                base_path = PathResolver.get_base_path()
                warmboot_runs_dir = base_path / "warm-boot" / "runs"
                run_dir = self._extract_run_directory(ecid, warmboot_runs_dir)
                if not run_dir:
                    return None
                path = run_dir / f"cycle-metrics-{ecid}.json"
            
            if not path.exists():
                return None
            
            async with aiofiles.open(path) as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.warning(f"{self.name} error loading metrics: {e}")
            return None
    
    def _extract_run_directory(self, ecid: str, warmboot_runs_dir: Path) -> Optional[Path]:
        """Extract run directory from ECID"""
        try:
            parts = ecid.split('-')
            if len(parts) >= 3:
                run_number = parts[-1]
                run_number = run_number.zfill(3) if run_number.isdigit() else run_number
                run_dir = warmboot_runs_dir / f"run-{run_number}"
                if run_dir.exists():
                    return run_dir
            return None
        except Exception:
            return None
    
    def _determine_health(self, snapshot: Dict[str, Any], metrics: Optional[Dict[str, Any]]) -> str:
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
    
    def _build_agent_summary(self, snapshot: Dict[str, Any], metrics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
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
    
    def _build_timeline(self, snapshot: Dict[str, Any], metrics: Optional[Dict[str, Any]]) -> List:
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



