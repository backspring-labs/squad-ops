"""
Build Requirements Prompt Skill

Skill: Build requirements reasoning pattern for generating development requirements.
According to SIP-040, this is a deterministic reasoning pattern with no side effects.
"""

from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class BuildRequirementsPrompt:
    """
    Skill: Build requirements reasoning pattern
    
    Loads and formats the build_requirements.txt template for LLM interactions.
    This is a pure function - deterministic, no side effects.
    """
    
    def __init__(self):
        """Initialize the skill with template path"""
        self.template_path = Path(__file__).parent / 'prompts' / 'build_requirements.txt'
    
    def load(self, **kwargs) -> str:
        """
        Load and format the build requirements prompt template.
        
        Args:
            **kwargs: Template variables:
                - app_name: Application name
                - version: Application version
                - run_id: Run identifier
                - features: List of features (will be joined as comma-separated string)
                - prd_content: PRD content to analyze
        
        Returns:
            Formatted prompt string
        """
        template_content = None
        safe_kwargs = {}
        
        try:
            with open(self.template_path, 'r') as f:
                template_content = f.read()
            
            # Use string.Template for safer substitution
            from string import Template
            template = Template(template_content)
            
            # Convert kwargs to safe format for Template
            for key, value in kwargs.items():
                if isinstance(value, str):
                    # Escape $ signs to prevent template injection
                    safe_kwargs[key] = value.replace('$', '$$')
                elif isinstance(value, list):
                    # Join list items with commas
                    safe_kwargs[key] = ', '.join(str(v) for v in value).replace('$', '$$')
                else:
                    safe_kwargs[key] = str(value).replace('$', '$$')
            
            return template.safe_substitute(**safe_kwargs)
            
        except Exception as e:
            logger.error(f"BuildRequirementsPrompt failed to format template: {e}")
            if template_content:
                logger.error(f"BuildRequirementsPrompt template preview: {template_content[:200]}...")
            logger.error(f"BuildRequirementsPrompt safe kwargs: {safe_kwargs}")
            raise

