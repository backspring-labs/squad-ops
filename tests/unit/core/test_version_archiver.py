#!/usr/bin/env python3
"""
Unit tests for VersionArchiver capability
Tests version archiving capability
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.capabilities.version_archiver import VersionArchiver


class TestVersionArchiver:
    """Test VersionArchiver capability"""
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent instance"""
        agent = MagicMock()
        agent.name = "test-agent"
        agent.llm_client = MagicMock()
        return agent
    
    @pytest.fixture
    def version_archiver(self, mock_agent):
        """Create VersionArchiver instance"""
        return VersionArchiver(mock_agent)
    
    @pytest.mark.unit
    def test_version_archiver_initialization(self, mock_agent):
        """Test VersionArchiver initialization"""
        archiver = VersionArchiver(mock_agent)
        assert archiver.agent == mock_agent
        assert archiver.name == "test-agent"
        assert archiver.version_manager is not None
        assert archiver.app_builder is not None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_archive_success(self, version_archiver):
        """Test successful version archiving"""
        requirements = {
            'application': 'TestApp',
            'version': '2.0.0',
            'source_dir': '/test/source'
        }
        
        with patch.object(version_archiver.version_manager, 'archive_existing_version', new_callable=AsyncMock) as mock_archive:
            mock_archive.return_value = {
                'status': 'success',
                'archived_version': '1.0.0',
                'archive_dir': '/test/archive'
            }
            
            result = await version_archiver.archive('task-001', requirements)
            
            assert result['status'] == 'completed'
            assert result['action'] == 'archive'
            assert result['app_name'] == 'TestApp'
            assert result['archived_version'] == '1.0.0'
            assert result['archive_dir'] == '/test/archive'
            mock_archive.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_archive_default_source_dir(self, version_archiver):
        """Test archiving with default source directory"""
        requirements = {
            'application': 'TestApp',
            'version': '2.0.0'
        }
        
        with patch.object(version_archiver.version_manager, 'archive_existing_version', new_callable=AsyncMock) as mock_archive:
            mock_archive.return_value = {
                'status': 'success',
                'archived_version': '1.0.0',
                'archive_dir': '/test/archive'
            }
            
            result = await version_archiver.archive('task-001', requirements)
            
            assert result['status'] == 'completed'
            # Should use default source directory
            call_args = mock_archive.call_args[0]
            assert call_args[0] == 'TestApp'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_archive_failure(self, version_archiver):
        """Test archiving when archive fails"""
        requirements = {
            'application': 'TestApp',
            'version': '2.0.0',
            'source_dir': '/test/source'
        }
        
        with patch.object(version_archiver.version_manager, 'archive_existing_version', new_callable=AsyncMock) as mock_archive:
            mock_archive.return_value = {
                'status': 'error',
                'error': 'Archive failed'
            }
            
            result = await version_archiver.archive('task-001', requirements)
            
            assert result['status'] == 'error'
            assert 'Archive failed' in result['error']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_archive_exception_handling(self, version_archiver):
        """Test archiving exception handling"""
        requirements = {
            'application': 'TestApp',
            'version': '2.0.0'
        }
        
        with patch.object(version_archiver.version_manager, 'archive_existing_version', new_callable=AsyncMock, side_effect=Exception("Unexpected error")):
            result = await version_archiver.archive('task-001', requirements)
            
            assert result['status'] == 'error'
            assert 'error' in result

