"""
ACI-based capability executor using queue transport.

Implements the CapabilityExecutor port by wrapping the QueuePort
to dispatch TaskEnvelope messages and await TaskResult responses.
"""

import asyncio
import json
import logging
import uuid
from typing import Any

from squadops.ports.comms.queue import QueuePort
from squadops.ports.capabilities.executor import CapabilityExecutor

# Import ACI models from v0_legacy (path added via pytest pythonpath)
# [DEFERRED] Migrate TaskEnvelope/TaskResult to canonical location in future SIP
from agents.tasks.models import TaskEnvelope, TaskResult

logger = logging.getLogger(__name__)


class ExecutorError(Exception):
    """Raised when task execution fails."""

    def __init__(self, message: str, task_id: str | None = None):
        self.task_id = task_id
        super().__init__(message)


class ACICapabilityExecutor(CapabilityExecutor):
    """
    ACI queue-based capability executor.

    Dispatches TaskEnvelope messages via QueuePort and awaits
    TaskResult responses. Uses a response queue pattern for
    synchronous execution semantics.
    """

    def __init__(
        self,
        queue: QueuePort,
        response_queue_prefix: str = "responses",
        default_timeout_seconds: int = 300,
    ):
        """
        Initialize the ACI executor.

        Args:
            queue: QueuePort implementation for message transport
            response_queue_prefix: Prefix for response queues
            default_timeout_seconds: Default timeout for task execution
        """
        self._queue = queue
        self._response_queue_prefix = response_queue_prefix
        self._default_timeout = default_timeout_seconds
        self._executor_id = f"aci-executor-{uuid.uuid4().hex[:8]}"

    @property
    def executor_id(self) -> str:
        """Unique identifier for this executor."""
        return self._executor_id

    def _get_agent_queue(self, agent_id: str) -> str:
        """Get the queue name for an agent."""
        # Standard queue naming convention: agent.{agent_id}.tasks
        return f"agent.{agent_id}.tasks"

    def _get_response_queue(self, task_id: str) -> str:
        """Get the response queue name for a task."""
        return f"{self._response_queue_prefix}.{task_id}"

    async def execute(
        self,
        envelope: TaskEnvelope,
        timeout_seconds: int | None = None,
    ) -> TaskResult:
        """
        Execute a task and await its result.

        The executor:
        1. Publishes the TaskEnvelope to the agent's task queue
        2. Awaits a TaskResult on the response queue
        3. Returns the result or raises on timeout/error

        Args:
            envelope: ACI TaskEnvelope with task details
            timeout_seconds: Maximum time to wait for result

        Returns:
            TaskResult with execution outcome

        Raises:
            TimeoutError: If execution exceeds timeout
            ExecutorError: If execution fails
        """
        timeout = timeout_seconds or self._default_timeout
        task_id = envelope.task_id
        agent_id = envelope.agent_id

        # Get queue names
        agent_queue = self._get_agent_queue(agent_id)
        response_queue = self._get_response_queue(task_id)

        # Add response queue to envelope metadata
        envelope_dict = envelope.model_dump()
        envelope_dict["metadata"]["response_queue"] = response_queue

        logger.info(
            f"Executing task {task_id} for agent {agent_id} "
            f"(timeout: {timeout}s)"
        )

        try:
            # Publish task to agent queue
            await self._queue.publish(
                queue_name=agent_queue,
                payload=json.dumps(envelope_dict),
            )

            # Wait for response with timeout
            result = await asyncio.wait_for(
                self._wait_for_result(response_queue, task_id),
                timeout=timeout,
            )

            logger.info(f"Task {task_id} completed with status: {result.status}")
            return result

        except asyncio.TimeoutError:
            logger.error(f"Task {task_id} timed out after {timeout}s")
            raise TimeoutError(f"Task {task_id} timed out after {timeout} seconds")

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            raise ExecutorError(f"Task execution failed: {e}", task_id=task_id)

    async def _wait_for_result(
        self, response_queue: str, task_id: str
    ) -> TaskResult:
        """
        Wait for a TaskResult on the response queue.

        Polls the response queue until a message is received.
        """
        poll_interval = 0.5  # seconds

        while True:
            messages = await self._queue.consume(
                queue_name=response_queue,
                max_messages=1,
            )

            if messages:
                message = messages[0]
                try:
                    data = json.loads(message.payload)
                    result = TaskResult(**data)

                    # Verify task_id matches
                    if result.task_id != task_id:
                        logger.warning(
                            f"Received result for wrong task: "
                            f"expected {task_id}, got {result.task_id}"
                        )
                        await self._queue.retry(message, delay_seconds=0)
                        continue

                    # Acknowledge and return
                    await self._queue.ack(message)
                    return result

                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Invalid result message: {e}")
                    await self._queue.ack(message)  # Discard invalid messages
                    continue

            # No message yet, wait and poll again
            await asyncio.sleep(poll_interval)

    async def health(self) -> dict[str, Any]:
        """Check the health status of the executor."""
        queue_health = await self._queue.health()
        return {
            "status": "healthy" if queue_health.get("status") == "healthy" else "unhealthy",
            "executor_id": self._executor_id,
            "queue_status": queue_health,
        }

    def can_execute(self, capability_id: str, agent_role: str) -> bool:
        """
        Check if this executor can execute a given capability.

        The ACI executor can execute any capability for any role,
        as long as the queue is available.
        """
        # ACI executor is general-purpose
        return True
