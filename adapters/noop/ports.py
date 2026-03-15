"""NoOp port implementations for PortsBundle bootstrap.

Cycle task handlers don't use skills or external ports, but the
PortsBundle dataclass requires concrete values for all 7 slots.
These stubs exist only to satisfy that requirement.

Behavior split per SIP-0066 D3:
  - Safe do-nothing (fire-and-forget / ambient): MetricsPort, EventPort, QueuePort
  - Hard-fail (NotImplementedError): LLMPort, MemoryPort, PromptService, FileSystemPort

Part of SIP-0066 Phase 2.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import uuid4

from squadops.agents.base import PortsBundle
from squadops.comms.queue_message import QueueMessage
from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse
from squadops.memory.models import MemoryEntry, MemoryQuery, MemoryResult
from squadops.ports.comms.queue import QueuePort
from squadops.ports.llm.provider import LLMPort
from squadops.ports.memory.store import MemoryPort
from squadops.ports.prompts.service import PromptService
from squadops.ports.telemetry.events import EventPort
from squadops.ports.telemetry.metrics import MetricsPort
from squadops.ports.tools.filesystem import FileSystemPort
from squadops.prompts.models import AssembledPrompt
from squadops.telemetry.models import Span, StructuredEvent

# ---------------------------------------------------------------------------
# Hard-fail stubs (intentional calls that should never happen)
# ---------------------------------------------------------------------------


class NoOpLLMPort(LLMPort):
    """Hard-fail LLM stub. Used when no LLM provider is configured."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError("NoOpLLMPort: no LLM provider configured")

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> ChatMessage:
        raise NotImplementedError("NoOpLLMPort: no LLM provider configured")

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[str]:
        raise NotImplementedError("NoOpLLMPort: no LLM provider configured")
        yield  # pragma: no cover — unreachable, makes this a proper async generator

    def list_models(self) -> list[str]:
        raise NotImplementedError("NoOpLLMPort: no LLM provider configured")

    async def refresh_models(self) -> list[str]:
        raise NotImplementedError("NoOpLLMPort: no LLM provider configured")

    async def health(self) -> dict[str, Any]:
        raise NotImplementedError("NoOpLLMPort: no LLM provider configured")


class NoOpMemoryPort(MemoryPort):
    """Hard-fail memory stub. Cycle task handlers never access memory."""

    async def store(self, entry: MemoryEntry) -> str:
        raise NotImplementedError("NoOpMemoryPort: memory not expected in cycle task handlers")

    async def search(self, query: MemoryQuery) -> list[MemoryResult]:
        raise NotImplementedError("NoOpMemoryPort: memory not expected in cycle task handlers")

    async def get(self, memory_id: str) -> MemoryEntry | None:
        raise NotImplementedError("NoOpMemoryPort: memory not expected in cycle task handlers")

    async def delete(self, memory_id: str) -> bool:
        raise NotImplementedError("NoOpMemoryPort: memory not expected in cycle task handlers")


class NoOpPromptService(PromptService):
    """Hard-fail prompt stub. Cycle task handlers never assemble prompts."""

    def assemble(
        self,
        role: str,
        hook: str,
        task_type: str | None = None,
        recovery: bool = False,
    ) -> AssembledPrompt:
        raise NotImplementedError(
            "NoOpPromptService: prompt assembly not expected in cycle task handlers"
        )

    def get_system_prompt(self, role: str) -> AssembledPrompt:
        raise NotImplementedError(
            "NoOpPromptService: prompt assembly not expected in cycle task handlers"
        )

    def get_version(self) -> str:
        raise NotImplementedError(
            "NoOpPromptService: prompt assembly not expected in cycle task handlers"
        )


class NoOpFileSystemPort(FileSystemPort):
    """Hard-fail filesystem stub. Cycle task handlers never touch the filesystem."""

    def read(self, path: Path) -> str:
        raise NotImplementedError(
            "NoOpFileSystemPort: filesystem not expected in cycle task handlers"
        )

    def write(self, path: Path, content: str) -> None:
        raise NotImplementedError(
            "NoOpFileSystemPort: filesystem not expected in cycle task handlers"
        )

    def exists(self, path: Path) -> bool:
        raise NotImplementedError(
            "NoOpFileSystemPort: filesystem not expected in cycle task handlers"
        )

    def list_dir(self, path: Path, pattern: str | None = None) -> list[Path]:
        raise NotImplementedError(
            "NoOpFileSystemPort: filesystem not expected in cycle task handlers"
        )

    def mkdir(self, path: Path, parents: bool = True) -> None:
        raise NotImplementedError(
            "NoOpFileSystemPort: filesystem not expected in cycle task handlers"
        )

    def delete(self, path: Path) -> None:
        raise NotImplementedError(
            "NoOpFileSystemPort: filesystem not expected in cycle task handlers"
        )


# ---------------------------------------------------------------------------
# Safe do-nothing stubs (ambient / fire-and-forget)
# ---------------------------------------------------------------------------


class NoOpMetricsPort(MetricsPort):
    """Safe no-op metrics. Pipeline may emit metrics implicitly."""

    def counter(self, name: str, value: float = 1, labels: dict[str, str] | None = None) -> None:
        pass

    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        pass

    def histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        pass


class NoOpEventPort(EventPort):
    """Safe no-op events. Pipeline may emit events implicitly."""

    def emit(self, event: StructuredEvent) -> None:
        pass

    def start_span(
        self,
        name: str,
        parent: Span | None = None,
        attributes: dict[str, str] | None = None,
    ) -> Span:
        return Span(name=name, trace_id=uuid4().hex, span_id=uuid4().hex)

    def end_span(self, span: Span) -> None:
        pass


class NoOpQueuePort(QueuePort):
    """Safe no-op queue. Replicates existing pattern from ports/comms/noop.py."""

    async def publish(
        self, queue_name: str, payload: str, delay_seconds: int | None = None
    ) -> None:
        pass

    async def consume(self, queue_name: str, max_messages: int = 1) -> list[QueueMessage]:
        return []

    async def ack(self, message: QueueMessage) -> None:
        pass

    async def retry(self, message: QueueMessage, delay_seconds: int) -> None:
        pass

    async def health(self) -> dict[str, Any]:
        return {"status": "healthy", "provider": "noop"}

    def capabilities(self) -> dict[str, bool]:
        return {"delay": True, "fifo": True, "priority": True}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_noop_ports_bundle() -> PortsBundle:
    """Create PortsBundle with NoOp stubs for orchestrator bootstrap.

    Cycle task handlers don't use skills or external ports.
    These stubs exist only to satisfy the PortsBundle dataclass.
    """
    return PortsBundle(
        llm=NoOpLLMPort(),
        memory=NoOpMemoryPort(),
        prompt_service=NoOpPromptService(),
        queue=NoOpQueuePort(),
        metrics=NoOpMetricsPort(),
        events=NoOpEventPort(),
        filesystem=NoOpFileSystemPort(),
    )
