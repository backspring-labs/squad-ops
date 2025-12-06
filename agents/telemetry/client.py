"""
TelemetryClient protocol definition for SquadOps agents.

Defines the interface that all telemetry providers must implement.
Follows the same pattern as LLMClient for consistency.
"""

from contextlib import AbstractContextManager
from typing import Any, Protocol


class TelemetryClient(Protocol):
    """Protocol for telemetry providers (OpenTelemetry, AWS, Azure, GCP, etc.)"""
    
    def get_tracer(self, name: str) -> Any:
        """Get a tracer for creating spans"""
        ...
    
    def get_meter(self, name: str) -> Any:
        """Get a meter for recording metrics"""
        ...
    
    def create_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        kind: str | None = None
    ) -> AbstractContextManager:
        """
        Create a telemetry span (trace segment)
        
        Args:
            name: Span name
            attributes: Optional span attributes (tags)
            kind: Optional span kind (internal, server, client, etc.)
        
        Returns:
            Context manager for span lifecycle
        """
        ...
    
    def record_counter(
        self,
        name: str,
        value: int = 1,
        attributes: dict[str, str] | None = None
    ) -> None:
        """
        Record a counter metric (incremental)
        
        Args:
            name: Metric name
            value: Counter increment (default 1)
            attributes: Optional metric labels/attributes
        """
        ...
    
    def record_gauge(
        self,
        name: str,
        value: float,
        attributes: dict[str, str] | None = None
    ) -> None:
        """
        Record a gauge metric (absolute value)
        
        Args:
            name: Metric name
            value: Gauge value
            attributes: Optional metric labels/attributes
        """
        ...
    
    def record_histogram(
        self,
        name: str,
        value: float,
        attributes: dict[str, str] | None = None
    ) -> None:
        """
        Record a histogram metric (distribution)
        
        Args:
            name: Metric name
            value: Histogram value
            attributes: Optional metric labels/attributes
        """
        ...

