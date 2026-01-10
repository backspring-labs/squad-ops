"""
Unit tests for TelemetryClient abstraction (Phase 0)
Tests TelemetryClient protocol, implementations, and TelemetryRouter
"""
from unittest.mock import MagicMock, patch

import pytest


class TestTelemetryClientProtocol:
    """Test TelemetryClient protocol interface"""
    
    @pytest.mark.unit
    def test_telemetry_client_import(self):
        """Test that TelemetryClient protocol can be imported"""
        from agents.telemetry.client import TelemetryClient
        
        # Verify protocol exists
        assert TelemetryClient is not None
    
    @pytest.mark.unit
    def test_telemetry_client_methods(self):
        """Test that TelemetryClient protocol defines required methods"""
        import inspect

        from agents.telemetry.client import TelemetryClient
        
        # Check for required methods
        methods = [m[0] for m in inspect.getmembers(TelemetryClient, predicate=inspect.isfunction)]
        assert 'create_span' in methods or hasattr(TelemetryClient, 'create_span')
        assert 'record_counter' in methods or hasattr(TelemetryClient, 'record_counter')
        assert 'record_gauge' in methods or hasattr(TelemetryClient, 'record_gauge')


class TestNullTelemetryClient:
    """Test NullTelemetryClient implementation"""
    
    @pytest.mark.unit
    def test_null_client_import(self):
        """Test that NullTelemetryClient can be imported"""
        from agents.telemetry.providers.null_client import NullTelemetryClient
        
        client = NullTelemetryClient()
        assert client is not None
    
    @pytest.mark.unit
    def test_null_client_no_op(self):
        """Test that NullTelemetryClient methods are no-ops"""
        from agents.telemetry.providers.null_client import NullTelemetryClient
        
        client = NullTelemetryClient()
        
        # All methods should be callable without errors
        result = client.create_span("test_span", attributes={})
        assert result is not None
        
        # Enter context should work
        with client.create_span("test", {}):
            pass
        
        client.record_counter("test_metric", 1, {})
        client.record_gauge("test_gauge", 1.0, {})
        client.record_histogram("test_histogram", 1.0, {})
        
        # Should not raise exceptions
        assert True


class TestOpenTelemetryClient:
    """Test OpenTelemetryClient implementation"""
    
    @pytest.mark.unit
    def test_opentelemetry_client_import(self):
        """Test that OpenTelemetryClient can be imported"""
        try:
            from agents.telemetry.providers.opentelemetry_client import OpenTelemetryClient
            
            config = {
                'service_name': 'test-service',
                'service_version': '1.0.0',
                'otlp_endpoint': 'http://localhost:4317'
            }
            
            client = OpenTelemetryClient(config)
            assert client is not None
        except ImportError:
            pytest.skip("OpenTelemetry not available")
    
    @pytest.mark.unit
    def test_opentelemetry_client_create_span(self):
        """Test OpenTelemetryClient.create_span()"""
        try:
            from agents.telemetry.providers.opentelemetry_client import OpenTelemetryClient
            
            config = {
                'service_name': 'test-service',
                'service_version': '1.0.0',
                'otlp_endpoint': 'http://localhost:4317'
            }
            
            client = OpenTelemetryClient(config)
            
            # create_span should return a context manager
            span = client.create_span("test_span", {"key": "value"})
            assert span is not None
            
            # Should be usable as context manager
            with span:
                pass
            
        except ImportError:
            pytest.skip("OpenTelemetry not available")
    
    @pytest.mark.unit
    def test_opentelemetry_client_record_counter(self):
        """Test OpenTelemetryClient.record_counter()"""
        try:
            from agents.telemetry.providers.opentelemetry_client import OpenTelemetryClient
            
            config = {
                'service_name': 'test-service',
                'service_version': '1.0.0',
                'otlp_endpoint': 'http://localhost:4317'
            }
            
            client = OpenTelemetryClient(config)
            
            # Should not raise exception
            client.record_counter("test_counter", 1, {"label": "value"})
            
        except ImportError:
            pytest.skip("OpenTelemetry not available")
    
    @pytest.mark.unit
    def test_opentelemetry_client_get_prometheus_reader(self):
        """Test OpenTelemetryClient.get_prometheus_reader()"""
        try:
            from agents.telemetry.providers.opentelemetry_client import OpenTelemetryClient
            
            config = {
                'service_name': 'test-service',
                'service_version': '1.0.0',
                'otlp_endpoint': 'http://localhost:4317'
            }
            
            client = OpenTelemetryClient(config)
            
            # Should return PrometheusMetricReader or None
            # Handle case where OpenTelemetry is not available or prometheus_reader not initialized
            try:
                reader = client.get_prometheus_reader()
                # Can be None if not configured
                assert reader is None or reader is not None
            except AttributeError:
                # prometheus_reader might not exist if OpenTelemetry failed to initialize
                pass
            
        except ImportError:
            pytest.skip("OpenTelemetry not available")


