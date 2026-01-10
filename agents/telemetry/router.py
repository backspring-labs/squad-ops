"""
Telemetry router for selecting and configuring telemetry providers.

Routes telemetry requests to the appropriate provider based on platform.
Follows the same pattern as LLMRouter for consistency.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

from agents.telemetry.client import TelemetryClient
from agents.telemetry.providers.null_client import NullTelemetryClient
from agents.telemetry.providers.opentelemetry_client import OpenTelemetryClient

# Cloud providers will be imported when implemented
# from agents.telemetry.providers.aws_client import AWSTelemetryClient
# from agents.telemetry.providers.azure_client import AzureTelemetryClient
# from agents.telemetry.providers.gcp_client import GCPTelemetryClient


class TelemetryRouter:
    """Route telemetry requests to configured provider based on platform"""
    
    def __init__(self, config: dict[str, Any] | None = None):
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
    def from_config(cls, config_path: str | None = None) -> TelemetryClient:
        """
        Load router from unified config and return appropriate TelemetryClient
        
        Args:
            config_path: Optional config path (not used, for consistency with LLMRouter)
        
        Returns:
            TelemetryClient instance appropriate for the platform
        """
        try:
            import os
            from infra.config.loader import load_config
            strict_mode = os.getenv("SQUADOPS_STRICT_CONFIG", "false").lower() == "true"
            app_config = load_config(strict=strict_mode)
            # Platform is not in AppConfig schema yet, use default
            platform = "local"
            
            # Get telemetry backend from AppConfig
            telemetry_backend = app_config.telemetry.backend
            
            # Build telemetry config for the client
            telemetry_config = cls._build_telemetry_config(app_config, platform, telemetry_backend)
            
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
    def _build_telemetry_config(app_config, platform: str, backend: str | None = None) -> dict[str, Any]:
        """
        Build telemetry configuration from AppConfig
        
        Args:
            app_config: AppConfig instance
            platform: Platform name
            backend: Optional backend override
        
        Returns:
            Configuration dict for TelemetryClient
        """
        config = {
            'platform': platform,
            'telemetry_backend': backend or platform,
        }
        
        # Get agent info from AppConfig
        try:
            from config.version import SQUADOPS_VERSION
            config['service_name'] = 'squadops-agent'
            config['service_version'] = SQUADOPS_VERSION
            config['agent_name'] = app_config.agent.id
            config['agent_type'] = app_config.agent.role
            config['agent_llm'] = app_config.llm.model or 'unknown'
        except Exception as e:
            logger.debug(f"Failed to get agent info from AppConfig: {e}")
        
        # Get OTLP endpoint from AppConfig
        if app_config.telemetry.otlp_endpoint:
            config['otlp_endpoint'] = app_config.telemetry.otlp_endpoint
        
        # Get Prometheus port from AppConfig
        config['prometheus_port'] = app_config.telemetry.prometheus_port
        
        # Platform-specific configuration from AppConfig
        if backend == 'aws' and app_config.telemetry.aws:
            config['aws_region'] = app_config.telemetry.aws.region
            config['cloudwatch_logs_group'] = app_config.telemetry.aws.cloudwatch_logs_group
            config['xray_tracing_enabled'] = app_config.telemetry.aws.xray_tracing_enabled
        elif backend == 'azure' and app_config.telemetry.azure:
            config['azure_connection_string'] = app_config.telemetry.azure.connection_string
            config['azure_instrumentation_key'] = app_config.telemetry.azure.instrumentation_key
        elif backend == 'gcp' and app_config.telemetry.gcp:
            config['gcp_project_id'] = app_config.telemetry.gcp.project_id
            config['gcp_credentials_path'] = app_config.telemetry.gcp.credentials_path
        
        return config
    
    def get_default_client(self) -> TelemetryClient:
        """
        Get default telemetry client for the current platform
        
        Returns:
            TelemetryClient instance
        """
        return self.from_config()

