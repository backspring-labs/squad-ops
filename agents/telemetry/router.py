"""
Telemetry router for selecting and configuring telemetry providers.

Routes telemetry requests to the appropriate provider based on platform.
Follows the same pattern as LLMRouter for consistency.
"""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

from agents.telemetry.client import TelemetryClient
from agents.telemetry.providers.opentelemetry_client import OpenTelemetryClient
from agents.telemetry.providers.null_client import NullTelemetryClient

# Cloud providers will be imported when implemented
# from agents.telemetry.providers.aws_client import AWSTelemetryClient
# from agents.telemetry.providers.azure_client import AzureTelemetryClient
# from agents.telemetry.providers.gcp_client import GCPTelemetryClient


class TelemetryRouter:
    """Route telemetry requests to configured provider based on platform"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize telemetry router
        
        Args:
            config: Optional configuration dict with:
                - platform: Platform name (local, aws, azure, gcp, jetson)
                - telemetry_backend: Backend override (local, aws, azure, gcp, null)
                - telemetry_config: Backend-specific configuration
        """
        self.config = config or {}
        self.platform = self.config.get('platform', 'local')
        self.telemetry_backend = self.config.get('telemetry_backend')
    
    @classmethod
    def from_config(cls, config_path: Optional[str] = None) -> TelemetryClient:
        """
        Load router from unified config and return appropriate TelemetryClient
        
        Args:
            config_path: Optional config path (not used, for consistency with LLMRouter)
        
        Returns:
            TelemetryClient instance appropriate for the platform
        """
        try:
            from config.unified_config import get_config
            unified_config = get_config()
            platform = unified_config.get_platform()
            
            # Check for telemetry config override
            telemetry_backend = os.getenv('TELEMETRY_BACKEND')
            if telemetry_backend:
                logger.info(f"Using TELEMETRY_BACKEND override: {telemetry_backend}")
            else:
                # Try to get from unified config
                try:
                    telemetry_config = unified_config.get_telemetry_config()
                    if telemetry_config:
                        telemetry_backend = telemetry_config.get('backend')
                except AttributeError:
                    # get_telemetry_config() not implemented yet, use platform
                    pass
            
            # Build telemetry config for the client
            telemetry_config = cls._build_telemetry_config(unified_config, platform, telemetry_backend)
            
            # Select TelemetryClient based on backend or platform
            backend = telemetry_backend or platform
            
            if backend == 'aws':
                # TODO: Implement AWSTelemetryClient in Task 0.2b
                logger.warning("AWSTelemetryClient not implemented yet, falling back to OpenTelemetryClient")
                return OpenTelemetryClient(telemetry_config)
            elif backend == 'azure':
                # TODO: Implement AzureTelemetryClient in Task 0.2c
                logger.warning("AzureTelemetryClient not implemented yet, falling back to OpenTelemetryClient")
                return OpenTelemetryClient(telemetry_config)
            elif backend == 'gcp':
                # TODO: Implement GCPTelemetryClient in Task 0.2d
                logger.warning("GCPTelemetryClient not implemented yet, falling back to OpenTelemetryClient")
                return OpenTelemetryClient(telemetry_config)
            elif backend in ('local', 'jetson'):
                # Local deployment: use OpenTelemetryClient (Prometheus/Grafana or OTLP only)
                return OpenTelemetryClient(telemetry_config)
            else:
                # Unknown platform or disabled: use NullTelemetryClient
                logger.info(f"Unknown platform '{backend}' or telemetry disabled, using NullTelemetryClient")
                return NullTelemetryClient()
                
        except Exception as e:
            logger.warning(f"Failed to load telemetry config, using NullTelemetryClient: {e}")
            return NullTelemetryClient()
    
    @staticmethod
    def _build_telemetry_config(unified_config, platform: str, backend: Optional[str] = None) -> Dict[str, Any]:
        """
        Build telemetry configuration from unified config
        
        Args:
            unified_config: SquadOpsConfig instance
            platform: Platform name
            backend: Optional backend override
        
        Returns:
            Configuration dict for TelemetryClient
        """
        config = {
            'platform': platform,
            'telemetry_backend': backend or platform,
        }
        
        # Get agent info from unified config
        try:
            config['service_name'] = 'squadops-agent'
            config['service_version'] = unified_config.get_deployment_config('framework_version') or '0.3.0'
            config['agent_name'] = unified_config.get_agent_id()
            config['agent_type'] = unified_config.get_agent_role()
            config['agent_llm'] = unified_config.get_agent_model() or 'unknown'
        except Exception as e:
            logger.debug(f"Failed to get agent info from unified config: {e}")
        
        # Get OTLP endpoint from environment or unified config
        otlp_endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
        if otlp_endpoint:
            config['otlp_endpoint'] = otlp_endpoint
        
        # Get Prometheus port from environment
        prometheus_port = os.getenv('PROMETHEUS_METRICS_PORT', '8888')
        try:
            config['prometheus_port'] = int(prometheus_port)
        except ValueError:
            config['prometheus_port'] = 8888
        
        # Platform-specific configuration (to be loaded from platform profiles)
        if backend == 'aws':
            # TODO: Load from config/environments/aws.yaml
            config['aws_region'] = os.getenv('AWS_REGION')
            config['cloudwatch_logs_group'] = os.getenv('CLOUDWATCH_LOGS_GROUP', 'squadops/agents')
            config['xray_tracing_enabled'] = os.getenv('XRAY_TRACING_ENABLED', 'true').lower() == 'true'
        elif backend == 'azure':
            # TODO: Load from config/environments/azure.yaml
            config['azure_connection_string'] = os.getenv('AZURE_CONNECTION_STRING')
            config['azure_instrumentation_key'] = os.getenv('AZURE_INSTRUMENTATION_KEY')
        elif backend == 'gcp':
            # TODO: Load from config/environments/gcp.yaml
            config['gcp_project_id'] = os.getenv('GCP_PROJECT_ID')
            config['gcp_credentials_path'] = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        return config
    
    def get_default_client(self) -> TelemetryClient:
        """
        Get default telemetry client for the current platform
        
        Returns:
            TelemetryClient instance
        """
        return self.from_config()

