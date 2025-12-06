"""
Developer Prompt Skill

Skill: Developer reasoning pattern for generating application files.
According to SIP-040, this is a deterministic reasoning pattern with no side effects.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DeveloperPrompt:
    """
    Skill: Developer reasoning pattern
    
    Loads and formats the developer.txt template for LLM interactions.
    This is a pure function - deterministic, no side effects.
    """
    
    def __init__(self):
        """Initialize the skill with template path"""
        self.template_path = Path(__file__).parent / 'prompts' / 'developer.txt'
    
    def load(self, **kwargs) -> str:
        """
        Load and format the developer prompt template.
        
        Args:
            **kwargs: Template variables:
                - app_name: Application name
                - app_name_kebab: Application name in kebab-case
                - version: Application version
                - run_id: Run identifier
                - prd_analysis: PRD analysis content
                - features: List of features
                - constraints: Build constraints
                - manifest_summary: Architecture manifest summary
                - output_format: Output format (json or delimited)
                - squadops_constraints: SquadOps constraints (formatted string, injected via replace)
        
        Returns:
            Formatted prompt string (with $squadops_constraints placeholder if not provided)
        """
        template_content = None
        safe_kwargs = {}
        
        try:
            with open(self.template_path) as f:
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
            logger.error(f"DeveloperPrompt failed to format template: {e}")
            if template_content:
                logger.error(f"DeveloperPrompt template preview: {template_content[:200]}...")
            logger.error(f"DeveloperPrompt safe kwargs: {safe_kwargs}")
            raise

