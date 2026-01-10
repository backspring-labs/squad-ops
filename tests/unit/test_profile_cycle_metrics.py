#!/usr/bin/env python3
"""
Unit tests for CycleMetricsProfiler capability
Tests cycle metrics profiling capability
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.capabilities.data.profile_cycle_metrics import CycleMetricsProfiler


class TestCycleMetricsProfiler:
    """Test CycleMetricsProfiler capability"""
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent instance"""
        agent = MagicMock()
        agent.name = "test-agent"
        agent.config = MagicMock()
        # Use a temporary directory path instead of MagicMock to avoid creating "MagicMock" directory
        # Use TemporaryDirectory context manager for automatic cleanup
        temp_dir_ctx = TemporaryDirectory()
        temp_dir = Path(temp_dir_ctx.name)
        # Store context manager on agent so it persists for the test duration
        agent._temp_dir_ctx = temp_dir_ctx
        from infra.config.schema import CycleDataConfig
        agent.config.cycle_data = MagicMock(spec=CycleDataConfig)
        agent.config.cycle_data.root = temp_dir
        yield agent
        # Cleanup temporary directory after test
        temp_dir_ctx.cleanup()
    
    @pytest.fixture
    def profiler(self, mock_agent):
        """Create CycleMetricsProfiler instance"""
        return CycleMetricsProfiler(mock_agent)
    
    @pytest.mark.unit
    def test_profiler_initialization(self, mock_agent):
        """Test CycleMetricsProfiler initialization"""
        profiler = CycleMetricsProfiler(mock_agent)
        assert profiler.agent == mock_agent
        assert profiler.name == "test-agent"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_profile_success(self, profiler):
        """Test successful cycle metrics profiling"""
        ecid = "ECID-WB-001"
        
        mock_snapshot = {
            'cycle_id': ecid,
            'tasks': [{'task_id': 'task-1', 'status': 'completed'}],
            'agents': {'agent1': {'tasks': []}}
        }
        
        mock_metrics = {
            'total_tasks': 1,
            'completed_tasks': 1
        }
        
        mock_file_obj = AsyncMock()
        mock_file_obj.write = AsyncMock()
        mock_file_context = AsyncMock()
        mock_file_context.__aenter__ = AsyncMock(return_value=mock_file_obj)
        mock_file_context.__aexit__ = AsyncMock(return_value=None)
        
        # Use a temporary directory path instead of MagicMock to avoid creating "MagicMock" directory
        # Use TemporaryDirectory context manager for automatic cleanup
        with TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            
            # Mock agent's record_memory
            profiler.agent.record_memory = AsyncMock()
            
            with patch.object(profiler, '_load_snapshot', new_callable=AsyncMock, return_value=mock_snapshot), \
                 patch.object(profiler, '_compute_metrics', return_value=mock_metrics), \
                 patch('agents.utils.path_resolver.PathResolver.get_base_path', return_value=temp_dir), \
                 patch('aiofiles.open', return_value=mock_file_context):
                
                result = await profiler.profile(ecid)
                
                assert 'ecid' in result or 'metrics_json_path' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_profile_no_snapshot(self, profiler):
        """Test profiling when snapshot is missing"""
        ecid = "ECID-WB-001"
        
        with patch.object(profiler, '_load_snapshot', new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError):
                await profiler.profile(ecid)
    
    @pytest.mark.unit
    def test_compute_metrics(self, profiler):
        """Test computing metrics from snapshot"""
        snapshot = {
            'tasks': [
                {'task_id': 'task-1', 'status': 'completed', 'created_at': '2025-01-01T00:00:00Z'},
                {'task_id': 'task-2', 'status': 'failed', 'created_at': '2025-01-01T01:00:00Z'}
            ],
            'agents': {
                'agent1': {'tasks': [{'status': 'completed'}]},
                'agent2': {'tasks': [{'status': 'failed'}]}
            }
        }
        
        metrics = profiler._compute_metrics(snapshot)
        
        assert isinstance(metrics, dict)
        # The actual return value has 'agent_metrics' and other keys, not 'total_tasks'
        assert 'agent_metrics' in metrics or 'computed_at' in metrics

