#!/usr/bin/env python3
"""
Unit tests for ManifestGenerator capability
Tests manifest generation capability
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.capabilities.manifest_generator import ManifestGenerator


class TestManifestGenerator:
    """Test ManifestGenerator capability"""
    
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
    def manifest_generator(self, mock_agent):
        """Create ManifestGenerator instance"""
        return ManifestGenerator(mock_agent)
    
    @pytest.mark.unit
    def test_manifest_generator_initialization(self, mock_agent):
        """Test ManifestGenerator initialization"""
        generator = ManifestGenerator(mock_agent)
        assert generator.agent == mock_agent
        assert generator.name == "test-agent"
        assert generator.architect_prompt_skill is not None
        assert generator.squadops_constraints_skill is not None
        assert generator.app_builder is not None
        assert generator.file_manager is not None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_success(self, manifest_generator, mock_agent):
        """Test successful manifest generation"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'features': ['feature1', 'feature2'],
            'prd_analysis': 'Test analysis',
            'constraints': {},
            'success_criteria': ['Deploy successfully'],
            'cycle_id': 'ec-001',
            'target_directory': '/test/target'
        }
        
        mock_manifest = {
            'architecture_type': 'spa_web_app',
            'files': [
                {'path': 'index.html', 'type': 'html'},
                {'path': 'script.js', 'type': 'javascript'}
            ]
        }
        
        mock_files = [
            {'type': 'create_file', 'file_path': 'index.html', 'content': '<html></html>', 'directory': '/test/target'}
        ]
        
        with patch.object(manifest_generator.architect_prompt_skill, 'load', return_value='architect prompt'), \
             patch.object(manifest_generator.squadops_constraints_skill, 'load', return_value='constraints'), \
             patch.object(manifest_generator.app_builder, 'generate_manifest_json', new_callable=AsyncMock, return_value=mock_manifest), \
             patch.object(manifest_generator.app_builder, 'generate_files_json', new_callable=AsyncMock, return_value=mock_files), \
             patch.object(manifest_generator.file_manager, 'create_file', new_callable=AsyncMock) as mock_create:
            
            mock_create.return_value = {'status': 'success'}
            
            result = await manifest_generator.generate('task-001', requirements)
            
            assert result['status'] == 'completed'
            assert result['action'] == 'design_manifest'
            assert result['architecture_type'] == 'spa_web_app'
            assert 'created_files' in result
            mock_create.assert_called()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_with_string_features(self, manifest_generator):
        """Test manifest generation with string features"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'features': ['feature1', 'feature2'],
            'cycle_id': 'ec-001'
        }
        
        mock_manifest = {'architecture_type': 'spa_web_app', 'files': []}
        
        with patch.object(manifest_generator.architect_prompt_skill, 'load', return_value='prompt'), \
             patch.object(manifest_generator.squadops_constraints_skill, 'load', return_value='constraints'), \
             patch.object(manifest_generator.app_builder, 'generate_manifest_json', new_callable=AsyncMock, return_value=mock_manifest), \
             patch.object(manifest_generator.app_builder, 'generate_files_json', new_callable=AsyncMock, return_value=[]), \
             patch.object(manifest_generator.file_manager, 'create_file', new_callable=AsyncMock, return_value={'status': 'success'}):
            
            result = await manifest_generator.generate('task-001', requirements)
            
            assert result['status'] == 'completed'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_with_dict_features(self, manifest_generator):
        """Test manifest generation with dict features"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'features': [{'name': 'feature1'}, {'description': 'feature2'}],
            'cycle_id': 'ec-001'
        }
        
        mock_manifest = {'architecture_type': 'spa_web_app', 'files': []}
        
        with patch.object(manifest_generator.architect_prompt_skill, 'load', return_value='prompt'), \
             patch.object(manifest_generator.squadops_constraints_skill, 'load', return_value='constraints'), \
             patch.object(manifest_generator.app_builder, 'generate_manifest_json', new_callable=AsyncMock, return_value=mock_manifest), \
             patch.object(manifest_generator.app_builder, 'generate_files_json', new_callable=AsyncMock, return_value=[]), \
             patch.object(manifest_generator.file_manager, 'create_file', new_callable=AsyncMock, return_value={'status': 'success'}):
            
            result = await manifest_generator.generate('task-001', requirements)
            
            assert result['status'] == 'completed'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_file_creation_failure(self, manifest_generator):
        """Test manifest generation when file creation fails"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'features': [],
            'cycle_id': 'ec-001'
        }
        
        mock_manifest = {'architecture_type': 'spa_web_app', 'files': []}
        mock_files = [
            {'type': 'create_file', 'file_path': 'test.txt', 'content': 'content', 'directory': '/test'}
        ]
        
        with patch.object(manifest_generator.architect_prompt_skill, 'load', return_value='prompt'), \
             patch.object(manifest_generator.squadops_constraints_skill, 'load', return_value='constraints'), \
             patch.object(manifest_generator.app_builder, 'generate_manifest_json', new_callable=AsyncMock, return_value=mock_manifest), \
             patch.object(manifest_generator.app_builder, 'generate_files_json', new_callable=AsyncMock, return_value=mock_files), \
             patch.object(manifest_generator.file_manager, 'create_file', new_callable=AsyncMock, return_value={'status': 'error', 'error': 'Failed'}):
            
            result = await manifest_generator.generate('task-001', requirements)
            
            # Should still complete, but file creation failure is logged
            assert result['status'] == 'completed'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_exception_handling(self, manifest_generator):
        """Test manifest generation exception handling"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'features': []
        }
        
        with patch.object(manifest_generator.architect_prompt_skill, 'load', side_effect=Exception("Unexpected error")):
            result = await manifest_generator.generate('task-001', requirements)
            
            assert result['status'] == 'error'
            assert 'error' in result

