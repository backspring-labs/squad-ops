#!/usr/bin/env python3
"""
Unit tests for BuildRequirementsGenerator capability
Tests build requirements generation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.capabilities.build_requirements_generator import BuildRequirementsGenerator


class TestBuildRequirementsGenerator:
    """Test BuildRequirementsGenerator capability"""
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent instance"""
        agent = MagicMock()
        agent.name = "test-agent"
        agent.llm_client = MagicMock()
        agent.communication_log = []
        return agent
    
    @pytest.fixture
    def generator(self, mock_agent):
        """Create BuildRequirementsGenerator instance"""
        return BuildRequirementsGenerator(mock_agent)
    
    @pytest.mark.unit
    def test_generator_initialization(self, mock_agent):
        """Test BuildRequirementsGenerator initialization"""
        generator = BuildRequirementsGenerator(mock_agent)
        assert generator.agent == mock_agent
        assert generator.name == "test-agent"
        assert generator.llm_client == mock_agent.llm_client
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_success(self, generator, mock_agent):
        """Test generating build requirements successfully"""
        prd_content = "Test PRD content"
        app_name = "TestApp"
        version = "1.0.0"
        run_id = "run-001"
        
        mock_yaml_response = """
app_name: TestApp
version: 1.0.0
run_id: run-001
prd_analysis: Test analysis
features:
  - feature1
  - feature2
constraints:
  framework: vanilla_js
success_criteria:
  - Deploy successfully
"""
        
        mock_agent.llm_client.complete = AsyncMock(return_value=mock_yaml_response)
        
        with patch.object(generator.build_requirements_prompt_skill, 'load', return_value='test prompt'):
            result = await generator.generate(prd_content, app_name, version, run_id)
            
            assert result['app_name'] == app_name
            assert result['version'] == version
            assert 'features' in result
            assert 'constraints' in result
            assert 'success_criteria' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_no_llm_client(self, generator, mock_agent):
        """Test generating requirements when LLM client not available"""
        generator.llm_client = None
        
        result = await generator.generate("PRD", "TestApp", "1.0.0", "run-001")
        
        # Should return fallback dict
        assert result['app_name'] == "TestApp"
        assert 'prd_analysis' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_with_features(self, generator, mock_agent):
        """Test generating requirements with features"""
        mock_yaml_response = """
app_name: TestApp
version: 1.0.0
run_id: run-001
prd_analysis: Test
features:
  - feature1
constraints: {}
success_criteria: []
"""
        
        mock_agent.llm_client.complete = AsyncMock(return_value=mock_yaml_response)
        
        with patch.object(generator.build_requirements_prompt_skill, 'load', return_value='prompt'):
            result = await generator.generate("PRD", "TestApp", "1.0.0", "run-001", features=['feature1'])
            
            assert 'features' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_llm_error(self, generator, mock_agent):
        """Test generating requirements when LLM call fails"""
        mock_agent.llm_client.complete = AsyncMock(side_effect=Exception("LLM error"))
        
        with patch.object(generator.build_requirements_prompt_skill, 'load', return_value='prompt'):
            result = await generator.generate("PRD", "TestApp", "1.0.0", "run-001")
            
            # Should return fallback dict
            assert result['app_name'] == "TestApp"
            assert 'error' in result['prd_analysis'] or 'failed' in result['prd_analysis'].lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_invalid_yaml(self, generator, mock_agent):
        """Test generating requirements when LLM returns invalid YAML"""
        mock_agent.llm_client.complete = AsyncMock(return_value="Not valid YAML")
        
        with patch.object(generator.build_requirements_prompt_skill, 'load', return_value='prompt'):
            with patch('agents.llm.validators.clean_yaml_response', return_value="Not valid YAML"):
                result = await generator.generate("PRD", "TestApp", "1.0.0", "run-001")
                
                # Should return fallback dict with defaults
                assert result['app_name'] == "TestApp"
                assert result['version'] == "1.0.0"
                assert isinstance(result['features'], list)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_logs_to_communication_log(self, generator, mock_agent):
        """Test that generation logs to communication_log"""
        mock_yaml_response = "app_name: TestApp\nversion: 1.0.0"
        mock_agent.llm_client.complete = AsyncMock(return_value=mock_yaml_response)
        
        with patch.object(generator.build_requirements_prompt_skill, 'load', return_value='prompt'):
            await generator.generate("PRD", "TestApp", "1.0.0", "run-001")
            
            assert len(mock_agent.communication_log) == 1
            assert mock_agent.communication_log[0]['message_type'] == 'build_requirements_generation'

