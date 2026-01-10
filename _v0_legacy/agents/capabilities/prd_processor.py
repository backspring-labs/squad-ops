#!/usr/bin/env python3
"""
PRD Processor Capability Handlers
Implements prd.read and prd.analyze capabilities for processing Product Requirements Documents.
"""

import json
import logging
from datetime import datetime
from typing import Any

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
    
    async def read(self, prd_path: str) -> dict[str, Any]:
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
    
    def _parse_sections(self, content: str) -> dict[str, str]:
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
        self.current_cycle_id = agent.current_cycle_id if hasattr(agent, 'current_cycle_id') else None
        
        # Import Skill (reasoning pattern)
        from agents.skills.lead.prd_analysis_prompt import PRDAnalysisPrompt
        
        # Initialize Skill
        self.prd_analysis_prompt_skill = PRDAnalysisPrompt()
    
    async def analyze(self, prd_content: str, agent_role: str = "Lead Agent") -> dict[str, Any]:
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
            # Compose Skills: Load prompt using Skill
            analysis_prompt = self.prd_analysis_prompt_skill.load(
                agent_role=agent_role,
                prd_content=prd_content
            )
            
            logger.info(f"{self.name} making LLM call for PRD analysis...")
            llm_response = await self.agent.llm_response(analysis_prompt, "PRD Analysis")
            logger.info(f"{self.name} received LLM response: {llm_response[:200]}...")
            
            # Log the real AI reasoning to communication log for wrap-up extraction
            self.communication_log.append({
                'timestamp': datetime.utcnow().isoformat(),
                'agent': self.name,
                'message_type': 'llm_reasoning',
                'description': f"Real AI PRD Analysis: {llm_response[:500]}...",
                'cycle_id': self.current_cycle_id,
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


class PRDProcessor:
    """
    PRD Processor - Implements prd.process capability
    
    Orchestrates the complete PRD processing workflow:
    - Reads PRD file
    - Analyzes PRD requirements
    - Creates development tasks
    - Delegates tasks to appropriate agents
    - Handles manifest injection for build tasks
    """
    
    def __init__(self, agent):
        """
        Initialize PRDProcessor with agent instance.
        
        Args:
            agent: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent
        self.name = agent.name if hasattr(agent, 'name') else 'unknown'
        self.capability_loader = agent.capability_loader if hasattr(agent, 'capability_loader') else None
    
    async def process(self, task: dict[str, Any] = None, prd_path: str = None, cycle_id: str = None) -> dict[str, Any]:
        """
        Process a PRD request - orchestrates reading, analysis, task creation, and delegation.
        
        Implements the prd.process capability.
        
        Args:
            task: Task dictionary (if provided, extracts prd_path and cycle_id from it)
            prd_path: Path to PRD file (used if task not provided)
            cycle_id: Execution cycle ID (optional, extracted from task or defaults to CYCLE-WB-001)
            
        Returns:
            Dictionary containing:
            - status: 'success' or 'error'
            - message: Status message
            - prd_path: Path to PRD file
            - tasks_delegated: List of delegated tasks
            - prd_analysis: PRD analysis results
        """
        try:
            # Extract parameters from task dict if provided (for generic routing)
            if task:
                prd_path = task.get('prd_path') or prd_path
                cycle_id = task.get('cycle_id') or task.get('context', {}).get('cycle_id') or cycle_id
            
            if not prd_path:
                return {"status": "error", "message": "PRD path not provided"}
            
            logger.info(f"{self.name} processing PRD request: {prd_path}")
            
            # Use provided cycle_id or create default
            if not cycle_id:
                cycle_id = "CYCLE-WB-001"
            
            # Create execution cycle with project_id (SIP-0047)
            try:
                await self.agent.create_execution_cycle(
                    cycle_id, "PID-001", "warmboot", 
                    f"WarmBoot {cycle_id}", prd_path,
                    project_id="warmboot_selftest"
                )
                logger.info(f"{self.name} created execution cycle {cycle_id} with project_id=warmboot_selftest")
            except Exception as e:
                # Execution cycle may already exist in edge cases - continue anyway
                logger.warning(f"Execution cycle {cycle_id} creation failed (may already exist): {e}")
            
            # Store the current cycle_id for use in create_development_tasks
            self.agent.current_cycle_id = cycle_id
            logger.info(f"{self.name} stored current cycle_id: {cycle_id}")
            
            # Read PRD via capability Loader
            if not self.capability_loader:
                return {"status": "error", "message": "Capability loader not initialized"}
            
            prd_result = await self.capability_loader.execute('prd.read', self.agent, prd_path)
            prd_content = prd_result.get('prd_content', '')
            if not prd_content:
                return {"status": "error", "message": "Failed to read PRD"}
            
            # Analyze PRD requirements via capability Loader
            prd_analysis = await self.capability_loader.execute(
                'prd.analyze', self.agent, prd_content, agent_role="Max, the Lead Agent"
            )
            if not prd_analysis:
                return {"status": "error", "message": "Failed to analyze PRD"}
            
            # Extract app name from PRD path or content
            app_name = "Application"  # Default fallback
            if "prd-" in prd_path.lower():
                # Extract app name from PRD filename (e.g., "PRD-001-HelloSquad.md" -> "HelloSquad")
                import re
                match = re.search(r'PRD-\d+-(.+)\.md', prd_path)
                if match:
                    app_name = match.group(1)
            
            # Create development tasks via capability Loader
            task_result = await self.capability_loader.execute(
                'task.create', self.agent, prd_analysis, app_name, cycle_id
            )
            tasks = task_result.get('tasks', [])
            if not tasks:
                return {"status": "error", "message": "Failed to create tasks"}
            
            # Delegate tasks to appropriate agents
            delegated_tasks = []
            for task in tasks:
                # For build tasks, inject manifest from warmboot_state if available
                # Generic check: if task requires manifest and we have one, inject it
                requirements = task.get('requirements', {})
                if requirements.get('action') == 'build':
                    # Check if manifest is needed and available
                    if requirements.get('manifest') is None:
                        # Check agent's warmboot_state for manifest
                        warmboot_state = getattr(self.agent, 'warmboot_state', {})
                        if warmboot_state.get('manifest'):
                            requirements['manifest'] = warmboot_state['manifest']
                            logger.info(f"{self.name} injected manifest into build task {task['task_id']}")
                        else:
                            # Build task without manifest - skip for now, will be delegated after design manifest completes
                            logger.info(f"{self.name} skipping build task {task['task_id']} - manifest not yet available")
                            continue
                
                # Determine delegation target via Loader
                delegation_result = await self.capability_loader.execute(
                    'task.determine_target', self.agent, task["task_type"]
                )
                delegation_target = delegation_result.get('target_agent', 'dev-agent')
                
                # Log task delegation
                await self.agent.log_task_delegation(
                    task['task_id'],
                    cycle_id,
                    delegation_target,
                    task['description']
                )
                
                await self.agent.send_message(
                    recipient=delegation_target,
                    message_type="task_delegation",
                    payload=task,
                    context={
                        'delegated_by': self.name,
                        'delegation_reason': f"PRD-based task: {task['description']}",
                        'prd_path': prd_path,
                        'prd_analysis': prd_analysis
                    }
                )
                
                # Record memory for task delegation (SIP-042)
                await self.agent.record_memory(
                    kind="task_delegation",
                    payload={
                        'task_id': task['task_id'],
                        'task_type': task.get('task_type', 'unknown'),
                        'delegated_to': delegation_target,
                        'decision': 'approved',
                        'cycle_id': cycle_id
                    },
                    importance=0.7,
                    task_context={'cycle_id': cycle_id, 'pid': task.get('pid', 'unknown')}
                )
                
                delegated_tasks.append({
                    'task_id': task['task_id'],
                    'delegated_to': delegation_target,
                    'status': 'delegated'
                })
            
            logger.info(f"{self.name} successfully processed PRD and delegated {len(delegated_tasks)} tasks")
            
            return {
                "status": "success",
                "message": f"PRD processed and {len(delegated_tasks)} tasks delegated",
                "prd_path": prd_path,
                "tasks_delegated": delegated_tasks,
                "prd_analysis": prd_analysis
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to process PRD request: {e}", exc_info=True)
            return {"status": "error", "message": f"PRD processing failed: {e}"}

