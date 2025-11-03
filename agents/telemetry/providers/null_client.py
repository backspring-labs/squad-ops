"""
Null TelemetryClient implementation for SquadOps agents.

No-op implementation used when telemetry is unavailable, disabled, or for testing.
Similar to mock LLM client when USE_LOCAL_LLM=false.
"""

from typing import Optional, Dict, Any
from contextlib import nullcontext
from agents.telemetry.client import TelemetryClient


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
        attributes: Optional[Dict[str, Any]] = None,
        kind: Optional[str] = None
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
        attributes: Optional[Dict[str, str]] = None
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
        attributes: Optional[Dict[str, str]] = None
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
        attributes: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a histogram metric (no-op)
        
        Args:
            name: Metric name (ignored)
            value: Histogram value (ignored)
            attributes: Optional metric labels/attributes (ignored)
        """
        pass

