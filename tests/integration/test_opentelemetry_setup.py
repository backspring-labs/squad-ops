"""
Integration tests for OpenTelemetry setup
Validates that OpenTelemetry is properly configured and accessible
"""

import os
import sys

import pytest

# Add agents path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))



class TestOpenTelemetrySetup:
    """Test OpenTelemetry initialization and configuration"""
    
    def test_base_agent_has_telemetry_attributes(self):
        """Test that BaseAgent has telemetry attributes after initialization"""
        # Use a real agent role that exists (lead) instead of "test"
        from agents.roles.lead.agent import LeadAgent
        
        agent = LeadAgent("test-lead-agent")
        
        # Should have telemetry_client (TelemetryClient abstraction)
        assert hasattr(agent, 'telemetry_client')
        assert agent.telemetry_client is not None
        
        # Should have telemetry helper methods
        assert hasattr(agent, 'get_tracer')
        assert hasattr(agent, 'get_meter')
        assert hasattr(agent, 'create_span')
        assert hasattr(agent, 'record_counter')
        assert hasattr(agent, 'record_gauge')
        assert hasattr(agent, 'record_histogram')
    
    def test_telemetry_helper_methods_exist(self):
        """Test that all telemetry helper methods exist and are callable"""
        # Use a real agent role that exists (lead) instead of "test"
        from agents.roles.lead.agent import LeadAgent
        
        agent = LeadAgent("test-lead-agent")
        
        # All helper methods should exist and be callable
        assert callable(agent.get_tracer)
        assert callable(agent.get_meter)
        assert callable(agent.create_span)
        assert callable(agent.record_counter)
        assert callable(agent.record_gauge)
        assert callable(agent.record_histogram)
    
    def test_create_span_context_manager(self):
        """Test that create_span returns a context manager"""
        # Use a real agent role that exists (lead) instead of "test"
        from agents.roles.lead.agent import LeadAgent
        
        agent = LeadAgent("test-lead-agent")
        
        # create_span should return a context manager
        span = agent.create_span("test-span")
        assert hasattr(span, '__enter__')
        assert hasattr(span, '__exit__')
    
    def test_record_metrics_no_error(self):
        """Test that recording metrics doesn't raise errors (graceful degradation)"""
        # Use a real agent role that exists (lead) instead of "test"
        from agents.roles.lead.agent import LeadAgent
        
        agent = LeadAgent("test-lead-agent")
        
        # Should not raise errors even if OpenTelemetry not fully configured
        try:
            agent.record_counter("test_counter", 1.0, {"label": "value"})
            agent.record_gauge("test_gauge", 42.0, {"label": "value"})
            agent.record_histogram("test_histogram", 100.0, {"label": "value"})
        except Exception as e:
            pytest.fail(f"Recording metrics should not raise errors: {e}")

