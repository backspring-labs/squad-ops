"""
Unit tests for ValidateAcceptanceCriteria capability
Tests product.validate_acceptance_criteria capability
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.capabilities.product.validate_acceptance_criteria import ValidateAcceptanceCriteria


class TestValidateAcceptanceCriteria:
    """Test ValidateAcceptanceCriteria capability"""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_success(self):
        """Test successful criteria validation"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.read_file = AsyncMock(return_value="""
# PRD
## Success Criteria
- Application displays version information
- Clean, professional appearance
""")
        mock_agent.record_memory = AsyncMock()  # Mock as AsyncMock for await
        
        capability = ValidateAcceptanceCriteria(mock_agent)
        
        # Mock the compare skill - patch where it's imported
        with patch('agents.skills.qa.compare_app_output_to_criteria.CompareAppOutputToCriteria') as mock_compare_class:
            mock_compare = MagicMock()
            mock_compare.compare = AsyncMock(return_value={
                'criteria_met': [
                    {'criterion_id': 'criteria_001', 'description': 'Application displays version information'}
                ],
                'criteria_unmet': [],
                'criteria_partial': []
            })
            mock_compare_class.return_value = mock_compare
            
            result = await capability.validate(
                prd_path="/test/prd.md",
                app_url="http://localhost:8080/test"
            )
            
            assert 'criteria_met' in result
            assert 'criteria_unmet' in result
            assert 'criteria_partial' in result
            assert 'validation_score' in result
            assert 'details' in result
            assert 0.0 <= result['validation_score'] <= 1.0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_no_criteria(self):
        """Test handling PRD with no criteria"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.read_file = AsyncMock(return_value="# PRD\n## Features\n- Feature 1")
        
        capability = ValidateAcceptanceCriteria(mock_agent)
        
        result = await capability.validate(
            prd_path="/test/prd.md",
            app_url="http://localhost:8080/test"
        )
        
        assert result['validation_score'] == 0.0
        assert len(result['criteria_met']) == 0
        assert result['details']['total_criteria'] == 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_partial_match(self):
        """Test validation with partial matches"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.read_file = AsyncMock(return_value="""
# PRD
## Success Criteria
- Application displays version information
- Shows build timestamp
""")
        mock_agent.record_memory = AsyncMock()  # Mock as AsyncMock for await
        
        capability = ValidateAcceptanceCriteria(mock_agent)
        
        with patch('agents.skills.qa.compare_app_output_to_criteria.CompareAppOutputToCriteria') as mock_compare_class:
            mock_compare = MagicMock()
            mock_compare.compare = AsyncMock(return_value={
                'criteria_met': [
                    {'criterion_id': 'criteria_001', 'description': 'Application displays version information'}
                ],
                'criteria_unmet': [],
                'criteria_partial': [
                    {'criterion_id': 'criteria_002', 'description': 'Shows build timestamp', 'match_score': 0.8}
                ]
            })
            mock_compare_class.return_value = mock_compare
            
            result = await capability.validate(
                prd_path="/test/prd.md",
                app_url="http://localhost:8080/test"
            )
            
            assert len(result['criteria_partial']) > 0
            # Score should account for partial matches (half credit)
            assert result['validation_score'] > 0.5
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_default_app_url(self):
        """Test using default app URL"""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.read_file = AsyncMock(return_value="# PRD\n## Success Criteria\n- Test")
        mock_agent.record_memory = AsyncMock()  # Mock as AsyncMock for await
        
        capability = ValidateAcceptanceCriteria(mock_agent)
        
        with patch('agents.skills.qa.compare_app_output_to_criteria.CompareAppOutputToCriteria') as mock_compare_class:
            mock_compare = MagicMock()
            mock_compare.compare = AsyncMock(return_value={
                'criteria_met': [],
                'criteria_unmet': [],
                'criteria_partial': []
            })
            mock_compare_class.return_value = mock_compare
            
            result = await capability.validate(prd_path="/test/prd.md")
            
            assert result['details']['app_url'] == "http://localhost:8080/hello-squad/"

