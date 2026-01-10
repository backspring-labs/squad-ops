#!/usr/bin/env python3
"""
Format PRD Prompt Skill
Formats prompt for LLM to generate PRD content from requirement/objective using template.
"""

import logging

logger = logging.getLogger(__name__)


class FormatPRDPrompt:
    """
    Format PRD Prompt - Product domain skill
    
    Formats prompt that instructs LLM to fill template placeholders.
    Deterministic skill (prompt formatting only).
    """
    
    def format_prompt(self, requirement: str, objective: str, app_name: str, template_content: str) -> str:
        """
        Format prompt that instructs LLM to generate PRD content by filling template placeholders.
        
        Args:
            requirement: User requirement/request
            objective: Objective or goal for the application
            app_name: Application name
            template_content: PRD template content with placeholders
            
        Returns:
            Formatted prompt string for LLM
        """
        prompt = f"""You are a product strategist drafting a Product Requirements Document (PRD).

Application Name: {app_name}
Requirement: {requirement}
Objective: {objective}

Below is a PRD template with placeholders marked as {{PLACEHOLDER}}. Your task is to fill in all placeholders with appropriate content based on the requirement and objective.

PRD Template:
{template_content}

Instructions:
1. Replace all {{PLACEHOLDER}} markers with appropriate content
2. For {{APP_NAME}}, use: {app_name}
3. For {{PROBLEM}}, describe the problem this application solves based on the requirement
4. For {{SOLUTION}}, describe how the application solves the problem
5. For {{CORE_FEATURES}}, list the main features as a numbered list
6. For {{SUCCESS_CRITERIA}}, list measurable success criteria as bullet points
7. For {{TECHNICAL_REQUIREMENTS}}, describe performance, scalability, and technical constraints
8. For {{DATA_SOURCES}}, list data sources and APIs if applicable
9. For {{ENV_VARS}}, list environment variables needed
10. For {{DESIGN_GUIDELINES}}, describe visual style and content structure guidelines

Generate a complete PRD by filling in all placeholders. Maintain the template structure, headers, and formatting. Return only the filled PRD, no additional commentary."""
        
        return prompt