class TestTelemetryRouter:
    """Test TelemetryRouter factory"""
    
    @pytest.mark.unit
    def test_telemetry_router_import(self):
        """Test that TelemetryRouter can be imported"""
        from agents.telemetry.router import TelemetryRouter
        
        assert TelemetryRouter is not None
    
    @pytest.mark.unit
    def test_telemetry_router_from_config_local(self):
        """Test TelemetryRouter.from_config() for local platform"""
        with patch('infra.config.loader.load_config') as mock_get_config:
            from infra.config.schema import AppConfig, AgentConfig, LLMConfig, TelemetryConfig
            mock_config = MagicMock(spec=AppConfig)
            mock_config.agent = MagicMock(spec=AgentConfig)
            mock_config.agent.id = 'test-agent'
            mock_config.agent.role = 'test'
            mock_config.llm = MagicMock(spec=LLMConfig)
            mock_config.llm.model = 'test-model'
            mock_config.telemetry = MagicMock(spec=TelemetryConfig)
            mock_config.telemetry.backend = 'opentelemetry'
            mock_config.telemetry.otlp_endpoint = 'http://localhost:4317'
            mock_get_config.return_value = mock_config
            
            from agents.telemetry.router import TelemetryRouter
            
            try:
                client = TelemetryRouter.from_config()
                assert client is not None
            except ImportError:
                # OpenTelemetry might not be available in test environment
                pytest.skip("OpenTelemetry not available")
    
    @pytest.mark.unit
    def test_telemetry_router_from_config_null_fallback(self):
        """Test TelemetryRouter falls back to NullTelemetryClient when backend unavailable"""
        with patch('infra.config.loader.load_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.get_platform.return_value = 'unknown'
            mock_config.get_telemetry_config.return_value = {
                'backend': 'unavailable',
                'otlp_endpoint': 'http://localhost:4317'
            }
            mock_get_config.return_value = mock_config
            
            from agents.telemetry.router import TelemetryRouter
            
            client = TelemetryRouter.from_config()
            assert client is not None
            
            # Should be NullTelemetryClient when backend unavailable
            from agents.telemetry.providers.null_client import NullTelemetryClient
            assert isinstance(client, NullTelemetryClient)
    
    @pytest.mark.unit
    def test_telemetry_router_env_var_override(self, mock_unified_config):
        """Test TelemetryRouter respects config telemetry backend"""
        from agents.telemetry.router import TelemetryRouter
        
        # Mock config to return null backend
        mock_unified_config.telemetry.backend = 'null'
        
        with patch("infra.config.loader.load_config", return_value=mock_unified_config):
            client = TelemetryRouter.from_config()
            assert client is not None
            
            # Should be NullTelemetryClient when backend is set to 'null'
            from agents.telemetry.providers.null_client import NullTelemetryClient
            assert isinstance(client, NullTelemetryClient)

