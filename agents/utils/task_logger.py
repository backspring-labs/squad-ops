"""
TaskLogger - Unified task logging helper for all agents (SIP-0048)

Provides a consistent task logging mechanism used by all agents.
Writes to agent_task_log table via Runtime API only (no direct DB access).
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class TaskLogger:
    """
    Unified task logging helper for all agents (SIP-0048).
    
    Provides context manager support and consistent logging interface.
    Writes to agent_task_log table via Runtime API only (maintains separation of concerns).
    Uses agent_id for agent identification (not role normalization).
    Uses cycle_id (not ecid) for cycle references (SIP-0048).
    """
    
    def __init__(self, runtime_api_url: str, agent_id: str, cycle_id: str):
        """
        Initialize TaskLogger.
        
        Args:
            runtime_api_url: Base URL for Runtime API (SIP-0048: renamed from task-api)
            agent_id: Agent identifier (use agent_id, not role normalization)
            cycle_id: Execution cycle identifier (SIP-0048: renamed from ecid)
        """
        self.runtime_api_url = runtime_api_url
        self.agent_id = agent_id
        self.cycle_id = cycle_id
        self.current_task_id: str | None = None
        self._start_time: datetime | None = None
    
    @asynccontextmanager
    async def log_task(self, task_id: str, task_name: str, description: str | None = None,
                      priority: str = "MEDIUM", pid: str | None = None,
                      dependencies: list[str] | None = None):
        """
        Context manager for task logging.
        
        Usage:
            async with task_logger.log_task("task-123", "build_app", "Build the application"):
                # Do work
                await task_logger.record_metric("files_created", 5)
                await task_logger.attach_artifact("build_log", {"path": "/tmp/build.log"})
        
        Args:
            task_id: Task identifier
            task_name: Task name/type identifier (SIP-0048)
            description: Task description
            priority: Task priority (default: MEDIUM)
            pid: Optional process identifier
            dependencies: Optional list of task dependencies
        """
        await self.log_start(task_id, task_name, description, priority, pid, dependencies)
        try:
            yield self
            await self.log_end(task_id, "completed")
        except Exception as e:
            await self.log_end(task_id, "failed", error_log=str(e))
            raise
    
    async def log_start(self, task_id: str, task_name: str, description: str | None = None,
                       priority: str = "MEDIUM", pid: str | None = None,
                       dependencies: list[str] | None = None) -> bool:
        """
        Log task start via Runtime API.
        
        Args:
            task_id: Task identifier
            task_name: Task name/type identifier (SIP-0048)
            description: Task description
            priority: Task priority (default: MEDIUM)
            pid: Optional process identifier
            dependencies: Optional list of task dependencies
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.current_task_id = task_id
            self._start_time = datetime.utcnow()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.runtime_api_url}/api/v1/tasks/start",
                    json={
                        "task_id": task_id,
                        "cycle_id": self.cycle_id,  # SIP-0048: renamed from ecid
                        "agent": self.agent_id,  # For backward compatibility
                        "agent_id": self.agent_id,  # SIP-0048: use agent_id
                        "task_name": task_name,  # SIP-0048: new field
                        "status": "started",
                        "priority": priority,
                        "description": description,
                        "pid": pid,
                        "dependencies": dependencies or [],
                    }
                ) as resp:
                    if resp.status == 200:
                        logger.debug(f"TaskLogger: Started task {task_id} for cycle {self.cycle_id}")
                        return True
                    else:
                        logger.warning(f"TaskLogger: Failed to start task {task_id}: {await resp.text()}")
                        return False
        except Exception as e:
            logger.warning(f"TaskLogger: Error starting task {task_id}: {e}")
            return False
    
    async def log_end(self, task_id: str, status: str = "completed",
                     error_log: str | None = None) -> bool:
        """
        Log task end via Runtime API.
        
        Args:
            task_id: Task identifier
            status: Task status (completed, failed, etc.)
            error_log: Optional error log if task failed
            
        Returns:
            True if successful, False otherwise
        """
        try:
            end_time = datetime.utcnow()
            
            async with aiohttp.ClientSession() as session:
                update_data = {
                    "status": status,
                    "end_time": end_time.isoformat(),
                }
                if error_log:
                    update_data["error_log"] = error_log
                
                async with session.put(
                    f"{self.runtime_api_url}/api/v1/tasks/{task_id}",
                    json=update_data
                ) as resp:
                    if resp.status == 200:
                        logger.debug(f"TaskLogger: Ended task {task_id} with status {status}")
                        self.current_task_id = None
                        self._start_time = None
                        return True
                    else:
                        logger.warning(f"TaskLogger: Failed to end task {task_id}: {await resp.text()}")
                        return False
        except Exception as e:
            logger.warning(f"TaskLogger: Error ending task {task_id}: {e}")
            return False
    
    async def attach_artifact(self, artifact_type: str, artifact_data: dict[str, Any],
                            task_id: str | None = None) -> bool:
        """
        Attach an artifact to a task via Runtime API.
        
        Args:
            artifact_type: Type of artifact (e.g., "code", "test_report", "build_plan")
            artifact_data: Artifact data dictionary
            task_id: Optional task identifier (uses current task if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        task_id = task_id or self.current_task_id
        if not task_id:
            logger.warning("TaskLogger: No task_id provided and no current task")
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    f"{self.runtime_api_url}/api/v1/tasks/{task_id}",
                    json={
                        "artifacts": [{
                            "type": artifact_type,
                            **artifact_data
                        }]
                    }
                ) as resp:
                    if resp.status == 200:
                        logger.debug(f"TaskLogger: Attached artifact {artifact_type} to task {task_id}")
                        return True
                    else:
                        logger.warning(f"TaskLogger: Failed to attach artifact: {await resp.text()}")
                        return False
        except Exception as e:
            logger.warning(f"TaskLogger: Error attaching artifact: {e}")
            return False
    
    async def record_metric(self, metric_name: str, metric_value: Any,
                           task_id: str | None = None) -> bool:
        """
        Record a metric for a task via Runtime API.
        
        Args:
            metric_name: Name of the metric
            metric_value: Value of the metric (will be JSON-serialized)
            task_id: Optional task identifier (uses current task if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        task_id = task_id or self.current_task_id
        if not task_id:
            logger.warning("TaskLogger: No task_id provided and no current task")
            return False
        
        try:
            # Get current task to merge metrics
            async with aiohttp.ClientSession() as session:
                # First, get current task to retrieve existing metrics
                async with session.get(
                    f"{self.runtime_api_url}/api/v1/tasks/{task_id}"
                ) as get_resp:
                    current_metrics = {}
                    if get_resp.status == 200:
                        task_data = await get_resp.json()
                        if task_data.get("metrics"):
                            current_metrics = task_data["metrics"]
                    
                    # Merge new metric
                    current_metrics[metric_name] = metric_value
                    
                    # Update task with merged metrics
                    async with session.put(
                        f"{self.runtime_api_url}/api/v1/tasks/{task_id}",
                        json={"metrics": current_metrics}
                    ) as put_resp:
                        if put_resp.status == 200:
                            logger.debug(f"TaskLogger: Recorded metric {metric_name}={metric_value} for task {task_id}")
                            return True
                        else:
                            logger.warning(f"TaskLogger: Failed to record metric: {await put_resp.text()}")
                            return False
        except Exception as e:
            logger.warning(f"TaskLogger: Error recording metric: {e}")
            return False
    
    async def add_dependency(self, depends_on_task_id: str,
                           task_id: str | None = None) -> bool:
        """
        Add a dependency relationship between tasks via Runtime API.
        
        Args:
            depends_on_task_id: Task ID that this task depends on
            task_id: Optional task identifier (uses current task if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        task_id = task_id or self.current_task_id
        if not task_id:
            logger.warning("TaskLogger: No task_id provided and no current task")
            return False
        
        try:
            # Get current task to merge dependencies
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.runtime_api_url}/api/v1/tasks/{task_id}"
                ) as get_resp:
                    current_dependencies = []
                    if get_resp.status == 200:
                        task_data = await get_resp.json()
                        if task_data.get("dependencies"):
                            current_dependencies = task_data["dependencies"]
                    
                    # Add new dependency if not already present
                    if depends_on_task_id not in current_dependencies:
                        current_dependencies.append(depends_on_task_id)
                        
                        # Update task with merged dependencies
                        async with session.put(
                            f"{self.runtime_api_url}/api/v1/tasks/{task_id}",
                            json={"dependencies": current_dependencies}
                        ) as put_resp:
                            if put_resp.status == 200:
                                logger.debug(f"TaskLogger: Added dependency {depends_on_task_id} to task {task_id}")
                                return True
                            else:
                                logger.warning(f"TaskLogger: Failed to add dependency: {await put_resp.text()}")
                                return False
                    else:
                        logger.debug(f"TaskLogger: Dependency {depends_on_task_id} already exists for task {task_id}")
                        return True
        except Exception as e:
            logger.warning(f"TaskLogger: Error adding dependency: {e}")
            return False


