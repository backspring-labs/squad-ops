"""
SquadOps Constraints Skill

Skill: SquadOps platform constraints and requirements.
According to SIP-040, this is a deterministic reasoning pattern with no side effects.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SquadOpsConstraints:
    """
    Skill: SquadOps platform constraints
    
    Loads and formats the squadops_constraints.txt template.
    This is a pure function - deterministic, no side effects.
    """
    
    def __init__(self):
        """Initialize the skill with template path"""
        self.template_path = Path(__file__).parent / 'prompts' / 'squadops_constraints.txt'
    
    def load(self, **kwargs) -> str:
        """
        Load and format the SquadOps constraints template.
        
        Args:
            **kwargs: Template variables:
                - version: Application version
                - run_id: Run identifier
                - app_name_kebab: Application name in kebab-case
        
        Returns:
            Formatted constraints string
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
            logger.error(f"SquadOpsConstraints failed to format template: {e}")
            if template_content:
                logger.error(f"SquadOpsConstraints template preview: {template_content[:200]}...")
            logger.error(f"SquadOpsConstraints safe kwargs: {safe_kwargs}")
            raise

