#!/usr/bin/env python3
"""
Cycle Metrics Profiler Capability Handler
Implements the data.profile_cycle_metrics capability for computing metrics from cycle snapshots.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles

logger = logging.getLogger(__name__)


class CycleMetricsProfiler:
    """
    Cycle Metrics Profiler - Implements data.profile_cycle_metrics capability
    
    Computes metrics from cycle snapshots and generates JSON + Markdown reports.
    """
    
    def __init__(self, agent):
        """
        Initialize CycleMetricsProfiler with agent instance.
        
        Args:
            agent: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent
        self.name = agent.name if hasattr(agent, 'name') else 'unknown'
    
    async def profile(self, ecid: str, snapshot_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Compute metrics from cycle snapshot.
        
        Implements the data.profile_cycle_metrics capability.
        
        Args:
            ecid: Execution cycle ID
            snapshot_path: Optional path to snapshot JSON (auto-detected if not provided)
            
        Returns:
            Dictionary containing:
            - metrics_json_path: Path to metrics JSON file
            - metrics_md_path: Path to metrics Markdown file
            - ecid: Execution cycle ID
            - metrics_summary: Summary of key metrics
        """
        logger.info(f"{self.name} profiling cycle metrics for ECID: {ecid}")
        
        try:
            # Load snapshot
            snapshot = await self._load_snapshot(ecid, snapshot_path)
            if not snapshot:
                raise ValueError(f"Could not load snapshot for ECID: {ecid}")
            
            # Compute metrics
            metrics = self._compute_metrics(snapshot)
            
            # Determine output directory
            from agents.utils.path_resolver import PathResolver
            base_path = PathResolver.get_base_path()
            warmboot_runs_dir = base_path / "warm-boot" / "runs"
            
            # Extract run directory from snapshot path or ECID
            if snapshot_path:
                output_dir = Path(snapshot_path).parent
            else:
                run_dir = self._extract_run_directory(ecid, warmboot_runs_dir)
                output_dir = run_dir if run_dir else warmboot_runs_dir / f"run-{ecid.split('-')[-1]}"
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate JSON metrics file
            metrics_json_path = output_dir / f"cycle-metrics-{ecid}.json"
            async with aiofiles.open(metrics_json_path, 'w') as f:
                await f.write(json.dumps(metrics, indent=2))
            
            logger.info(f"{self.name} saved metrics JSON: {metrics_json_path}")
            
            # Generate Markdown summary
            metrics_md_path = output_dir / f"cycle-metrics-{ecid}.md"
            markdown_content = self._generate_markdown(ecid, metrics, snapshot)
            async with aiofiles.open(metrics_md_path, 'w') as f:
                await f.write(markdown_content)
            
            logger.info(f"{self.name} saved metrics Markdown: {metrics_md_path}")
            
            # Record memory
            if hasattr(self.agent, 'record_memory'):
                await self.agent.record_memory(
                    kind="cycle_metrics_profiled",
                    payload={
                        "ecid": ecid,
                        "metrics_json_path": str(metrics_json_path),
                        "total_tasks": metrics.get("summary", {}).get("total_tasks", 0)
                    },
                    ns="role",
                    importance=0.7
                )
            
            return {
                "metrics_json_path": str(metrics_json_path),
                "metrics_md_path": str(metrics_md_path),
                "ecid": ecid,
                "metrics_summary": metrics.get("summary", {})
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to profile cycle metrics: {e}", exc_info=True)
            raise
    
    async def _load_snapshot(self, ecid: str, snapshot_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load snapshot JSON file"""
        try:
            if snapshot_path:
                path = Path(snapshot_path)
            else:
                # Auto-detect from ECID
                from agents.utils.path_resolver import PathResolver
                base_path = PathResolver.get_base_path()
                warmboot_runs_dir = base_path / "warm-boot" / "runs"
                run_dir = self._extract_run_directory(ecid, warmboot_runs_dir)
                if not run_dir:
                    return None
                path = run_dir / f"cycle-snapshot-{ecid}.json"
            
            if not path.exists():
                logger.warning(f"{self.name} snapshot file not found: {path}")
                return None
            
            async with aiofiles.open(path) as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"{self.name} error loading snapshot: {e}")
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
    
    def _compute_metrics(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Compute metrics from snapshot"""
        tasks = snapshot.get("tasks", [])
        agents = snapshot.get("agents", {})
        execution_cycle = snapshot.get("execution_cycle", {})
        
        # Task status distribution
        status_distribution = {}
        for task in tasks:
            status = task.get('status') or task.get('state') or 'unknown'
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        # Per-agent metrics
        agent_metrics = {}
        for agent_name, agent_data in agents.items():
            agent_tasks = agent_data.get("tasks", [])
            success_count = sum(1 for t in agent_tasks if (t.get('status') or t.get('state') or '').lower() in ['completed', 'success'])
            failure_count = sum(1 for t in agent_tasks if (t.get('status') or t.get('state') or '').lower() in ['failed', 'error'])
            total_count = len(agent_tasks)
            
            agent_metrics[agent_name] = {
                "task_count": total_count,
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": round(success_count / total_count, 3) if total_count > 0 else 0.0,
                "status_breakdown": agent_data.get("statuses", {})
            }
        
        # Duration stats (if timestamps available)
        duration_stats = self._compute_duration_stats(tasks, execution_cycle)
        
        # Timeline (ordered events)
        timeline = self._build_timeline(tasks)
        
        # Summary
        total_tasks = len(tasks)
        total_success = sum(1 for t in tasks if (t.get('status') or t.get('state') or '').lower() in ['completed', 'success'])
        total_failure = sum(1 for t in tasks if (t.get('status') or t.get('state') or '').lower() in ['failed', 'error'])
        
        metrics = {
            "ecid": snapshot.get("ecid"),
            "computed_at": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "total_tasks": total_tasks,
                "total_agents": len(agents),
                "total_success": total_success,
                "total_failure": total_failure,
                "success_rate": round(total_success / total_tasks, 3) if total_tasks > 0 else 0.0,
                "failure_rate": round(total_failure / total_tasks, 3) if total_tasks > 0 else 0.0
            },
            "status_distribution": status_distribution,
            "agent_metrics": agent_metrics,
            "duration_stats": duration_stats,
            "timeline": timeline
        }
        
        return metrics
    
    def _compute_duration_stats(self, tasks: List[Dict[str, Any]], execution_cycle: Dict[str, Any]) -> Dict[str, Any]:
        """Compute duration statistics from tasks"""
        durations = []
        
        for task in tasks:
            # Try to extract duration from task
            if 'duration' in task:
                durations.append(task['duration'])
            elif 'duration_seconds' in task:
                durations.append(task['duration_seconds'])
            elif 'started_at' in task and 'completed_at' in task:
                try:
                    start = datetime.fromisoformat(task['started_at'].replace('Z', '+00:00'))
                    end = datetime.fromisoformat(task['completed_at'].replace('Z', '+00:00'))
                    durations.append((end - start).total_seconds())
                except Exception:
                    pass
        
        if not durations:
            return {"available": False, "message": "No duration data available"}
        
        return {
            "available": True,
            "count": len(durations),
            "min_seconds": round(min(durations), 2),
            "max_seconds": round(max(durations), 2),
            "avg_seconds": round(sum(durations) / len(durations), 2),
            "total_seconds": round(sum(durations), 2)
        }
    
    def _build_timeline(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build ordered timeline of events"""
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
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x.get("timestamp", ""))
        
        return timeline[:50]  # Limit to first 50 events
    
    def _generate_markdown(self, ecid: str, metrics: Dict[str, Any], snapshot: Dict[str, Any]) -> str:
        """Generate Markdown summary of metrics"""
        summary = metrics.get("summary", {})
        agent_metrics = metrics.get("agent_metrics", {})
        status_dist = metrics.get("status_distribution", {})
        duration_stats = metrics.get("duration_stats", {})
        
        md = f"""# Cycle Metrics Report

**ECID:** {ecid}  
**Generated:** {metrics.get('computed_at', 'Unknown')}

## Summary

- **Total Tasks:** {summary.get('total_tasks', 0)}
- **Total Agents:** {summary.get('total_agents', 0)}
- **Success Rate:** {summary.get('success_rate', 0.0):.1%}
- **Failure Rate:** {summary.get('failure_rate', 0.0):.1%}

## Status Distribution

"""
        for status, count in status_dist.items():
            md += f"- **{status}:** {count}\n"
        
        md += "\n## Per-Agent Metrics\n\n"
        for agent_name, agent_data in agent_metrics.items():
            md += f"### {agent_name}\n\n"
            md += f"- **Tasks:** {agent_data.get('task_count', 0)}\n"
            md += f"- **Success:** {agent_data.get('success_count', 0)}\n"
            md += f"- **Failures:** {agent_data.get('failure_count', 0)}\n"
            md += f"- **Success Rate:** {agent_data.get('success_rate', 0.0):.1%}\n\n"
        
        if duration_stats.get("available"):
            md += "## Duration Statistics\n\n"
            md += f"- **Min:** {duration_stats.get('min_seconds', 0):.2f}s\n"
            md += f"- **Max:** {duration_stats.get('max_seconds', 0):.2f}s\n"
            md += f"- **Average:** {duration_stats.get('avg_seconds', 0):.2f}s\n"
            md += f"- **Total:** {duration_stats.get('total_seconds', 0):.2f}s\n\n"
        
        return md



