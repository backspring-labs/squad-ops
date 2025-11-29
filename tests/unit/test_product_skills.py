"""
Unit tests for Product domain skills
Tests format_prd_prompt, parse_prd_acceptance_criteria, and text_match skills
"""

import pytest

from agents.skills.product.format_prd_prompt import FormatPRDPrompt
from agents.skills.product.parse_prd_acceptance_criteria import ParsePRDAcceptanceCriteria
from agents.skills.shared.text_match import TextMatch


class TestFormatPRDPrompt:
    """Test FormatPRDPrompt skill"""
    
    @pytest.mark.unit
    def test_format_prompt_basic(self):
        """Test basic prompt formatting"""
        formatter = FormatPRDPrompt()
        
        requirement = "Build a todo app"
        objective = "Help users manage tasks"
        app_name = "TodoApp"
        template_content = "# PRD Template\n{{APP_NAME}}\n{{PROBLEM}}\n{{SOLUTION}}"
        
        result = formatter.format_prompt(requirement, objective, app_name, template_content)
        
        assert isinstance(result, str)
        assert app_name in result
        assert requirement in result
        assert objective in result
        assert template_content in result
        assert "{{APP_NAME}}" in result or "TodoApp" in result
    
    @pytest.mark.unit
    def test_format_prompt_with_all_placeholders(self):
        """Test prompt formatting with all placeholders"""
        formatter = FormatPRDPrompt()
        
        requirement = "Create a dashboard"
        objective = "Monitor system health"
        app_name = "DashboardApp"
        template_content = """
# PRD Template
{{APP_NAME}}
{{PROBLEM}}
{{SOLUTION}}
{{CORE_FEATURES}}
{{SUCCESS_CRITERIA}}
{{TECHNICAL_REQUIREMENTS}}
{{DATA_SOURCES}}
{{ENV_VARS}}
{{DESIGN_GUIDELINES}}
"""
        
        result = formatter.format_prompt(requirement, objective, app_name, template_content)
        
        assert "{{APP_NAME}}" in result or app_name in result
        assert "{{PROBLEM}}" in result
        assert "{{SOLUTION}}" in result
        assert "{{CORE_FEATURES}}" in result
        assert "{{SUCCESS_CRITERIA}}" in result


class TestParsePRDAcceptanceCriteria:
    """Test ParsePRDAcceptanceCriteria skill"""
    
    @pytest.mark.unit
    def test_extract_criteria_bullet_points(self):
        """Test extracting criteria from bullet points"""
        parser = ParsePRDAcceptanceCriteria()
        
        prd_content = """
## 2. Functional Requirements

### Success Criteria
- Application loads and displays correctly
- Shows real version and build information
- Displays actual system data (not simulated)
- Clean, professional appearance
- No errors or broken functionality
"""
        
        criteria = parser.extract(prd_content)
        
        assert len(criteria) > 0
        assert all('criterion_id' in c for c in criteria)
        assert all('description' in c for c in criteria)
        assert all('type' in c for c in criteria)
        assert all('testable' in c for c in criteria)
        assert any('loads and displays' in c['description'].lower() for c in criteria)
    
    @pytest.mark.unit
    def test_extract_criteria_numbered_list(self):
        """Test extracting criteria from numbered list"""
        parser = ParsePRDAcceptanceCriteria()
        
        prd_content = """
### Success Criteria
1. Application must load quickly
2. Should display version information
3. Must show real system data
"""
        
        criteria = parser.extract(prd_content)
        
        assert len(criteria) >= 3
        assert all('criterion_id' in c for c in criteria)
    
    @pytest.mark.unit
    def test_extract_criteria_no_section(self):
        """Test handling PRD with no Success Criteria section"""
        parser = ParsePRDAcceptanceCriteria()
        
        prd_content = """
# PRD
## Features
- Feature 1
- Feature 2
"""
        
        criteria = parser.extract(prd_content)
        
        assert isinstance(criteria, list)
        assert len(criteria) == 0
    
    @pytest.mark.unit
    def test_criteria_type_classification(self):
        """Test criteria type classification"""
        parser = ParsePRDAcceptanceCriteria()
        
        prd_content = """
### Success Criteria
- Application loads quickly (performance requirement)
- Clean, modern design
- User can create tasks
"""
        
        criteria = parser.extract(prd_content)
        
        # Check that types are classified
        types = [c['type'] for c in criteria]
        assert 'functional' in types or 'technical' in types or 'design' in types


class TestTextMatch:
    """Test TextMatch shared skill"""
    
    @pytest.mark.unit
    def test_match_exact_phrase(self):
        """Test exact phrase matching"""
        matcher = TextMatch()
        
        text = "The application displays version information correctly"
        pattern = "displays version information"
        
        result = matcher.match(text, pattern, threshold=0.7)
        
        assert result['matched'] is True
        assert result['match_score'] >= 0.7
    
    @pytest.mark.unit
    def test_match_partial_keywords(self):
        """Test partial keyword matching"""
        matcher = TextMatch()
        
        text = "The application shows build info and version data"
        pattern = "displays version information"
        
        result = matcher.match(text, pattern, threshold=0.5)
        
        assert 'match_score' in result
        assert 'matched' in result
        # Should match because "version" is in both
    
    @pytest.mark.unit
    def test_match_no_match(self):
        """Test when pattern doesn't match"""
        matcher = TextMatch()
        
        text = "The application shows build info"
        pattern = "user authentication and login"
        
        result = matcher.match(text, pattern, threshold=0.7)
        
        assert result['matched'] is False
        assert result['match_score'] < 0.7
    
    @pytest.mark.unit
    def test_match_empty_pattern(self):
        """Test matching with empty pattern"""
        matcher = TextMatch()
        
        text = "Some text content"
        pattern = ""
        
        result = matcher.match(text, pattern, threshold=0.7)
        
        # Empty pattern should match everything
        assert result['matched'] is True
        assert result['match_score'] == 1.0
    
    @pytest.mark.unit
    def test_match_threshold_adjustment(self):
        """Test threshold adjustment affects matching"""
        matcher = TextMatch()
        
        text = "The application shows some version data"
        pattern = "displays version information correctly"
        
        result_low = matcher.match(text, pattern, threshold=0.3)
        result_high = matcher.match(text, pattern, threshold=0.9)
        
        # Lower threshold should be more lenient
        assert result_low['match_score'] >= result_high['match_score']

