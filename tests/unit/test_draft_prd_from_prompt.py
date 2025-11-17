"""
Unit tests for DraftPRDFromPrompt capability
Tests product.draft_prd_from_prompt capability
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.capabilities.product.draft_prd_from_prompt import DraftPRDFromPrompt


class TestDraftPRDFromPrompt:
    """Test DraftPRDFromPrompt capability"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_draft_prd_success(self):
        """Test successful PRD drafting"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.read_file = AsyncMock(return_value="# PRD Template\n{{APP_NAME}}\n{{PROBLEM}}")
        mock_agent.write_file = AsyncMock()
        mock_agent.record_memory = AsyncMock()  # Mock as AsyncMock for await
        mock_agent.llm_client = MagicMock()
        mock_agent.llm_client.complete = AsyncMock(return_value={
            'response': '# PRD\nTestApp\nTest Problem\nTest Solution'
        })
        
        capability = DraftPRDFromPrompt(mock_agent)
        
        result = await capability.draft(
            requirement="Build a todo app",
            objective="Help users manage tasks",
            app_name="TodoApp"
        )
        
        assert 'prd_content' in result
        assert 'prd_path' in result
        assert 'sections_generated' in result
        assert mock_agent.read_file.called
        assert mock_agent.write_file.called
        assert mock_agent.llm_client.complete.called
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_draft_prd_llm_empty_response(self):
        """Test handling empty LLM response"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.read_file = AsyncMock(return_value="# PRD Template\n{{APP_NAME}}")
        mock_agent.llm_client = MagicMock()
        mock_agent.llm_client.complete = AsyncMock(return_value={'response': ''})
        
        capability = DraftPRDFromPrompt(mock_agent)
        
        with pytest.raises(ValueError, match="empty PRD content"):
            await capability.draft(
                requirement="Build app",
                objective="Test",
                app_name="TestApp"
            )
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_draft_prd_no_llm_client(self):
        """Test handling missing LLM client"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.read_file = AsyncMock(return_value="# PRD Template")
        mock_agent.llm_client = None
        
        capability = DraftPRDFromPrompt(mock_agent)
        
        with pytest.raises(ValueError, match="LLM client not initialized"):
            await capability.draft(
                requirement="Build app",
                objective="Test",
                app_name="TestApp"
            )
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_draft_prd_path_generation(self):
        """Test PRD path generation"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.read_file = AsyncMock(return_value="# PRD Template")
        mock_agent.write_file = AsyncMock()
        mock_agent.record_memory = AsyncMock()  # Mock as AsyncMock for await
        mock_agent.llm_client = MagicMock()
        mock_agent.llm_client.complete = AsyncMock(return_value={
            'response': '# PRD\nTestApp'
        })
        
        capability = DraftPRDFromPrompt(mock_agent)
        
        result = await capability.draft(
            requirement="Build app",
            objective="Test",
            app_name="TestApp"
        )
        
        assert 'prd_path' in result
        assert result['prd_path'].endswith('.md')
        assert 'PRD-' in result['prd_path']
        assert 'TestApp' in result['prd_path']

