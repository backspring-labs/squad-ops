"""
OpenTelemetry TelemetryClient implementation for SquadOps agents.

Wraps OpenTelemetry SDK for local/Prometheus deployment.
Supports OTLP Collector and Prometheus exporters.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Check if OpenTelemetry is available
try:
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.prometheus import PrometheusMetricReader
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource  # Fixed: resources (plural), not resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.semconv.resource import ResourceAttributes
    
    # Optional automatic instrumentation
    try:
        from opentelemetry.instrumentation.aiohttp import AioHttpClientInstrumentor
    except ImportError:
        AioHttpClientInstrumentor = None
    
    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
    except ImportError:
        AsyncPGInstrumentor = None
    
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger.warning("OpenTelemetry packages not available, telemetry will be disabled")
    TracerProvider = None
    MeterProvider = None
    Resource = None
    OTLPSpanExporter = None
    PrometheusMetricReader = None
    ResourceAttributes = None


class OpenTelemetryClient:
    """OpenTelemetry telemetry client implementation for local/Prometheus setup"""
    
    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize OpenTelemetry client
        
        Args:
            config: Optional configuration dict with:
                - service_name: Service name for resource attributes
                - service_version: Service version
                - agent_name: Agent name
                - agent_type: Agent type/role
                - agent_llm: LLM model name
                - otlp_endpoint: OTLP endpoint URL (optional)
                - prometheus_port: Prometheus metrics port (default 8888)
        """
        self.config = config or {}
        self.tracer = None
        self.meter = None
        self.tracer_provider = None
        self.meter_provider = None
        
        if not OPENTELEMETRY_AVAILABLE:
            logger.warning("OpenTelemetry not available, using null implementation")
            return
        
        self._setup_telemetry()
    
    def _setup_telemetry(self):
        """Set up OpenTelemetry SDK (TracerProvider, MeterProvider, exporters)"""
        try:
            # Get configuration with defaults
            service_name = self.config.get('service_name', 'squadops-agent')
            service_version = self.config.get('service_version', '0.3.0')
            agent_name = self.config.get('agent_name', 'unknown')
            agent_type = self.config.get('agent_type', 'unknown')
            agent_llm = self.config.get('agent_llm', 'unknown')
            
            # Create resource with attributes
            resource = Resource.create({
                ResourceAttributes.SERVICE_NAME: service_name,
                ResourceAttributes.SERVICE_VERSION: service_version,
                'agent.name': agent_name,
                'agent.type': agent_type,
                'agent.llm': agent_llm,
            })
            
            # Initialize TracerProvider
            self.tracer_provider = TracerProvider(resource=resource)
            
            # Configure OTLP exporter (if collector available)
            otlp_endpoint = self.config.get('otlp_endpoint') or os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
            if otlp_endpoint:
                try:
                    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                    self.tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                    logger.info(f"OTLP exporter configured for {otlp_endpoint}")
                except Exception as e:
                    logger.warning(f"Failed to configure OTLP exporter: {e}")
            else:
                logger.debug("OTLP endpoint not configured, using local-only traces")
            
            trace.set_tracer_provider(self.tracer_provider)
            self.tracer = trace.get_tracer(service_name, service_version)
            
            # Initialize MeterProvider with Prometheus exporter
            try:
                # PrometheusMetricReader collects metrics but doesn't expose HTTP endpoint
                # We'll expose metrics via separate HTTP server (Task 0.12)
                self.prometheus_reader = PrometheusMetricReader()
                self.meter_provider = MeterProvider(resource=resource, metric_readers=[self.prometheus_reader])
                metrics.set_meter_provider(self.meter_provider)
                self.meter = metrics.get_meter(service_name, service_version)
                logger.info("Prometheus metrics exporter configured (reader initialized)")
            except Exception as e:
                logger.warning(f"Failed to configure Prometheus exporter: {e}")
                self.meter = None
                self.prometheus_reader = None
            
            # Automatic instrumentation (when available)
            if AioHttpClientInstrumentor:
                try:
                    AioHttpClientInstrumentor().instrument()
                    logger.debug("aiohttp instrumentation enabled")
                except Exception as e:
                    logger.debug(f"aiohttp instrumentation failed: {e}")
            
            if AsyncPGInstrumentor:
                try:
                    AsyncPGInstrumentor().instrument()
                    logger.debug("asyncpg instrumentation enabled")
                except Exception as e:
                    logger.debug(f"asyncpg instrumentation failed: {e}")
            
            logger.info("OpenTelemetry initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry: {e}")
            self.tracer = None
            self.meter = None
            self.prometheus_reader = None
    
    def get_prometheus_reader(self):
        """Get PrometheusMetricReader instance for metrics server"""
        return self.prometheus_reader
    
    def get_tracer(self, name: str):
        """Get a tracer for creating spans"""
        return self.tracer if self.tracer else None
    
    def get_meter(self, name: str):
        """Get a meter for recording metrics"""
        return self.meter if self.meter else None
    
    def create_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        kind: str | None = None
    ):
        """
        Create a telemetry span (trace segment)
        
        Args:
            name: Span name
            attributes: Optional span attributes (tags)
            kind: Optional span kind (internal, server, client, etc.)
        
        Returns:
            Context manager for span lifecycle
        """
        if not self.tracer:
            # Return a no-op context manager if telemetry unavailable
            from contextlib import nullcontext
            return nullcontext()
        
        # start_as_current_span returns a context manager, not the span itself
        # We need to wrap it to set attributes when entering the context
        from contextlib import contextmanager
        
        @contextmanager
        def span_with_attributes():
            with self.tracer.start_as_current_span(name) as span:
                if attributes:
                    # Filter out None values - OpenTelemetry doesn't accept NoneType
                    filtered_attributes = {k: v for k, v in attributes.items() if v is not None}
                    for key, value in filtered_attributes.items():
                        span.set_attribute(key, value)
                yield span
        
        return span_with_attributes()
    
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
        if not self.meter:
            return
        
        try:
            counter = self.meter.create_counter(name)
            counter.add(value, attributes or {})
        except Exception as e:
            logger.debug(f"Failed to record counter {name}: {e}")
    
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
        if not self.meter:
            return
        
        try:
            # Use up_down_counter for gauge-like behavior
            gauge = self.meter.create_up_down_counter(name)
            gauge.add(value, attributes or {})
        except Exception as e:
            logger.debug(f"Failed to record gauge {name}: {e}")
    
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
        if not self.meter:
            return
        
        try:
            histogram = self.meter.create_histogram(name)
            histogram.record(value, attributes or {})
        except Exception as e:
            logger.debug(f"Failed to record histogram {name}: {e}")

