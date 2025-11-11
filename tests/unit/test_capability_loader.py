"""
Unit tests for CapabilityLoader class
Tests capability resolution and execution
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from agents.capabilities.loader import CapabilityLoader
from pathlib import Path


class TestCapabilityLoader:
    """Test CapabilityLoader core functionality"""
    
    @pytest.mark.unit
    def test_loader_initialization(self):
        """Test CapabilityLoader initialization"""
        loader = CapabilityLoader()
        
        assert loader.base_path is not None
        assert loader.catalog_path is not None
        assert loader.bindings_path is not None
        assert loader._class_cache == {}
    
    @pytest.mark.unit
    def test_resolve_capability(self):
        """Test capability resolution"""
        loader = CapabilityLoader()
        
        # Resolve task.create capability
        capability_class = loader.resolve('task.create')
        assert capability_class is not None
        assert capability_class.__name__ == 'TaskCreator'
        
        # Resolve prd.read capability
        capability_class = loader.resolve('prd.read')
        assert capability_class is not None
        assert capability_class.__name__ == 'PRDReader'
        
        # Resolve prd.analyze capability
        capability_class = loader.resolve('prd.analyze')
        assert capability_class is not None
        assert capability_class.__name__ == 'PRDAnalyzer'
        
        # Resolve build.artifact capability
        capability_class = loader.resolve('build.artifact')
        assert capability_class is not None
        assert capability_class.__name__ == 'BuildArtifact'
    
    @pytest.mark.unit
    def test_resolve_unknown_capability(self):
        """Test resolving unknown capability"""
        loader = CapabilityLoader()
        
        capability_class = loader.resolve('unknown.capability')
        assert capability_class is None
    
    @pytest.mark.unit
    def test_resolve_caching(self):
        """Test capability class caching"""
        loader = CapabilityLoader()
        
        # First resolve
        class1 = loader.resolve('task.create')
        assert class1 is not None
        
        # Second resolve should use cache
        class2 = loader.resolve('task.create')
        assert class2 is class1  # Same object from cache
        assert 'task.create' in loader._class_cache
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_capability(self):
        """Test capability execution"""
        loader = CapabilityLoader()
        
        # Mock agent instance
        mock_agent = MagicMock()
        mock_agent.name = 'test-agent'
        mock_agent.read_file = AsyncMock(return_value='Test PRD content')
        
        # Execute prd.read capability
        result = await loader.execute('prd.read', mock_agent, 'test-prd.md')
        
        assert result is not None
        assert 'prd_content' in result
        assert result['prd_content'] == 'Test PRD content'
        mock_agent.read_file.assert_called_once_with('test-prd.md')
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_unknown_capability(self):
        """Test executing unknown capability"""
        loader = CapabilityLoader()
        
        mock_agent = MagicMock()
        
        with pytest.raises(ValueError, match="could not be resolved"):
            await loader.execute('unknown.capability', mock_agent)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_with_kwargs(self):
        """Test capability execution with keyword arguments"""
        loader = CapabilityLoader()
        
        # Mock agent instance
        mock_agent = MagicMock()
        mock_agent.name = 'test-agent'
        mock_agent.llm_response = AsyncMock(return_value='{"core_features": ["Feature 1"]}')
        
        # Execute prd.analyze with agent_role kwarg
        prd_content = "Test PRD content"
        result = await loader.execute(
            'prd.analyze', 
            mock_agent, 
            prd_content, 
            agent_role="Test Agent"
        )
        
        assert result is not None
        mock_agent.llm_response.assert_called()
    
    @pytest.mark.unit
    def test_load_catalog(self):
        """Test loading capability catalog"""
        loader = CapabilityLoader()
        
        catalog = loader.load_catalog()
        
        assert catalog is not None
        assert len(catalog) > 0
        assert 'task.create' in catalog
        assert 'prd.read' in catalog
        assert 'prd.analyze' in catalog
    
    @pytest.mark.unit
    def test_load_bindings(self):
        """Test loading capability bindings"""
        loader = CapabilityLoader()
        
        bindings = loader.load_bindings()
        
        assert bindings is not None
        assert len(bindings) > 0
        assert 'task.create' in bindings or 'build.artifact' in bindings
    
    @pytest.mark.unit
    def test_get_agent_for_capability(self):
        """Test resolving capability to agent"""
        loader = CapabilityLoader()
        
        agent_id = loader.get_agent_for_capability('task.create')
        # May be None if not in bindings, but should not raise error
        assert agent_id is None or isinstance(agent_id, str)
    
    @pytest.mark.unit
    def test_validate_capability(self):
        """Test capability validation"""
        loader = CapabilityLoader()
        
        # Validate existing capability
        assert loader.validate_capability('task.create') is True
        assert loader.validate_capability('prd.read') is True
        assert loader.validate_capability('build.artifact') is True
        
        # Validate unknown capability
        assert loader.validate_capability('unknown.capability') is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_build_artifact_capability(self):
        """Test executing build.artifact capability"""
        loader = CapabilityLoader()
        
        # Mock agent instance
        mock_agent = MagicMock()
        mock_agent.name = 'test-dev-agent'
        mock_agent.llm_client = MagicMock()
        
        # Mock AppBuilder, DockerManager, and FileManager at their import locations
        with patch('agents.tools.app_builder.AppBuilder') as MockAppBuilder, \
             patch('agents.tools.docker_manager.DockerManager') as MockDockerManager, \
             patch('agents.tools.file_manager.FileManager') as MockFileManager:
            
            # Setup mocks
            mock_app_builder = MagicMock()
            mock_app_builder.generate_files_json = AsyncMock(return_value=[
                {"type": "create_file", "file_path": "index.html", "content": "<html></html>", "directory": None}
            ])
            MockAppBuilder.return_value = mock_app_builder
            
            mock_docker_manager = MagicMock()
            mock_docker_manager.build_image = AsyncMock(return_value={
                'status': 'success',
                'image_name': 'test-app',
                'image': 'test-app:1.0.0'
            })
            MockDockerManager.return_value = mock_docker_manager
            
            mock_file_manager = MagicMock()
            mock_file_manager.directory_exists = AsyncMock(return_value=False)
            mock_file_manager.create_file = AsyncMock(return_value={'status': 'success'})
            mock_file_manager.list_files = AsyncMock(return_value=['index.html'])
            MockFileManager.return_value = mock_file_manager
            
            # Execute build.artifact capability
            requirements = {
                'application': 'TestApp',
                'version': '1.0.0',
                'manifest': {
                    'architecture_type': 'spa_web_app',
                    'framework': 'vanilla_js'
                },
                'features': ['Feature 1'],
                'ecid': 'ECID-001'
            }
            
            result = await loader.execute('build.artifact', mock_agent, requirements)
            
            assert result is not None
            assert 'artifact_uri' in result
            assert 'files_generated' in result
            assert 'manifest_uri' in result
            assert result['manifest_uri'] == 'spa_web_app'

