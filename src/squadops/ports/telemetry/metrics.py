"""Metrics port interface.

Abstract base class for metrics collection adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence


class MetricsPort(ABC):
    """Port interface for metrics collection.

    Adapters must implement counter, gauge, and histogram methods.
    All implementations must be non-blocking (enqueue/buffer, do not block caller).
    """

    @abstractmethod
    def counter(
        self,
        name: str,
        value: float = 1,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name
            value: Amount to increment (default 1)
            labels: Optional labels/tags for the metric
        """
        ...

    @abstractmethod
    def gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge metric value.

        Args:
            name: Metric name
            value: Current value
            labels: Optional labels/tags for the metric
        """
        ...

    @abstractmethod
    def histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        *,
        boundaries: Sequence[float] | None = None,
    ) -> None:
        """Record a histogram observation.

        Args:
            name: Metric name
            value: Observed value
            labels: Optional labels/tags for the metric
            boundaries: The instrument's bucket upper bounds, ascending, where the caller knows
                its scale (#2260). Applied when the instrument is first created; ``None`` leaves
                the backend's defaults. An adapter that keeps no buckets ignores them.
        """
        ...
