"""
Null TelemetryClient implementation for SquadOps agents.

No-op implementation used when telemetry is unavailable, disabled, or for testing.
Similar to mock LLM client when USE_LOCAL_LLM=false.
"""

from contextlib import nullcontext
from typing import Any


class NullTelemetryClient:
    """Null/no-op telemetry client implementation"""
    
    def __init__(self):
        """Initialize null telemetry client (no-op)"""
        pass
    
    def get_tracer(self, name: str) -> Any:
        """Get a tracer (returns None for null client)"""
        return None
    
    def get_meter(self, name: str) -> Any:
        """Get a meter (returns None for null client)"""
        return None
    
    def create_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        kind: str | None = None
    ):
        """
        Create a telemetry span (no-op context manager)
        
        Args:
            name: Span name (ignored)
            attributes: Optional span attributes (ignored)
            kind: Optional span kind (ignored)
        
        Returns:
            Null context manager (no-op)
        """
        return nullcontext()
    
    def record_counter(
        self,
        name: str,
        value: int = 1,
        attributes: dict[str, str] | None = None
    ) -> None:
        """
        Record a counter metric (no-op)
        
        Args:
            name: Metric name (ignored)
            value: Counter increment (ignored)
            attributes: Optional metric labels/attributes (ignored)
        """
        pass
    
    def record_gauge(
        self,
        name: str,
        value: float,
        attributes: dict[str, str] | None = None
    ) -> None:
        """
        Record a gauge metric (no-op)
        
        Args:
            name: Metric name (ignored)
            value: Gauge value (ignored)
            attributes: Optional metric labels/attributes (ignored)
        """
        pass
    
    def record_histogram(
        self,
        name: str,
        value: float,
        attributes: dict[str, str] | None = None
    ) -> None:
        """
        Record a histogram metric (no-op)
        
        Args:
            name: Metric name (ignored)
            value: Histogram value (ignored)
            attributes: Optional metric labels/attributes (ignored)
        """
        pass

