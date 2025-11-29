"""
Metrics HTTP Server for exposing Prometheus metrics
Exposes /metrics endpoint on port 8888 for Prometheus scraping
"""

import logging
from typing import Optional
from aiohttp import web

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry metrics
try:
    from opentelemetry import metrics  # noqa: F401
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.exporter.prometheus import PrometheusMetricReader
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger.warning("OpenTelemetry not available for metrics server")

# Try to import prometheus_client for formatting
try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest, REGISTRY  # noqa: F401
    PROMETHEUS_CLIENT_AVAILABLE = True
except ImportError:
    PROMETHEUS_CLIENT_AVAILABLE = False
    logger.warning("prometheus_client not available for metrics formatting")


class MetricsHTTPServer:
    """HTTP server for exposing Prometheus metrics"""
    
    def __init__(self, port: int = 8888, meter_provider: Optional[MeterProvider] = None, prometheus_reader: Optional[PrometheusMetricReader] = None):
        """
        Initialize metrics HTTP server
        
        Args:
            port: Port to serve metrics on (default 8888)
            meter_provider: OpenTelemetry MeterProvider instance (optional)
            prometheus_reader: PrometheusMetricReader instance (optional, used to collect metrics)
        """
        self.port = port
        self.meter_provider = meter_provider
        self.prometheus_reader = prometheus_reader
        self.app = web.Application()
        self.runner = None
        self.site = None
        
        # Setup routes
        self.app.router.add_get('/metrics', self.handle_metrics)
        self.app.router.add_get('/health', self.handle_health)
    
    async def handle_metrics(self, request):
        """Handle /metrics endpoint - return Prometheus-formatted metrics"""
        # CRITICAL: Always try REGISTRY directly first - this is guaranteed to work
        # This ensures Python GC metrics are always returned
        if not PROMETHEUS_CLIENT_AVAILABLE:
            return web.Response(
                text="# PROMETHEUS_CLIENT_AVAILABLE is False\n",
                content_type='text/plain; version=0.0.4'
            )
        
        # Import symbols explicitly to ensure they're in scope
        from prometheus_client import generate_latest, REGISTRY, CONTENT_TYPE_LATEST
        
        # Strip charset from CONTENT_TYPE_LATEST (aiohttp doesn't allow it in content_type)
        content_type = CONTENT_TYPE_LATEST.split(';')[0].strip() if CONTENT_TYPE_LATEST else 'text/plain'
        
        try:
            default_text = generate_latest(REGISTRY)
            if default_text:
                decoded = default_text.decode('utf-8')
                # Return if we have any content (even empty is fine for Prometheus)
                return web.Response(
                    text=decoded,
                    content_type=content_type
                )
        except Exception as e:
            logger.error(f"Error generating metrics from REGISTRY: {e}", exc_info=True)
            # Try _get_prometheus_metrics as fallback
            try:
                metrics_text = self._get_prometheus_metrics()
                if metrics_text:
                    if isinstance(metrics_text, bytes):
                        metrics_text = metrics_text.decode('utf-8')
                    if metrics_text:
                        return web.Response(
                            text=metrics_text,
                            content_type=content_type
                        )
            except Exception as e2:
                logger.error(f"Error in fallback _get_prometheus_metrics: {e2}", exc_info=True)
        
        # Final fallback (should never reach here if prometheus_client is available)
        logger.error("handle_metrics: All paths failed - returning '# No metrics available'")
        return web.Response(
            text="# No metrics available\n",
            content_type='text/plain; version=0.0.4'
        )
    
    def _get_prometheus_metrics(self) -> str:
        """Get Prometheus-formatted metrics from PrometheusMetricReader"""
        # Always get Python GC metrics from default REGISTRY first (guaranteed to work)
        default_decoded = ""
        if PROMETHEUS_CLIENT_AVAILABLE:
            try:
                default_text = generate_latest(REGISTRY)
                default_decoded = default_text.decode('utf-8') if default_text else ""
                logger.debug(f"Got {len(default_decoded)} chars from default REGISTRY")
            except Exception as e:
                logger.warning(f"Error getting default REGISTRY: {e}", exc_info=True)
                default_decoded = ""
        
        try:
            
            # PrometheusMetricReader has an internal _collector that formats OpenTelemetry metrics
            # We need to register it with prometheus_client REGISTRY and use it for formatting
            if PROMETHEUS_CLIENT_AVAILABLE and self.prometheus_reader:
                try:
                    # Trigger collection from MeterProvider first
                    if self.meter_provider:
                        try:
                            # PrometheusMetricReader.collect() triggers collection from MeterProvider
                            self.prometheus_reader.collect(timeout_millis=5000)
                        except Exception as collect_error:
                            logger.debug(f"Reader collect() error (may be expected): {collect_error}")
                    
                    # Access the reader's internal collector for OpenTelemetry metrics
                    # The PrometheusMetricReader has a _collector that formats OpenTelemetry metrics
                    if hasattr(self.prometheus_reader, '_collector'):
                        try:
                            # Create a temporary registry with just the OpenTelemetry collector
                            from prometheus_client import CollectorRegistry
                            temp_registry = CollectorRegistry()
                            temp_registry.register(self.prometheus_reader._collector)
                            
                            # Generate formatted metrics from the temporary registry
                            otel_metrics = generate_latest(temp_registry)
                            otel_text = otel_metrics.decode('utf-8') if otel_metrics else ""
                            
                            # Combine OpenTelemetry metrics (if any) with Python GC metrics
                            if otel_text and otel_text.strip():
                                # Has OpenTelemetry metrics - combine them
                                if default_decoded:
                                    return otel_text + "\n" + default_decoded
                                return otel_text
                        except Exception as collector_error:
                            logger.debug(f"Error accessing _collector: {collector_error}")
                            # Fall through to return default_decoded
                    
                    # Return Python GC metrics (at minimum, always available)
                    if default_decoded:
                        return default_decoded
                except Exception as e:
                    logger.warning(f"Error generating metrics from prometheus_client REGISTRY: {e}", exc_info=True)
            
            # Return Python GC metrics (at minimum, always available)
            if default_decoded:
                return default_decoded
        except Exception as e:
            logger.warning(f"Error in OpenTelemetry metrics path: {e}", exc_info=True)
            # Continue to return default_decoded below (it was set before the try block)
        
        # Always return Python GC metrics if we have them (regardless of exceptions above)
        if default_decoded:
            logger.debug(f"Returning {len(default_decoded)} chars of Python GC metrics")
            return default_decoded
        
        # Final fallback (should never reach here if prometheus_client is available)
        logger.warning("No metrics available - this should not happen if prometheus_client is available")
        return "# No metrics collected yet\n"
    
    def _format_metric_data(self, metric_data) -> str:
        """Format OpenTelemetry MetricData to Prometheus text format (fallback)"""
        # This is a fallback formatter - prometheus_client.generate_latest() should be primary
        # OpenTelemetry's MetricData structure is complex, so we rely on prometheus_client integration
        try:
            lines = []
            lines.append("# HELP Metrics from OpenTelemetry")
            lines.append("# TYPE Metrics are automatically formatted by prometheus_client")
            
            # PrometheusMetricReader integrates with prometheus_client REGISTRY
            # If we reach here, it means prometheus_client wasn't available
            # Return placeholder with note
            lines.append("# NOTE: prometheus_client not available - using basic format")
            lines.append("# Metrics collected but formatted output requires prometheus_client")
            
            return "\n".join(lines) + "\n"
        except Exception as e:
            logger.debug(f"Error formatting metric data: {e}")
            return "# Error formatting metrics\n"
    
    async def handle_health(self, request):
        """Handle /health endpoint"""
        return web.Response(
            text="OK",
            content_type='text/plain'
        )
    
    async def start(self):
        """Start the HTTP server"""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
            await self.site.start()
            logger.info(f"Metrics HTTP server started on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start metrics HTTP server: {e}")
            raise
    
    async def stop(self):
        """Stop the HTTP server"""
        try:
            if self.site:
                await self.site.stop()
            if self.runner:
                await self.runner.cleanup()
            logger.info(f"Metrics HTTP server stopped")
        except Exception as e:
            logger.error(f"Error stopping metrics HTTP server: {e}")


async def start_metrics_server(port: int = 8888, meter_provider=None, prometheus_reader=None):
    """
    Start metrics HTTP server as a background task
    
    Args:
        port: Port to serve metrics on (default 8888)
        meter_provider: OpenTelemetry MeterProvider instance (optional)
        prometheus_reader: PrometheusMetricReader instance (optional)
    
    Returns:
        MetricsHTTPServer instance
    """
    server = MetricsHTTPServer(port=port, meter_provider=meter_provider, prometheus_reader=prometheus_reader)
    await server.start()
    return server

