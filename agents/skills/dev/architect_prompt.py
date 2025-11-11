"""
Architect Prompt Skill

Skill: Architecture reasoning pattern for generating build manifests.
According to SIP-040, this is a deterministic reasoning pattern with no side effects.
"""

from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ArchitectPrompt:
    """
    Skill: Architecture reasoning pattern
    
    Loads and formats the architect.txt template for LLM interactions.
    This is a pure function - deterministic, no side effects.
    """
    
    def __init__(self):
        """Initialize the skill with template path"""
        self.template_path = Path(__file__).parent / 'prompts' / 'architect.txt'
    
    def load(self, **kwargs) -> str:
        """
        Load and format the architect prompt template.
        
        Args:
            **kwargs: Template variables:
                - app_name: Application name
                - version: Application version
                - prd_analysis: PRD analysis content
                - features: List of features
                - constraints: Build constraints
                - squadops_constraints: SquadOps constraints (formatted string)
                - output_format: Output format (json or yaml)
        
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
                else:
                    safe_kwargs[key] = str(value).replace('$', '$$')
            
            return template.safe_substitute(**safe_kwargs)
            
        except Exception as e:
            logger.error(f"ArchitectPrompt failed to format template: {e}")
            if template_content:
                logger.error(f"ArchitectPrompt template preview: {template_content[:200]}...")
            logger.error(f"ArchitectPrompt safe kwargs: {safe_kwargs}")
            raise

