#!/usr/bin/env python3
"""
Draft PRD From Prompt Capability
Drafts PRD from requirement/objective prompt using template structure.
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DraftPRDFromPrompt:
    """
    Draft PRD From Prompt - Product domain capability
    
    Drafts PRD from requirement/objective prompt using template structure.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize DraftPRDFromPrompt with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
    
    async def draft(self, requirement: str, objective: str, app_name: str) -> dict[str, Any]:
        """
        Draft PRD from requirement/objective prompt.
        
        Implements the product.draft_prd_from_prompt capability.
        
        Args:
            requirement: User requirement/request
            objective: Objective or goal for the application
            app_name: Application name
            
        Returns:
            Dictionary containing:
            - prd_content: Generated PRD markdown string
            - prd_path: Path where PRD was saved
            - sections_generated: List of sections that were filled
        """
        try:
            # Load PRD template
            template_path = Path("warm-boot/prd/PRD-template.md")
            template_content = await self.agent.read_file(str(template_path))
            
            logger.info(f"{self.name} loaded PRD template from {template_path}")
            
            # Import and use FormatPRDPrompt skill
            from agents.skills.product.format_prd_prompt import FormatPRDPrompt
            formatter = FormatPRDPrompt()
            prompt = formatter.format_prompt(requirement, objective, app_name, template_content)
            
            # Call LLM to generate PRD content
            if not hasattr(self.agent, 'llm_client') or not self.agent.llm_client:
                raise ValueError("LLM client not initialized")
            
            llm_result = await self.agent.llm_client.complete(
                prompt=prompt,
                temperature=0.7,
                max_tokens=4000
            )
            
            prd_content = llm_result.get('response', '') if isinstance(llm_result, dict) else str(llm_result)
            
            if not prd_content:
                raise ValueError("LLM returned empty PRD content")
            
            # Generate PRD file path
            # Use app_name to create filename, sanitize it
            safe_app_name = re.sub(r'[^a-zA-Z0-9_-]', '', app_name.replace(' ', '-'))
            
            # Find next available PRD number
            prd_dir = Path("warm-boot/prd")
            existing_prds = list(prd_dir.glob("PRD-*.md"))
            prd_numbers = []
            for prd_file in existing_prds:
                match = re.search(r'PRD-(\d+)', prd_file.name)
                if match:
                    prd_numbers.append(int(match.group(1)))
            
            next_number = max(prd_numbers) + 1 if prd_numbers else 1
            prd_filename = f"PRD-{next_number:03d}-{safe_app_name}.md"
            prd_path = prd_dir / prd_filename
            
            # Save PRD
            await self.agent.write_file(str(prd_path), prd_content)
            
            logger.info(f"{self.name} saved PRD to {prd_path}")
            
            # Extract sections that were generated
            sections_generated = []
            section_patterns = [
                r'##\s+(\d+\.\s+[^\n]+)',
                r'###\s+([^\n]+)'
            ]
            for pattern in section_patterns:
                matches = re.findall(pattern, prd_content)
                sections_generated.extend(matches)
            
            # Record memory for PRD creation
            if hasattr(self.agent, 'record_memory'):
                await self.agent.record_memory(
                    kind="prd_draft",
                    payload={
                        'requirement': requirement,
                        'objective': objective,
                        'app_name': app_name,
                        'prd_path': str(prd_path),
                        'sections_generated': sections_generated
                    },
                    importance=0.8
                )
            
            return {
                'prd_content': prd_content,
                'prd_path': str(prd_path),
                'sections_generated': sections_generated
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to draft PRD: {e}", exc_info=True)
            raise

