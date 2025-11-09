#!/usr/bin/env python3
"""
PRD Processor Capability Handlers
Implements prd.read and prd.analyze capabilities for processing Product Requirements Documents.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


class PRDReader:
    """
    PRD Reader - Implements prd.read capability
    
    Reads and parses PRD files.
    """
    
    def __init__(self, agent):
        """
        Initialize PRDReader with agent instance.
        
        Args:
            agent: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent
        self.name = agent.name if hasattr(agent, 'name') else 'unknown'
    
    async def read(self, prd_path: str) -> Dict[str, Any]:
        """
        Read and return PRD content.
        
        Implements the prd.read capability.
        
        Args:
            prd_path: Path to PRD file
            
        Returns:
            Dictionary containing prd_content, file_path, and parsed_sections
        """
        try:
            prd_content = await self.agent.read_file(prd_path)
            logger.info(f"{self.name} read PRD: {prd_path}")
            
            # Parse sections (basic parsing - can be enhanced)
            parsed_sections = self._parse_sections(prd_content)
            
            return {
                'prd_content': prd_content,
                'file_path': prd_path,
                'parsed_sections': parsed_sections
            }
        except Exception as e:
            logger.error(f"{self.name} failed to read PRD {prd_path}: {e}")
            return {
                'prd_content': '',
                'file_path': prd_path,
                'parsed_sections': {},
                'error': str(e)
            }
    
    def _parse_sections(self, content: str) -> Dict[str, str]:
        """
        Parse PRD content into sections.
        
        Basic implementation - can be enhanced with more sophisticated parsing.
        """
        sections = {}
        
        # Simple section parsing (look for markdown headers)
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            if line.startswith('#'):
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # Start new section
                current_section = line.lstrip('#').strip()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections


class PRDAnalyzer:
    """
    PRD Analyzer - Implements prd.analyze capability
    
    Analyzes PRD content and extracts requirements using LLM.
    """
    
    def __init__(self, agent):
        """
        Initialize PRDAnalyzer with agent instance.
        
        Args:
            agent: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent
        self.name = agent.name if hasattr(agent, 'name') else 'unknown'
        self.communication_log = agent.communication_log if hasattr(agent, 'communication_log') else []
        self.current_ecid = agent.current_ecid if hasattr(agent, 'current_ecid') else None
    
    async def analyze(self, prd_content: str, agent_role: str = "Lead Agent") -> Dict[str, Any]:
        """
        Analyze PRD content and extract requirements using LLM.
        
        Implements the prd.analyze capability.
        
        Args:
            prd_content: PRD content to analyze
            agent_role: Role of the agent performing the analysis (for prompt customization)
            
        Returns:
            Dictionary containing core_features, technical_requirements, success_criteria, and analysis_summary
        """
        try:
            analysis_prompt = f"""
            You are {agent_role} responsible for analyzing Product Requirements Documents (PRDs) and extracting requirements.
            
            Please analyze the following PRD and extract:
            1. **Core Features**: List the main features that need to be built
            2. **Technical Requirements**: Identify technical constraints and requirements
            3. **Success Criteria**: What defines success for this project
            
            PRD Content:
            {prd_content}
            
            Respond with a structured analysis in JSON format:
            {{
                "core_features": ["feature1", "feature2", ...],
                "technical_requirements": ["req1", "req2", ...],
                "success_criteria": ["criteria1", "criteria2", ...]
            }}
            """
            
            logger.info(f"{self.name} making LLM call for PRD analysis...")
            llm_response = await self.agent.llm_response(analysis_prompt, "PRD Analysis")
            logger.info(f"{self.name} received LLM response: {llm_response[:200]}...")
            
            # Log the real AI reasoning to communication log for wrap-up extraction
            self.communication_log.append({
                'timestamp': datetime.utcnow().isoformat(),
                'agent': self.name,
                'message_type': 'llm_reasoning',
                'description': f"Real AI PRD Analysis: {llm_response[:500]}...",
                'ecid': self.current_ecid,
                'full_response': llm_response
            })
            
            logger.info(f"{self.name} analyzed PRD requirements")
            
            # Try to parse the LLM response as JSON
            try:
                # Extract JSON from the response if it's wrapped in markdown or other text
                if "```json" in llm_response:
                    json_start = llm_response.find("```json") + 7
                    json_end = llm_response.find("```", json_start)
                    json_str = llm_response[json_start:json_end].strip()
                elif "{" in llm_response and "}" in llm_response:
                    json_start = llm_response.find("{")
                    json_end = llm_response.rfind("}") + 1
                    json_str = llm_response[json_start:json_end]
                else:
                    json_str = llm_response
                
                parsed_analysis = json.loads(json_str)
                
                # Add analysis summary
                analysis_summary = f"Analyzed PRD with {len(parsed_analysis.get('core_features', []))} core features, {len(parsed_analysis.get('technical_requirements', []))} technical requirements, and {len(parsed_analysis.get('success_criteria', []))} success criteria."
                
                return {
                    'core_features': parsed_analysis.get('core_features', []),
                    'technical_requirements': parsed_analysis.get('technical_requirements', []),
                    'success_criteria': parsed_analysis.get('success_criteria', []),
                    'analysis_summary': analysis_summary
                }
            except json.JSONDecodeError:
                logger.warning(f"{self.name} could not parse LLM response as JSON, using fallback")
                # Fallback: create a basic structure from the text response
                return {
                    "core_features": ["Core Application Features", "User Interface", "Data Management", "Integration Points"],
                    "technical_requirements": ["Performance requirements", "Scalability", "Security", "Compatibility"],
                    "success_criteria": ["Functional requirements met", "Performance targets achieved", "User acceptance criteria satisfied"],
                    "analysis_summary": "PRD analysis completed with fallback structure due to JSON parsing error."
                }
            
        except Exception as e:
            logger.error(f"{self.name} failed to analyze PRD: {e}")
            return {
                "core_features": ["Core Application Features", "User Interface", "Data Management"],
                "technical_requirements": ["Performance", "Scalability", "Security"],
                "success_criteria": ["Functional requirements", "Performance", "User acceptance"],
                "analysis_summary": f"PRD analysis failed with error: {str(e)}"
            }

