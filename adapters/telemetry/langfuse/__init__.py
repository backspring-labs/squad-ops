"""LangFuse LLM observability adapter (SIP-0061).

Provides the concrete LangFuse implementation of LLMObservabilityPort.
The langfuse SDK is lazily imported — this package can be imported without
the SDK installed; only LangFuseAdapter construction requires it.
"""

from adapters.telemetry.langfuse.adapter import LangFuseAdapter

__all__ = ["LangFuseAdapter"]
