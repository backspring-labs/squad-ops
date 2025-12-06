#!/usr/bin/env python3
"""
Unit tests for DockerBuilder capability
Tests Docker image building capability
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.capabilities.docker_builder import DockerBuilder


class TestDockerBuilder:
    """Test DockerBuilder capability"""
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent instance"""
        agent = MagicMock()
        agent.name = "test-agent"
        agent.llm_client = MagicMock()
        agent.current_ecid = "ec-001"
        agent.emit_reasoning_event = AsyncMock()
        agent.record_memory = AsyncMock()
        return agent
    
    @pytest.fixture
    def docker_builder(self, mock_agent):
        """Create DockerBuilder instance"""
        return DockerBuilder(mock_agent)
    
    @pytest.mark.unit
    def test_docker_builder_initialization(self, mock_agent):
        """Test DockerBuilder initialization"""
        builder = DockerBuilder(mock_agent)
        assert builder.agent == mock_agent
        assert builder.name == "test-agent"
        assert builder.docker_manager is not None
        assert builder.file_manager is not None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_build_success_with_existing_files(self, docker_builder, mock_agent):
        """Test building Docker image when files already exist"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'manifest': {'architecture_type': 'spa_web_app', 'files': []},
            'cycle_id': 'ec-001'
        }
        
        with patch.object(docker_builder.file_manager, 'directory_exists', new_callable=AsyncMock, return_value=True), \
             patch.object(docker_builder.file_manager, 'list_files', new_callable=AsyncMock, return_value=['file1.txt', 'file2.txt']), \
             patch.object(docker_builder.docker_manager, 'build_image', new_callable=AsyncMock) as mock_build:
            
            mock_build.return_value = {
                'status': 'success',
                'image_name': 'test-app',
                'version': '1.0.0'
            }
            
            result = await docker_builder.build('task-001', requirements)
            
            assert result['status'] == 'completed'
            assert result['action'] == 'build'
            assert result['app_name'] == 'TestApp'
            assert result['version'] == '1.0.0'
            mock_build.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_build_success_creates_files(self, docker_builder, mock_agent):
        """Test building Docker image when files need to be created"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'manifest': {'architecture_type': 'spa_web_app', 'files': []},
            'cycle_id': 'ec-001',
            'prd_analysis': 'Test analysis',
            'features': ['feature1'],
            'constraints': {},
            'success_criteria': ['Deploy successfully']
        }
        
        with patch.object(docker_builder.file_manager, 'directory_exists', new_callable=AsyncMock, return_value=False), \
             patch.object(docker_builder.file_manager, 'create_file', new_callable=AsyncMock) as mock_create, \
             patch('agents.tools.app_builder.AppBuilder') as mock_app_builder_class:
            
            mock_app_builder = MagicMock()
            mock_app_builder_class.return_value = mock_app_builder
            mock_app_builder.generate_files_json = AsyncMock(return_value=[
                {'type': 'create_file', 'file_path': 'index.html', 'content': '<html></html>', 'directory': '/test'}
            ])
            
            mock_create.return_value = {'status': 'success'}
            
            with patch.object(docker_builder.docker_manager, 'build_image', new_callable=AsyncMock) as mock_build:
                mock_build.return_value = {
                    'status': 'success',
                    'image_name': 'test-app',
                    'version': '1.0.0'
                }
                
                result = await docker_builder.build('task-001', requirements)
                
                assert result['status'] == 'completed'
                assert mock_create.called
                assert mock_build.called
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_build_missing_manifest(self, docker_builder):
        """Test building when manifest is missing"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0'
        }
        
        result = await docker_builder.build('task-001', requirements)
        
        assert result['status'] == 'error'
        assert 'Manifest is required' in result['error']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_build_empty_manifest(self, docker_builder):
        """Test building when manifest is empty"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'manifest': {}
        }
        
        result = await docker_builder.build('task-001', requirements)
        
        assert result['status'] == 'error'
        assert 'Manifest is required' in result['error']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_build_no_files_created(self, docker_builder):
        """Test building when no files are created"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'manifest': {'architecture_type': 'spa_web_app', 'files': []},
            'cycle_id': 'ec-001'
        }
        
        with patch.object(docker_builder.file_manager, 'directory_exists', new_callable=AsyncMock, return_value=False), \
             patch('agents.tools.app_builder.AppBuilder') as mock_app_builder_class:
            
            mock_app_builder = MagicMock()
            mock_app_builder_class.return_value = mock_app_builder
            mock_app_builder.generate_files_json = AsyncMock(return_value=[])
            
            result = await docker_builder.build('task-001', requirements)
            
            assert result['status'] == 'error'
            assert 'No files were created' in result['error']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_build_docker_build_fails(self, docker_builder):
        """Test building when Docker build fails"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'manifest': {'architecture_type': 'spa_web_app', 'files': []},
            'cycle_id': 'ec-001'
        }
        
        with patch.object(docker_builder.file_manager, 'directory_exists', new_callable=AsyncMock, return_value=True), \
             patch.object(docker_builder.file_manager, 'list_files', new_callable=AsyncMock, return_value=['file1.txt']), \
             patch.object(docker_builder.docker_manager, 'build_image', new_callable=AsyncMock) as mock_build:
            
            mock_build.return_value = {
                'status': 'error',
                'error': 'Docker build failed'
            }
            
            result = await docker_builder.build('task-001', requirements)
            
            assert result['status'] == 'error'
            assert 'Docker build failed' in result['error']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_build_exception_handling(self, docker_builder):
        """Test building exception handling"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'manifest': {'architecture_type': 'spa_web_app', 'files': []}
        }
        
        with patch.object(docker_builder.file_manager, 'directory_exists', new_callable=AsyncMock, side_effect=Exception("Unexpected error")):
            result = await docker_builder.build('task-001', requirements)
            
            assert result['status'] == 'error'
            assert 'error' in result

