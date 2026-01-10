#!/usr/bin/env python3
"""
Telemetry Collector Capability Handler
Implements the telemetry.collect capability for collecting comprehensive telemetry data.
"""

import hashlib
import logging
import os
from datetime import UTC, datetime
from typing import Any

import psutil

logger = logging.getLogger(__name__)


class TelemetryCollector:
    """
    Telemetry Collector - Implements telemetry.collect capability

    Collects comprehensive telemetry data including:
    - Database metrics (task logs, execution cycles)
    - RabbitMQ metrics (queue stats, message counts)
    - Docker events (container lifecycle events)
    - Reasoning logs (LLM interactions, token usage)
    - System metrics (CPU, memory, GPU)
    - Artifact hashes (file integrity)
    - Event timeline (chronological event log)
    """

    def __init__(self, agent):
        """
        Initialize TelemetryCollector with agent instance.

        Args:
            agent: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent
        self.name = agent.name if hasattr(agent, "name") else "unknown"
        self.runtime_api_url = (
            agent.runtime_api_url if hasattr(agent, "runtime_api_url") else "http://localhost:8001"
        )  # SIP-0048: renamed from task_api_url
        self.communication_log = (
            agent.communication_log if hasattr(agent, "communication_log") else []
        )

    async def collect(self, cycle_id: str, task_id: str) -> dict[str, Any]:
        """
        Collect comprehensive telemetry data.

        Implements the telemetry.collect capability.

        Args:
            cycle_id: Execution cycle ID
            task_id: Task ID

        Returns:
            Dictionary containing all telemetry data
        """
        telemetry = {
            "database_metrics": {},
            "rabbitmq_metrics": {},
            "docker_events": {},
            "reasoning_logs": {},
            "system_metrics": {},
            "artifact_hashes": {},
            "event_timeline": [],
            "collection_timestamp": datetime.utcnow().isoformat(),
        }

        try:
            # Collect all telemetry components
            telemetry["database_metrics"] = await self.collect_database_metrics(cycle_id)
            telemetry["rabbitmq_metrics"] = await self.collect_rabbitmq_metrics(cycle_id)
            telemetry["system_metrics"] = await self.collect_system_metrics()
            telemetry["docker_events"] = await self.collect_docker_events(
                telemetry.get("database_metrics", {})
            )
            telemetry["artifact_hashes"] = await self.collect_artifact_hashes()
            telemetry["reasoning_logs"] = await self.collect_reasoning_logs(cycle_id)
            telemetry["event_timeline"] = self.build_event_timeline()

            # Add execution duration if available
            if "execution_duration" in telemetry["database_metrics"]:
                telemetry["execution_duration"] = telemetry["database_metrics"][
                    "execution_duration"
                ]

        except Exception as e:
            logger.error(f"{self.name} failed to collect telemetry: {e}")
            telemetry["collection_error"] = str(e)

        return telemetry

    async def collect_database_metrics(self, cycle_id: str) -> dict[str, Any]:
        """Collect database metrics via Task API"""
        metrics = {}

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                # Get task logs for this cycle_id
                async with session.get(
                    f"{self.runtime_api_url}/api/v1/tasks/ec/{cycle_id}"
                ) as resp:
                    if resp.status == 200:
                        task_logs = await resp.json()
                        metrics["task_count"] = len(task_logs)
                        metrics["tasks"] = task_logs
                    else:
                        logger.warning(
                            f"Failed to fetch tasks for cycle_id {cycle_id}: {await resp.text()}"
                        )
                        metrics["task_count"] = 0
                        metrics["tasks"] = []

                # Get execution cycle info
                async with session.get(
                    f"{self.runtime_api_url}/api/v1/execution-cycles/{cycle_id}"
                ) as resp:
                    if resp.status == 200:
                        cycle_info = await resp.json()
                        metrics["execution_cycle"] = cycle_info

                        # Calculate execution duration
                        try:
                            start_time_str = cycle_info.get("start_time") or cycle_info.get(
                                "created_at"
                            )
                            if start_time_str:
                                start_time = self._parse_datetime(start_time_str)
                                end_time = datetime.utcnow()
                                duration_seconds = (end_time - start_time).total_seconds()

                                metrics["execution_duration"] = {
                                    "start_time": start_time_str,
                                    "end_time": end_time.isoformat(),
                                    "duration_seconds": round(duration_seconds, 2),
                                    "duration_formatted": f"{int(duration_seconds // 60)}m {int(duration_seconds % 60)}s",
                                }
                                logger.info(
                                    f"{self.name} execution duration: {metrics['execution_duration']['duration_formatted']}"
                                )
                        except Exception as e:
                            logger.warning(
                                f"{self.name} failed to calculate execution duration: {e}"
                            )
                            metrics["execution_duration"] = {"error": str(e)}
                    else:
                        logger.warning(
                            f"Failed to fetch execution cycle {cycle_id}: {await resp.text()}"
                        )

            logger.info(
                f"{self.name} collected database metrics: {metrics.get('task_count', 0)} tasks"
            )

        except Exception as e:
            logger.warning(f"{self.name} failed to collect database metrics: {e}")
            metrics["error"] = str(e)

        return metrics

    async def collect_rabbitmq_metrics(self, cycle_id: str) -> dict[str, Any]:
        """Collect RabbitMQ metrics"""
        metrics = {}

        try:
            # Use rabbitmqctl to get queue stats
            result = await self.agent.execute_command(
                "rabbitmqctl list_queues name messages consumers"
            )
            queue_stats = {}
            total_messages_manual = len(self.communication_log)

            if result.get("success") and result.get("stdout"):
                for line in result.get("stdout", "").strip().split("\n")[1:]:  # Skip header
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        queue_name = parts[0].strip()
                        messages = int(parts[1].strip()) if parts[1].strip().isdigit() else 0
                        consumers = int(parts[2].strip()) if parts[2].strip().isdigit() else 0
                        queue_stats[queue_name] = {"messages": messages, "consumers": consumers}

            # Record RabbitMQ metrics via telemetry client
            try:
                self.agent.record_counter(
                    "rabbitmq_messages_total",
                    total_messages_manual,
                    {"source": "communication_log", "cycle_id": cycle_id},
                )
            except Exception as e:
                logger.debug(f"{self.name} failed to record RabbitMQ telemetry metric: {e}")

            # Query Prometheus for RabbitMQ metrics
            rabbitmq_from_telemetry = None
            total_messages_telemetry = 0
            try:
                import aiohttp
                from infra.config.loader import get_config

                app_config = get_config()
                prometheus_url = app_config.observability.prometheus.url
                query = f'sum(rabbitmq_messages_total{{cycle_id="{cycle_id}"}})'

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{prometheus_url}/api/v1/query",
                        params={"query": query},
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("status") == "success" and data.get("data", {}).get(
                                "result"
                            ):
                                result = (
                                    data["data"]["result"][0] if data["data"]["result"] else None
                                )
                                if result and "value" in result:
                                    total_messages_telemetry = int(float(result["value"][1]))
                                    rabbitmq_from_telemetry = {
                                        "source": "prometheus",
                                        "total_messages": total_messages_telemetry,
                                        "query": query,
                                    }
                                    logger.debug(
                                        f"{self.name} RabbitMQ metrics from Prometheus: {total_messages_telemetry} messages"
                                    )
            except Exception as e:
                logger.debug(f"{self.name} Failed to query Prometheus for RabbitMQ metrics: {e}")

            # Use telemetry backend as primary source, manual tracking as fallback
            total_messages = (
                total_messages_telemetry if total_messages_telemetry > 0 else total_messages_manual
            )
            messages_source = (
                rabbitmq_from_telemetry.get("source")
                if rabbitmq_from_telemetry
                else "manual_tracking"
            )

            metrics = {
                "messages_processed": total_messages,
                "messages_source": messages_source,
                "communication_log": self.communication_log[-10:],  # Last 10 messages
                "queue_stats": queue_stats,
                "queue_count": len(queue_stats),
                "telemetry_data": rabbitmq_from_telemetry,
            }

        except Exception as e:
            logger.warning(f"{self.name} failed to collect RabbitMQ metrics: {e}")
            metrics = {
                "messages_processed": len(self.communication_log),
                "communication_log": self.communication_log[-10:],
                "error": str(e),
            }

        return metrics

    async def collect_system_metrics(self) -> dict[str, Any]:
        """Collect system metrics (CPU, memory, GPU)"""
        metrics = {}

        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            metrics = {
                "cpu_usage_percent": cpu_percent,
                "memory_usage_gb": round(memory.used / (1024**3), 2),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_percent": memory.percent,
            }

            # Try to get GPU utilization
            try:
                result = await self.agent.execute_command(
                    "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits"
                )
                if result.get("success") and result.get("stdout"):
                    gpu_data = result.get("stdout", "").strip().split("\n")[0]
                    if gpu_data:
                        parts = gpu_data.split(", ")
                        if len(parts) >= 3:
                            gpu_util = int(parts[0].strip()) if parts[0].strip().isdigit() else 0
                            gpu_mem_used = (
                                int(parts[1].strip().split()[0])
                                if parts[1].strip().split()[0].isdigit()
                                else 0
                            )
                            gpu_mem_total = (
                                int(parts[2].strip().split()[0])
                                if parts[2].strip().split()[0].isdigit()
                                else 0
                            )
                            metrics["gpu_utilization"] = {
                                "gpu_usage_percent": gpu_util,
                                "memory_used_mb": gpu_mem_used,
                                "memory_total_mb": gpu_mem_total,
                                "memory_percent": round(
                                    (gpu_mem_used / gpu_mem_total * 100)
                                    if gpu_mem_total > 0
                                    else 0,
                                    2,
                                ),
                            }
                            # Record GPU metric via telemetry client
                            try:
                                self.agent.record_gauge("system_gpu_utilization_percent", gpu_util)
                            except Exception as e:
                                logger.debug(
                                    f"{self.name} failed to record GPU telemetry metric: {e}"
                                )
            except Exception as e:
                logger.debug(f"{self.name} GPU not available or nvidia-smi failed: {e}")
                metrics["gpu_utilization"] = None

            # Record system metrics via telemetry client
            try:
                self.agent.record_gauge("system_cpu_usage_percent", cpu_percent)
                self.agent.record_gauge("system_memory_usage_percent", memory.percent)
            except Exception as e:
                logger.debug(f"{self.name} failed to record system telemetry metrics: {e}")

        except Exception as e:
            logger.warning(f"{self.name} failed to collect system metrics: {e}")
            metrics = {"error": str(e)}

        return metrics

    async def collect_docker_events(self, database_metrics: dict[str, Any]) -> dict[str, Any]:
        """Collect Docker events"""
        events = {}

        try:
            # Get execution cycle start time for filtering
            cycle_start = None
            if "execution_duration" in database_metrics and database_metrics.get(
                "execution_duration", {}
            ).get("start_time"):
                start_time_str = database_metrics["execution_duration"]["start_time"]
                try:
                    from dateutil import parser

                    cycle_start = parser.parse(start_time_str)
                except (ImportError, Exception):
                    cycle_start = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                    if cycle_start.tzinfo:
                        cycle_start = cycle_start.astimezone(UTC).replace(tzinfo=None)

            # Get Docker events since cycle start (or last 5 minutes as fallback)
            since_time = "5m"  # Default
            if cycle_start:
                duration = datetime.utcnow() - cycle_start
                since_time = f"{int(duration.total_seconds())}s"

            # Get container lifecycle events
            result = await self.agent.execute_command(
                f"docker events --since {since_time} --format '{{{{.Time}}}} {{{{.Type}}}} {{{{.Action}}}} {{{{.Actor.Attributes.name}}}}'"
            )

            containers = {}
            images = {}
            events_list = []

            if result.get("success") and result.get("stdout"):
                docker_events = result.get("stdout", "").strip().split("\n")
                for event_line in docker_events:
                    if not event_line.strip():
                        continue
                    parts = event_line.split(" ")
                    if len(parts) >= 4:
                        event_time = parts[0]
                        event_type = parts[1]
                        event_action = parts[2]
                        event_name = " ".join(parts[3:]) if len(parts) > 3 else "unknown"

                        events_list.append(
                            {
                                "time": event_time,
                                "type": event_type,
                                "action": event_action,
                                "name": event_name,
                            }
                        )

                        # Track containers
                        if event_type == "container":
                            if event_name not in containers:
                                containers[event_name] = []
                            containers[event_name].append(
                                {"action": event_action, "time": event_time}
                            )

                        # Track images
                        elif event_type == "image":
                            if event_name not in images:
                                images[event_name] = []
                            images[event_name].append({"action": event_action, "time": event_time})

            events = {
                "containers": containers,
                "images": images,
                "events": events_list,
                "event_count": len(events_list),
                "container_count": len(containers),
                "image_count": len(images),
            }

        except Exception as e:
            logger.warning(f"{self.name} failed to collect Docker events: {e}")
            events = {"error": str(e)}

        return events

    async def collect_artifact_hashes(self) -> dict[str, str]:
        """Collect artifact hashes"""
        hashes = {}

        try:
            app_dir = "/app/warm-boot/apps/hello-squad"
            if os.path.exists(app_dir):
                for root, _dirs, files in os.walk(app_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "rb") as f:
                                file_hash = hashlib.sha256(f.read()).hexdigest()
                                relative_path = os.path.relpath(file_path, app_dir)
                                hashes[relative_path] = f"sha256:{file_hash}"
                        except Exception as e:
                            logger.warning(f"{self.name} failed to hash {file_path}: {e}")
        except Exception as e:
            logger.warning(f"{self.name} failed to collect artifact hashes: {e}")
            hashes = {"error": str(e)}

        return hashes

    async def collect_reasoning_logs(self, cycle_id: str) -> dict[str, Any]:
        """Collect reasoning logs from communication log"""
        logs = {}

        try:
            reasoning_entries = []
            ollama_logs = []
            tokens_by_agent = {}
            total_tokens_manual = 0

            for entry in self.communication_log:
                if (
                    "reasoning" in entry.get("message_type", "").lower()
                    or "llm" in entry.get("message_type", "").lower()
                ):
                    reasoning_entries.append(entry)

                    # Format as JSONL-like entry
                    ollama_log_entry = {
                        "timestamp": entry.get("timestamp"),
                        "agent": entry.get("agent"),
                        "cycle_id": entry.get("cycle_id"),
                        "trace_id": entry.get("trace_id"),
                        "prompt": entry.get("prompt", ""),
                        "response": entry.get("full_response", entry.get("description", "")),
                        "message_type": entry.get("message_type"),
                    }

                    # Include token usage
                    if "token_usage" in entry:
                        ollama_log_entry["token_usage"] = entry["token_usage"]
                        agent_name = entry.get("agent", "unknown")
                        entry_tokens = entry["token_usage"].get("total_tokens", 0)
                        if agent_name not in tokens_by_agent:
                            tokens_by_agent[agent_name] = 0
                        tokens_by_agent[agent_name] += entry_tokens
                        total_tokens_manual += entry_tokens

                    ollama_logs.append(ollama_log_entry)

            # Query Prometheus for token metrics
            tokens_from_telemetry = None
            total_tokens_telemetry = 0
            try:
                import aiohttp
                from infra.config.loader import get_config

                app_config = get_config()
                prometheus_url = app_config.observability.prometheus.url
                query_with_cycle_id = f'sum(agent_tokens_used_total{{cycle_id="{cycle_id}"}})'
                query_without_cycle_id = "sum(agent_tokens_used_total)"

                async with aiohttp.ClientSession() as session:
                    # First try with cycle_id label
                    async with session.get(
                        f"{prometheus_url}/api/v1/query",
                        params={"query": query_with_cycle_id},
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("status") == "success" and data.get("data", {}).get(
                                "result"
                            ):
                                result = (
                                    data["data"]["result"][0] if data["data"]["result"] else None
                                )
                                if result and "value" in result:
                                    total_tokens_telemetry = int(float(result["value"][1]))
                                    tokens_from_telemetry = {
                                        "source": "prometheus",
                                        "total_tokens": total_tokens_telemetry,
                                        "query": query_with_cycle_id,
                                    }
                                    logger.debug(
                                        f"{self.name} Token metrics from Prometheus: {total_tokens_telemetry} tokens"
                                    )

                    # If no results with cycle_id, try without cycle_id
                    if total_tokens_telemetry == 0:
                        async with session.get(
                            f"{prometheus_url}/api/v1/query",
                            params={"query": query_without_cycle_id},
                            timeout=aiohttp.ClientTimeout(total=5),
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get("status") == "success" and data.get("data", {}).get(
                                    "result"
                                ):
                                    total_sum = 0
                                    for result in data["data"]["result"]:
                                        if "value" in result:
                                            total_sum += int(float(result["value"][1]))
                                    if total_sum > 0:
                                        total_tokens_telemetry = total_sum
                                        tokens_from_telemetry = {
                                            "source": "prometheus",
                                            "total_tokens": total_tokens_telemetry,
                                            "query": query_without_cycle_id,
                                            "note": "Metrics without cycle_id label - aggregated all tokens",
                                        }
                                        logger.debug(
                                            f"{self.name} Token metrics from Prometheus (no cycle_id): {total_tokens_telemetry} tokens"
                                        )
            except Exception as e:
                logger.debug(f"{self.name} Failed to query Prometheus for token metrics: {e}")

            # Use telemetry backend as primary source, manual tracking as fallback
            tokens_used = (
                total_tokens_telemetry if total_tokens_telemetry > 0 else total_tokens_manual
            )
            tokens_source = (
                tokens_from_telemetry.get("source") if tokens_from_telemetry else "manual_tracking"
            )

            logs = {
                "reasoning_entries": reasoning_entries,
                "ollama_logs": ollama_logs,
                "entry_count": len(reasoning_entries),
                "agents_with_reasoning": list(
                    set(entry.get("agent", "unknown") for entry in reasoning_entries)
                ),
                "tokens_used": tokens_used,
                "tokens_by_agent": tokens_by_agent,
                "tokens_source": tokens_source,
                "tokens_from_telemetry": tokens_from_telemetry,
                "tokens_manual_fallback": total_tokens_manual
                if total_tokens_telemetry > 0
                else None,
            }

        except Exception as e:
            logger.warning(f"{self.name} failed to collect reasoning logs: {e}")
            logs = {"error": str(e)}

        return logs

    def build_event_timeline(self) -> list[dict[str, Any]]:
        """Build event timeline from communication log"""
        timeline = []

        try:
            for entry in self.communication_log:
                timeline.append(
                    {
                        "timestamp": entry.get("timestamp", "unknown"),
                        "agent": entry.get("agent", "unknown"),
                        "event_type": entry.get("message_type", "unknown"),
                        "description": entry.get("description", "No description"),
                    }
                )

            timeline = sorted(timeline, key=lambda x: x["timestamp"])

        except Exception as e:
            logger.warning(f"{self.name} failed to build event timeline: {e}")

        return timeline

    def _parse_datetime(self, datetime_str: str) -> datetime:
        """Parse datetime string with fallback strategies"""
        try:
            # Try datetime.fromisoformat first (Python 3.7+)
            dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            if dt.tzinfo:
                dt = dt.astimezone(UTC).replace(tzinfo=None)
            return dt
        except (ValueError, AttributeError):
            # Fallback to dateutil if available
            try:
                from dateutil import parser

                dt = parser.parse(datetime_str)
                if dt.tzinfo:
                    dt = dt.astimezone(UTC).replace(tzinfo=None)
                return dt
            except ImportError:
                # Last resort: assume format and parse manually
                logger.warning(f"{self.name} dateutil not available, using basic datetime parsing")
                return datetime.fromisoformat(datetime_str.replace("Z", "").split(".")[0])
