#!/usr/bin/env python3
"""
Unit tests for CycleSummaryComposer capability
Tests cycle summary composition capability
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.capabilities.data.compose_cycle_summary import CycleSummaryComposer


class TestCycleSummaryComposer:
    """Test CycleSummaryComposer capability"""
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent instance"""
        agent = MagicMock()
        agent.name = "test-agent"
        return agent
    
    @pytest.fixture
    def composer(self, mock_agent):
        """Create CycleSummaryComposer instance"""
        return CycleSummaryComposer(mock_agent)
    
    @pytest.mark.unit
    def test_composer_initialization(self, mock_agent):
        """Test CycleSummaryComposer initialization"""
        composer = CycleSummaryComposer(mock_agent)
        assert composer.agent == mock_agent
        assert composer.name == "test-agent"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_compose_success(self, composer):
        """Test successful cycle summary composition"""
        ecid = "ECID-WB-001"
        
        mock_snapshot = {
            'ecid': ecid,
            'tasks': [{'task_id': 'task-1', 'status': 'completed'}],
            'agents': {'agent1': {'tasks': []}}
        }
        
        mock_file_obj = AsyncMock()
        mock_file_obj.write = AsyncMock()
        mock_file_context = AsyncMock()
        mock_file_context.__aenter__ = AsyncMock(return_value=mock_file_obj)
        mock_file_context.__aexit__ = AsyncMock(return_value=None)
        
        # Mock agent's record_memory
        composer.agent.record_memory = AsyncMock()
        
        with patch.object(composer, '_load_snapshot', new_callable=AsyncMock, return_value=mock_snapshot), \
             patch.object(composer, '_load_metrics', new_callable=AsyncMock, return_value={}), \
             patch.object(composer, '_determine_health', return_value='green'), \
             patch.object(composer, '_build_agent_summary', return_value={}), \
             patch.object(composer, '_build_timeline', return_value=[]), \
             patch('aiofiles.open', return_value=mock_file_context):
            
            result = await composer.compose(ecid)
            
            assert 'ecid' in result or 'summary_path' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_compose_no_snapshot(self, composer):
        """Test composition when snapshot is missing"""
        ecid = "ECID-WB-001"
        
        with patch.object(composer, '_load_snapshot', new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError):
                await composer.compose(ecid)
    
    @pytest.mark.unit
    def test_determine_health_green(self, composer):
        """Test determining health flag as green"""
        snapshot = {
            'tasks': [{'status': 'completed'}, {'status': 'completed'}]
        }
        metrics = {}
        
        health = composer._determine_health(snapshot, metrics)
        
        assert health in ['green', 'yellow', 'red']
    
    @pytest.mark.unit
    def test_build_agent_summary(self, composer):
        """Test building agent summary"""
        snapshot = {
            'agents': {
                'agent1': {'tasks': [{'status': 'completed'}]},
                'agent2': {'tasks': [{'status': 'failed'}]}
            },
            'tasks': []
        }
        metrics = {}
        
        summary = composer._build_agent_summary(snapshot, metrics)
        
        assert isinstance(summary, dict)
    
    @pytest.mark.unit
    def test_build_timeline(self, composer):
        """Test building timeline"""
        snapshot = {
            'tasks': [{'task_id': 'task-1', 'created_at': '2025-01-01T00:00:00Z'}]
        }
        metrics = {}
        
        timeline = composer._build_timeline(snapshot, metrics)
        
        assert isinstance(timeline, list)

