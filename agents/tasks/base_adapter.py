"""
TaskAdapterBase - Abstract base class for task management adapters
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from agents.tasks.models import (
    Task,
    TaskCreate,
    TaskState,
    TaskFilters,
    Artifact,
    FlowRun,
    FlowCreate,
    FlowUpdate,
    FlowState,
    TaskSummary,
)


class TaskAdapterBase(ABC):
    """
    Abstract base class for task management adapters.
    All task operations go through this interface.
    
    **DTO Purity Principle:**
    Adapters return canonical DTOs only; they do not format API payloads.
    Any legacy response-shape compatibility transformations must occur
    only in the FastAPI layer. This ensures:
    - No drift between adapters and API
    - Prefect adapter won't need to mimic historical quirks
    - Adapter layer remains clean and future-proof
    """

    @abstractmethod
    async def create_task(self, task: TaskCreate) -> Task:
        """
        Create a new task.
        
        Args:
            task: Task creation DTO
            
        Returns:
            Created Task object
        """
        pass

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get a task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task object or None if not found
        """
        pass

    @abstractmethod
    async def list_tasks(self, filters: TaskFilters) -> List[Task]:
        """
        List tasks matching filters.
        
        Args:
            filters: Query filters (ecid, agent, status, pid, limit)
            
        Returns:
            List of Task objects
        """
        pass

    @abstractmethod
    async def update_task_state(
        self, task_id: str, state: TaskState, meta: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        Update task state.
        
        Args:
            task_id: Task identifier
            state: New task state
            meta: Optional metadata (e.g., end_time, error_log)
            
        Returns:
            Updated Task object
        """
        pass

    @abstractmethod
    async def add_artifact(self, task_id: str, artifact: Artifact) -> None:
        """
        Add an artifact to a task.
        
        Args:
            task_id: Task identifier
            artifact: Artifact to add
        """
        pass

    @abstractmethod
    async def add_dependency(self, task_id: str, depends_on_id: str) -> None:
        """
        Add a dependency relationship between tasks.
        
        Args:
            task_id: Task that depends on another
            depends_on_id: Task that is depended upon
        """
        pass

    @abstractmethod
    async def list_tasks_for_pid(self, pid: str) -> List[Task]:
        """
        List all tasks for a process ID.
        
        Args:
            pid: Process identifier
            
        Returns:
            List of Task objects
        """
        pass

    @abstractmethod
    async def list_tasks_for_ecid(self, ecid: str) -> List[Task]:
        """
        List all tasks for an execution cycle ID.
        
        Args:
            ecid: Execution cycle identifier
            
        Returns:
            List of Task objects
        """
        pass

    @abstractmethod
    async def create_flow(
        self, ecid: str, pid: str, meta: Optional[Dict[str, Any]] = None
    ) -> FlowRun:
        """
        Create a new execution cycle (flow).
        
        Args:
            ecid: Execution cycle identifier
            pid: Process identifier
            meta: Optional metadata (run_type, title, description, initiated_by)
            
        Returns:
            Created FlowRun object
        """
        pass

    @abstractmethod
    async def update_flow(
        self, flow_id: str, state: FlowState, meta: Optional[Dict[str, Any]] = None
    ) -> FlowRun:
        """
        Update an execution cycle (flow).
        
        Args:
            flow_id: Execution cycle identifier (ecid)
            state: New flow state
            meta: Optional metadata (notes, status)
            
        Returns:
            Updated FlowRun object
        """
        pass

    @abstractmethod
    async def get_flow(self, ecid: str) -> Optional[FlowRun]:
        """
        Get an execution cycle by ECID.
        
        Args:
            ecid: Execution cycle identifier
            
        Returns:
            FlowRun object or None if not found
        """
        pass

    @abstractmethod
    async def list_flows(
        self, run_type: Optional[str] = None
    ) -> List[FlowRun]:
        """
        List execution cycles, optionally filtered by run_type.
        
        Args:
            run_type: Optional filter by run type
            
        Returns:
            List of FlowRun objects
        """
        pass

    @abstractmethod
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task status from task_status table.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task status dict or None if not found
        """
        pass

    @abstractmethod
    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: float = 0.0,
        eta: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update task status in task_status table.
        
        Args:
            task_id: Task identifier
            status: Status string
            progress: Progress percentage (0.0-100.0)
            eta: Optional ETA string
            agent_name: Optional agent name
            
        Returns:
            Updated task status dict
        """
        pass

    @abstractmethod
    async def get_task_summary(self, ecid: str) -> TaskSummary:
        """
        Get task summary statistics for an execution cycle.
        
        Args:
            ecid: Execution cycle identifier
            
        Returns:
            TaskSummary DTO with counts and averages
        """
        pass

    async def initialize(self) -> None:
        """
        Optional backend initialization (pool setup, client boot).
        
        Adapters can override this method to perform initialization tasks
        such as setting up connection pools, initializing clients, etc.
        This is called during FastAPI startup.
        
        Default implementation is a no-op.
        """
        return None

    async def shutdown(self) -> None:
        """
        Optional backend teardown (pool close, client cleanup).
        
        Adapters can override this method to perform cleanup tasks
        such as closing connection pools, cleaning up clients, etc.
        This is called during FastAPI shutdown.
        
        Default implementation is a no-op.
        """
        return None

