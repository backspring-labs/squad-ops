#!/usr/bin/env python3
"""
Build Requirements Generator Capability Handler
Implements build.requirements.generate capability for generating build requirements from PRD content.
"""

import logging
import yaml
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class BuildRequirementsGenerator:
    """
    Build Requirements Generator - Implements build.requirements.generate capability
    
    Generates comprehensive build requirements from PRD content using LLM,
    including features, constraints, and success criteria.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize BuildRequirementsGenerator with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        self.llm_client = agent_instance.llm_client if hasattr(agent_instance, 'llm_client') else None
        self.communication_log = agent_instance.communication_log if hasattr(agent_instance, 'communication_log') else []
        
        # Import Skill (reasoning pattern)
        from agents.skills.lead.build_requirements_prompt import BuildRequirementsPrompt
        
        # Initialize Skill
        self.build_requirements_prompt_skill = BuildRequirementsPrompt()
    
    async def generate(self, prd_content: str, app_name: str, version: str, run_id: str, features: List[str] = None) -> Dict[str, Any]:
        """
        Generate build requirements from PRD content using LLM.
        
        Implements the build.requirements.generate capability.
        
        Args:
            prd_content: PRD content to analyze
            app_name: Application name
            version: Application version
            run_id: Run ID (ECID)
            features: Optional list of features to include
            
        Returns:
            Dictionary containing build requirements with keys:
            - app_name
            - version
            - run_id
            - prd_analysis
            - features
            - constraints
            - success_criteria
        """
        logger.info(f"{self.name} generating build requirements for {app_name} v{version}")
        
        # Compose Skills: Load prompt using Skill
        prompt = self.build_requirements_prompt_skill.load(
            app_name=app_name,
            version=version,
            run_id=run_id,
            features=features or [],
            prd_content=prd_content
        )
        
        try:
            if not self.llm_client:
                raise ValueError("LLM client not available")
            
            response = await self.llm_client.complete(
                prompt=prompt,
                temperature=0.5,  # Lower temp for structured output
                max_tokens=3000
            )
            
            # Clean and parse YAML response
            from agents.llm.validators import clean_yaml_response
            cleaned_response = clean_yaml_response(response)
            requirements = yaml.safe_load(cleaned_response)
            if not isinstance(requirements, dict):
                requirements = {}
            
            # Ensure required fields exist
            requirements.setdefault('app_name', app_name)
            requirements.setdefault('version', version)
            requirements.setdefault('run_id', run_id)
            requirements.setdefault('features', features or [])
            requirements.setdefault('constraints', {})
            requirements.setdefault('success_criteria', ["Application deploys successfully"])
            
            logger.info(f"{self.name} generated build requirements with {len(requirements.get('features', []))} features")
            
            # Log the requirements generation for telemetry
            self.communication_log.append({
                'timestamp': datetime.utcnow().isoformat(),
                'agent': self.name,
                'message_type': 'build_requirements_generation',
                'description': f"Generated build requirements for {app_name}: {response[:500]}...",
                'ecid': run_id,
                'full_response': response
            })
            
            return requirements
            
        except Exception as e:
            logger.error(f"{self.name} failed to generate build requirements: {e}")
            # Fallback to basic requirements dict
            return {
                'app_name': app_name,
                'version': version,
                'run_id': run_id,
                'prd_analysis': f"Basic analysis for {app_name} - Build requirements generation failed: {e}",
                'features': features or [],
                'constraints': {},
                'success_criteria': ["Application deploys successfully"]
            }

