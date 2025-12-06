#!/usr/bin/env python3
"""
Unit tests for WrapupGenerator capability
Tests wrap-up report generation
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.capabilities.wrapup_generator import WrapupGenerator


class TestWrapupGenerator:
    """Test WrapupGenerator capability"""
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent instance"""
        agent = MagicMock()
        agent.name = "test-agent"
        agent.communication_log = []
        agent.config = MagicMock()
        # Use a temporary directory path instead of MagicMock to avoid creating "MagicMock" directory
        # Use TemporaryDirectory context manager for automatic cleanup
        temp_dir_ctx = TemporaryDirectory()
        temp_dir = Path(temp_dir_ctx.name)
        # Store context manager on agent so it persists for the test duration
        agent._temp_dir_ctx = temp_dir_ctx
        agent.config.get_cycle_data_root = MagicMock(return_value=temp_dir)
        yield agent
        # Cleanup temporary directory after test
        temp_dir_ctx.cleanup()
    
    @pytest.fixture
    def generator(self, mock_agent):
        """Create WrapupGenerator instance"""
        return WrapupGenerator(mock_agent)
    
    @pytest.mark.unit
    def test_generator_initialization(self, mock_agent):
        """Test WrapupGenerator initialization"""
        generator = WrapupGenerator(mock_agent)
        assert generator.agent == mock_agent
        assert generator.name == "test-agent"
        assert generator.communication_log == []
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_wrapup_from_task_dict(self, generator, mock_agent):
        """Test generating wrapup from task dictionary"""
        task = {
            'cycle_id': 'ECID-WB-001',
            'task_id': 'task-001',
            'completion_payload': {'status': 'completed'},
            'telemetry': {'duration': 100},
            'reasoning_events': [{'reason_step': 'decision', 'summary': 'Test'}]
        }
        
        with patch.object(generator, 'generate_wrapup_markdown', new_callable=AsyncMock, return_value='# Wrap-up'), \
             patch('agents.cycle_data.CycleDataStore') as mock_cycle_store_class:
            mock_cycle_store = MagicMock()
            mock_cycle_store.write_text_artifact = MagicMock(return_value=True)
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=MagicMock() / 'artifacts' / 'warmboot-run001-wrapup.md')
            mock_cycle_store.get_cycle_path.return_value = mock_path
            mock_cycle_store_class.return_value = mock_cycle_store
            
            result = await generator.generate_wrapup(task=task)
            
            assert 'wrapup_uri' in result
            assert 'wrapup_content' in result
            mock_cycle_store.write_text_artifact.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_wrapup_from_parameters(self, generator, mock_agent):
        """Test generating wrapup from individual parameters"""
        with patch.object(generator, 'generate_wrapup_markdown', new_callable=AsyncMock, return_value='# Wrap-up'):
            result = await generator.generate_wrapup(
                cycle_id='CYCLE-WB-001',
                task_id='task-001',
                completion_payload={'status': 'completed'}
            )
            
            assert 'wrapup_uri' in result
            assert 'wrapup_content' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_wrapup_missing_cycle_id(self, generator):
        """Test generating wrapup when cycle_id is missing"""
        result = await generator.generate_wrapup(task_id='task-001')
        
        assert result['wrapup_uri'] is None
        assert 'error' in result
        assert 'cycle_id and task_id are required' in result['error']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_wrapup_write_failure(self, generator, mock_agent):
        """Test generating wrapup when file write fails"""
        with patch.object(generator, 'generate_wrapup_markdown', new_callable=AsyncMock, return_value='# Wrap-up'), \
             patch('agents.cycle_data.CycleDataStore') as mock_cycle_store_class:
            mock_cycle_store = MagicMock()
            mock_cycle_store.write_text_artifact = MagicMock(return_value=False)
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=MagicMock() / 'artifacts' / 'warmboot-run001-wrapup.md')
            mock_cycle_store.get_cycle_path.return_value = mock_path
            mock_cycle_store_class.return_value = mock_cycle_store
            
            result = await generator.generate_wrapup(
                cycle_id='CYCLE-WB-001',
                task_id='task-001'
            )
            
            assert result['wrapup_uri'] is None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_wrapup_markdown(self, generator):
        """Test generating wrapup markdown content"""
        cycle_id = 'CYCLE-WB-001'
        run_number = '001'
        task_id = 'task-001'
        completion_payload = {'status': 'completed'}
        telemetry_data = {'duration': 100}
        reasoning_events = [{'reason_step': 'decision', 'summary': 'Test'}]
        
        markdown = await generator.generate_wrapup_markdown(
            cycle_id, run_number, task_id, completion_payload, telemetry_data, reasoning_events
        )
        
        assert 'WarmBoot' in markdown
        assert cycle_id in markdown
        assert run_number in markdown
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_wrapup_markdown_no_reasoning_events(self, generator):
        """Test generating wrapup markdown without reasoning events"""
        markdown = await generator.generate_wrapup_markdown(
            'CYCLE-WB-001', '001', 'task-001', {}, {}, None
        )
        
        assert 'WarmBoot' in markdown
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_wrapup_exception_handling(self, generator):
        """Test generating wrapup exception handling"""
        with patch.object(generator, 'generate_wrapup_markdown', new_callable=AsyncMock, side_effect=Exception("Error")):
            result = await generator.generate_wrapup(
                cycle_id='CYCLE-WB-001',
                task_id='task-001'
            )
            
            assert result['wrapup_uri'] is None
            assert 'error' in result

