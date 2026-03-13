"""LangFuse LLM observability adapter (SIP-0061).

Non-blocking: all port methods enqueue to an internal buffer.
A single daemon thread handles background flushing to LangFuse.

The langfuse SDK is lazily imported in __init__ — this module can be
imported without the SDK; only construction triggers the import.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import random
import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from adapters.telemetry.langfuse.redaction import get_redaction_strategy
from squadops.config.schema import LangFuseConfig
from squadops.ports.telemetry.llm_observability import LLMObservabilityPort
from squadops.telemetry.models import (
    CorrelationContext,
    GenerationRecord,
    PromptLayerMetadata,
    StructuredEvent,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants (no magic numbers)
# ---------------------------------------------------------------------------
DEFAULT_FLUSH_INTERVAL_SECONDS = 5
DEFAULT_BUFFER_MAX_SIZE = 1000
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 5
OVERFLOW_WARNING_INTERVAL_SECONDS = 30
RETRY_BASE_DELAY_SECONDS = 1.0
RETRY_MAX_DELAY_SECONDS = 60.0
RETRY_BACKOFF_FACTOR = 2.0


# ---------------------------------------------------------------------------
# Internal event types for the buffer queue
# ---------------------------------------------------------------------------


class _EventType(StrEnum):
    START_CYCLE = "start_cycle"
    END_CYCLE = "end_cycle"
    START_PULSE = "start_pulse"
    END_PULSE = "end_pulse"
    START_TASK = "start_task"
    END_TASK = "end_task"
    GENERATION = "generation"
    EVENT = "event"
    FLUSH = "flush"


@dataclass(frozen=True)
class _BufferEntry:
    """Internal event envelope queued for background processing."""

    event_type: _EventType
    ctx: CorrelationContext
    payload: Any = None  # GenerationRecord, PromptLayerMetadata, StructuredEvent, etc.


class LangFuseAdapter(LLMObservabilityPort):
    """LangFuse implementation of LLMObservabilityPort.

    Non-blocking: enqueue to internal buffer. A single daemon thread
    handles all flushing to LangFuse.
    """

    def __init__(self, config: LangFuseConfig) -> None:
        # Lazy-import the SDK — fails here if not installed
        try:
            from langfuse import Langfuse  # noqa: F401
        except ImportError:
            raise ImportError(
                "langfuse SDK is required for LangFuseAdapter. "
                "Install with: pip install 'squadops[langfuse]'"
            ) from None

        self._config = config
        self._buffer: queue.Queue[_BufferEntry] = queue.Queue(maxsize=config.buffer_max_size)
        self._dropped_events = 0
        self._span_state: dict[str, Any] = {}  # Keyed by cycle_id/pulse_id/task_id
        self._lock = (
            threading.Lock()
        )  # Protects _span_state, _dropped_events, _last_overflow_warning
        self._shutdown = threading.Event()
        self._flush_requested = threading.Event()
        self._last_overflow_warning = 0.0  # Protected by _lock

        # Redaction applied before enqueue
        self._redaction = get_redaction_strategy(config.redaction_mode)

        # Initialize LangFuse client
        self._client = Langfuse(
            public_key=config.public_key,
            secret_key=config.secret_key,
            host=config.host,
        )

        # Start background flush thread
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="langfuse-flush"
        )
        self._flush_thread.start()

        logger.info(
            "langfuse_adapter_initialized",
            extra={
                "host": config.host,
                "buffer_max_size": config.buffer_max_size,
                "flush_interval": config.flush_interval_seconds,
                "redaction_mode": config.redaction_mode,
                "sample_rate": config.sample_rate_percent,
            },
        )

    # -------------------------------------------------------------------
    # Port interface — all non-blocking, enqueue only
    # -------------------------------------------------------------------

    def start_cycle_trace(self, ctx: CorrelationContext) -> None:
        self._enqueue(_BufferEntry(event_type=_EventType.START_CYCLE, ctx=ctx))

    def end_cycle_trace(self, ctx: CorrelationContext) -> None:
        self._enqueue(_BufferEntry(event_type=_EventType.END_CYCLE, ctx=ctx))

    def start_pulse_span(self, ctx: CorrelationContext) -> None:
        self._enqueue(_BufferEntry(event_type=_EventType.START_PULSE, ctx=ctx))

    def end_pulse_span(self, ctx: CorrelationContext) -> None:
        self._enqueue(_BufferEntry(event_type=_EventType.END_PULSE, ctx=ctx))

    def start_task_span(self, ctx: CorrelationContext) -> None:
        self._enqueue(_BufferEntry(event_type=_EventType.START_TASK, ctx=ctx))

    def end_task_span(self, ctx: CorrelationContext) -> None:
        self._enqueue(_BufferEntry(event_type=_EventType.END_TASK, ctx=ctx))

    def record_generation(
        self,
        ctx: CorrelationContext,
        record: GenerationRecord,
        prompt_layers: PromptLayerMetadata,
    ) -> None:
        # Sampling: applies ONLY to record_generation
        if self._config.sample_rate_percent < 100:
            if random.randint(1, 100) > self._config.sample_rate_percent:
                return  # Sampled out — silently dropped

        # Redact prompt/response text before buffering
        redacted_record = GenerationRecord(
            generation_id=record.generation_id,
            model=record.model,
            prompt_text=self._redaction.redact(record.prompt_text),
            response_text=self._redaction.redact(record.response_text),
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            total_tokens=record.total_tokens,
            latency_ms=record.latency_ms,
            prompt_name=record.prompt_name,
            prompt_version=record.prompt_version,
        )
        self._enqueue(
            _BufferEntry(
                event_type=_EventType.GENERATION,
                ctx=ctx,
                payload=(redacted_record, prompt_layers),
            )
        )

    def record_event(self, ctx: CorrelationContext, event: StructuredEvent) -> None:
        # Redact event message before buffering
        redacted_event = StructuredEvent(
            name=event.name,
            message=self._redaction.redact(event.message),
            level=event.level,
            attributes=event.attributes,
            timestamp=event.timestamp,
            span_id=event.span_id,
        )
        self._enqueue(_BufferEntry(event_type=_EventType.EVENT, ctx=ctx, payload=redacted_event))

    def flush(self) -> None:
        """Signal background thread to drain. Non-blocking."""
        self._flush_requested.set()

    def close(self) -> None:
        """Bounded flush + shutdown. Completes within shutdown_flush_timeout_seconds."""
        timeout = self._config.shutdown_flush_timeout_seconds
        self._shutdown.set()
        self._flush_requested.set()  # Wake the flush thread
        self._flush_thread.join(timeout=timeout)
        if self._flush_thread.is_alive():
            remaining = self._buffer.qsize()
            if remaining > 0:
                logger.warning("langfuse_close_timeout: discarding %d unflushed entries", remaining)
        # Shutdown the SDK client
        try:
            self._client.shutdown()
        except Exception:
            logger.warning("langfuse_client_shutdown_error", exc_info=True)

    async def health(self) -> dict:
        with self._lock:
            dropped = self._dropped_events
        buffer_size = self._buffer.qsize()

        details: dict[str, Any] = {
            "buffer_size": buffer_size,
            "dropped_events": dropped,
        }

        # Check if client is reachable (run blocking call off event loop)
        try:
            await asyncio.to_thread(self._client.auth_check)
            status = "ok"
        except Exception as exc:
            status = "down"
            details["error"] = str(exc)

        return {"status": status, "backend": "langfuse", "details": details}

    # -------------------------------------------------------------------
    # Internal: buffer management
    # -------------------------------------------------------------------

    def _enqueue(self, entry: _BufferEntry) -> None:
        """Enqueue an entry, dropping oldest on overflow."""
        try:
            self._buffer.put_nowait(entry)
        except queue.Full:
            # Drop oldest to make room
            try:
                self._buffer.get_nowait()
            except queue.Empty:
                pass  # Race condition — someone else drained it
            try:
                self._buffer.put_nowait(entry)
            except queue.Full:
                pass  # Still full — extremely unlikely, give up

            # All under one lock acquisition: increment counter + rate-limited warning
            now = time.monotonic()
            with self._lock:
                self._dropped_events += 1
                should_warn = now - self._last_overflow_warning >= OVERFLOW_WARNING_INTERVAL_SECONDS
                if should_warn:
                    self._last_overflow_warning = now
                total_dropped = self._dropped_events

            if should_warn:
                logger.warning(
                    "langfuse_buffer_overflow: dropped oldest entry (total dropped: %d)",
                    total_dropped,
                )

    # -------------------------------------------------------------------
    # Internal: background flush loop
    # -------------------------------------------------------------------

    def _flush_loop(self) -> None:
        """Background thread: drain buffer to LangFuse."""
        retry_delay = RETRY_BASE_DELAY_SECONDS

        while not self._shutdown.is_set():
            # Wait for flush interval or explicit signal
            self._flush_requested.wait(timeout=self._config.flush_interval_seconds)
            self._flush_requested.clear()

            try:
                self._drain_buffer()
                retry_delay = RETRY_BASE_DELAY_SECONDS  # Reset on success
            except Exception:
                logger.warning(
                    "langfuse_flush_error: retrying in %.1fs", retry_delay, exc_info=True
                )
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY_SECONDS)

        # Final drain attempt on shutdown
        try:
            self._drain_buffer()
        except Exception:
            logger.warning("langfuse_final_flush_error", exc_info=True)

    def _drain_buffer(self) -> None:
        """Process all entries currently in the buffer."""
        while True:
            try:
                entry = self._buffer.get_nowait()
            except queue.Empty:
                break
            self._process_entry(entry)

        # Flush the SDK client after draining
        try:
            self._client.flush()
        except Exception:
            logger.warning("langfuse_sdk_flush_error", exc_info=True)
            raise

    def _process_entry(self, entry: _BufferEntry) -> None:
        """Dispatch a single buffer entry to the LangFuse SDK."""
        ctx = entry.ctx
        tk = self._resolve_trace_key(ctx)

        if entry.event_type == _EventType.START_CYCLE:
            trace = self._client.trace(
                id=tk,
                name=f"cycle-{ctx.cycle_id}",
                metadata=self._ctx_metadata(ctx),
            )
            with self._lock:
                self._span_state[f"cycle:{tk}"] = trace

        elif entry.event_type == _EventType.END_CYCLE:
            with self._lock:
                trace = self._span_state.pop(f"cycle:{tk}", None)
            if trace is not None:
                trace.update(metadata={"ended": True})

        elif entry.event_type == _EventType.START_PULSE:
            with self._lock:
                trace = self._span_state.get(f"cycle:{tk}")
            if trace is not None:
                span = trace.span(
                    name=f"pulse-{ctx.pulse_id}",
                    metadata=self._ctx_metadata(ctx),
                )
                with self._lock:
                    self._span_state[f"pulse:{tk}:{ctx.pulse_id}"] = span

        elif entry.event_type == _EventType.END_PULSE:
            with self._lock:
                span = self._span_state.pop(f"pulse:{tk}:{ctx.pulse_id}", None)
            if span is not None:
                span.end()

        elif entry.event_type == _EventType.START_TASK:
            pulse_key = f"pulse:{tk}:{ctx.pulse_id}"
            with self._lock:
                parent = self._span_state.get(pulse_key)
                if parent is None:
                    # Fall back to cycle trace if no pulse span
                    parent = self._span_state.get(f"cycle:{tk}")
            if parent is not None:
                span = parent.span(
                    name=f"task-{ctx.task_id}",
                    metadata=self._ctx_metadata(ctx),
                )
                with self._lock:
                    self._span_state[f"task:{tk}:{ctx.task_id}"] = span

        elif entry.event_type == _EventType.END_TASK:
            with self._lock:
                span = self._span_state.pop(f"task:{tk}:{ctx.task_id}", None)
            if span is not None:
                span.end()

        elif entry.event_type == _EventType.GENERATION:
            record, prompt_layers = entry.payload
            task_key = f"task:{tk}:{ctx.task_id}"
            with self._lock:
                parent = self._span_state.get(task_key)
                if parent is None:
                    parent = self._span_state.get(f"cycle:{tk}")
            if parent is not None:
                # SIP-0084: resolve Langfuse prompt object for prompt-to-generation linkage
                langfuse_prompt = None
                if record.prompt_name:
                    langfuse_prompt = self._resolve_langfuse_prompt(
                        record.prompt_name, record.prompt_version
                    )

                gen_kwargs: dict[str, Any] = {
                    "id": record.generation_id,
                    "name": f"generation-{record.generation_id[:8]}",
                    "model": record.model,
                    "input": record.prompt_text,
                    "output": record.response_text,
                    "usage": {
                        "prompt_tokens": record.prompt_tokens,
                        "completion_tokens": record.completion_tokens,
                        "total_tokens": record.total_tokens,
                    },
                    "metadata": {
                        "latency_ms": record.latency_ms,
                        "prompt_layer_set_id": prompt_layers.prompt_layer_set_id,
                        "prompt_layers": [
                            {
                                "type": layer.layer_type,
                                "id": layer.layer_id,
                                "version": layer.layer_version,
                                "hash": layer.layer_hash,
                            }
                            for layer in prompt_layers.layers
                        ],
                        **self._ctx_metadata(ctx),
                    },
                }
                if langfuse_prompt is not None:
                    gen_kwargs["prompt"] = langfuse_prompt
                parent.generation(**gen_kwargs)

        elif entry.event_type == _EventType.EVENT:
            event: StructuredEvent = entry.payload
            # Attach event to the most specific active span
            parent = self._find_active_span(ctx)
            if parent is not None:
                parent.event(
                    name=event.name,
                    metadata={
                        "message": event.message,
                        "level": event.level,
                        "attributes": dict(event.attributes) if event.attributes else {},
                        **self._ctx_metadata(ctx),
                    },
                )

    # -------------------------------------------------------------------
    # Internal: helpers
    # -------------------------------------------------------------------

    def _resolve_langfuse_prompt(
        self, prompt_name: str, prompt_version: int | None = None
    ) -> Any:
        """Resolve a Langfuse prompt object for prompt-to-generation linkage.

        Returns the prompt object on success, None on any failure (best-effort).
        Called from the background flush thread — must not raise.
        """
        try:
            kwargs: dict[str, Any] = {"name": prompt_name}
            if prompt_version is not None:
                kwargs["version"] = prompt_version
            return self._client.get_prompt(**kwargs)
        except Exception:
            logger.debug(
                "langfuse_prompt_resolve_failed",
                extra={"prompt_name": prompt_name, "prompt_version": prompt_version},
                exc_info=True,
            )
            return None

    @staticmethod
    def _resolve_trace_key(ctx: CorrelationContext) -> str:
        """Return the canonical trace key: prefer trace_id, fall back to cycle_id."""
        return ctx.trace_id or ctx.cycle_id

    def _find_active_span(self, ctx: CorrelationContext) -> Any:
        """Find the most specific active span for a context."""
        tk = self._resolve_trace_key(ctx)
        with self._lock:
            # Try task → pulse → cycle
            if ctx.task_id:
                span = self._span_state.get(f"task:{tk}:{ctx.task_id}")
                if span is not None:
                    return span
            if ctx.pulse_id:
                span = self._span_state.get(f"pulse:{tk}:{ctx.pulse_id}")
                if span is not None:
                    return span
            return self._span_state.get(f"cycle:{tk}")

    @staticmethod
    def _ctx_metadata(ctx: CorrelationContext) -> dict[str, Any]:
        """Extract non-None context fields as metadata dict."""
        meta: dict[str, Any] = {"cycle_id": ctx.cycle_id}
        if ctx.pulse_id:
            meta["pulse_id"] = ctx.pulse_id
        if ctx.task_id:
            meta["task_id"] = ctx.task_id
        if ctx.correlation_id:
            meta["correlation_id"] = ctx.correlation_id
        if ctx.causation_id:
            meta["causation_id"] = ctx.causation_id
        if ctx.agent_id:
            meta["agent_id"] = ctx.agent_id
        if ctx.agent_role:
            meta["agent_role"] = ctx.agent_role
        if ctx.trace_id:
            meta["trace_id"] = ctx.trace_id
        if ctx.span_id:
            meta["span_id"] = ctx.span_id
        if ctx.message_id:
            meta["message_id"] = ctx.message_id
        return meta
