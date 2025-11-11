#!/usr/bin/env python3
"""
Refactored Dev Agent - Dev Role with Specialized Components
Uses composition pattern with specialized managers for different responsibilities
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from base_agent import BaseAgent, AgentMessage
import sys
import os
import aiohttp

# Add config path first
sys.path.append('/app')

from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse, Error, Timing
from agents.specs.validator import SchemaValidator
from datetime import datetime
from config.deployment_config import get_deployment_config, get_docker_config
from config.version import get_framework_version

logger = logging.getLogger(__name__)

class DevAgent(BaseAgent):
    """Dev Agent using composition with specialized components"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="developer",
            reasoning_style="deductive"
        )
        
        # Initialize schema validator
        from pathlib import Path
        base_path = Path(__file__).parent.parent.parent.parent
        self.validator = SchemaValidator(base_path)
        
        # Components are now loaded via capabilities - no direct instantiation needed
        
        # Task processing state
        self.current_task_requirements = {}
        self.current_run_id = "run-001"
        self.task_start_times = {}  # Task 3.1: Track task start times for duration calculation
    
    async def emit_reasoning_event(self, task_id: str, ecid: str, reason_step: str, 
                                   summary: str, context: str, 
                                   key_points: List[str] = None, confidence: float = None):
        """
        Emit reasoning event to LeadAgent for telemetry wrap-up
        
        Includes actual LLM reasoning from communication_log if available.
        
        Args:
            task_id: Task identifier
            ecid: Execution cycle identifier
            reason_step: Type of reasoning step ('decision', 'hypothesis', 'checkpoint')
            summary: Brief summary of reasoning
            context: Operation context ('manifest_generation', 'build', 'deploy', etc.)
            key_points: Optional list of key points
            confidence: Optional confidence level (0.0-1.0)
        """
        try:
            from datetime import datetime
            
            # Extract actual LLM reasoning from communication_log for this context
            llm_reasoning = None
            for entry in self.communication_log:
                entry_ecid = entry.get('ecid')
                entry_type = entry.get('message_type', '')
                entry_context = entry.get('description', '')
                
                # Match by ECID, llm_reasoning type, and context in description
                if (entry_ecid == ecid and 
                    entry_type == 'llm_reasoning' and 
                    context.lower() in entry_context.lower()):
                    # Found matching LLM reasoning - extract it
                    llm_reasoning = {
                        'prompt': entry.get('prompt', '')[:500],  # First 500 chars of prompt
                        'response': entry.get('full_response', '')[:1000],  # First 1000 chars of response
                        'token_usage': entry.get('token_usage', {}),
                        'timestamp': entry.get('timestamp')
                    }
                    break  # Use first matching entry
            
            reasoning_event = {
                'schema': 'reasoning.v1',
                'task_id': task_id,
                'ecid': ecid,
                'reason_step': reason_step,
                'summary': summary,
                'context': context,
                'timestamp': datetime.utcnow().isoformat(),
                'raw_reasoning_included': llm_reasoning is not None
            }
            
            # Add optional fields
            if key_points:
                reasoning_event['key_points'] = key_points
            if confidence is not None:
                reasoning_event['confidence'] = confidence
            
            # Include actual LLM reasoning if found
            if llm_reasoning:
                reasoning_event['llm_reasoning'] = llm_reasoning
                logger.debug(f"{self.name} included LLM reasoning in reasoning event for {context}")
            
            # Send reasoning event to LeadAgent
            await self.send_message(
                recipient='max',
                message_type='agent_reasoning',
                payload=reasoning_event,
                context={
                    'sender_agent': self.name,
                    'sender_role': 'developer',
                    'ecid': ecid
                }
            )
            
            if llm_reasoning:
                logger.info(f"{self.name} emitted reasoning event with LLM reasoning: {reason_step} for {context}")
            else:
                logger.debug(f"{self.name} emitted reasoning event (summary only): {reason_step} for {context}")
            
        except Exception as e:
            logger.warning(f"{self.name} failed to emit reasoning event: {e}")
    
    async def _create_technical_requirements(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Neo creates technical requirements for technical tasks"""
        logger.info(f"{self.name} creating technical requirements")
        
        prompt = f"""
        You are a senior software engineer creating technical requirements for a development task.
        
        TASK REQUIREMENTS:
        {requirements}
        
        Create comprehensive technical requirements that include:
        
        1. PRD_ANALYSIS: Technical analysis of the requirements, architecture considerations, and implementation approach
        2. FEATURES: Specific technical features and capabilities to implement
        3. CONSTRAINTS: Technical constraints, performance requirements, security considerations, code quality standards
        4. SUCCESS_CRITERIA: Measurable technical success criteria
        
        Focus on:
        - Code quality and maintainability
        - Performance and scalability
        - Security best practices
        - Testing and validation requirements
        - Documentation and deployment considerations
        
        Return the requirements in YAML format:
        
        app_name: "TechnicalTask"
        version: "1.0.0"
        run_id: "{self.current_run_id}"
        prd_analysis: |
          Your technical analysis here...
        features:
          - technical_feature1
          - technical_feature2
        constraints:
          code_quality: "requirements here"
          performance: "requirements here"
          security: "considerations here"
          testing: "requirements here"
        success_criteria:
          - "Technical criterion 1"
          - "Technical criterion 2"
        """
        
        try:
            response = await self.llm_client.complete(
                prompt=prompt,
                temperature=0.5,  # Lower temp for structured output
                max_tokens=3000
            )
            
            # Clean and parse YAML response
            from agents.llm.validators import clean_yaml_response
            import yaml
            cleaned_response = clean_yaml_response(response)
            tech_requirements = yaml.safe_load(cleaned_response)
            if not isinstance(tech_requirements, dict):
                tech_requirements = {}
            logger.info(f"{self.name} created technical requirements with {len(tech_requirements.get('features', []))} features")
            
            return tech_requirements
            
        except Exception as e:
            logger.error(f"{self.name} failed to create technical requirements: {e}")
            # Fallback to basic requirements dict
            return {
                "app_name": "TechnicalTask",
                "version": "1.0.0",
                "run_id": self.current_run_id,
                "prd_analysis": f"Technical task - Requirements generation failed: {e}",
                "features": [],
                "constraints": {},
                "success_criteria": ["Task completes successfully"]
            }
    
    def _extract_prd_analysis_from_communication_log(self) -> str:
        """Extract PRD analysis from communication log for AI-powered code generation"""
        try:
            # Look for the most recent PRD analysis from Max
            for entry in reversed(self.communication_log):
                if (entry.get('message_type') == 'llm_reasoning' and 
                    'PRD Analysis' in entry.get('description', '')):
                    # Extract the full response from the entry
                    full_response = entry.get('full_response', '')
                    if full_response:
                        return full_response
                    # Fallback to description if full_response not available
                    return entry.get('description', '')
            
            # If no PRD analysis found, return a default message
            logger.warning("No PRD analysis found in communication log, using default")
            return "No PRD analysis available - generating generic application"
            
        except Exception as e:
            logger.error(f"Failed to extract PRD analysis: {e}")
            return "Error extracting PRD analysis - generating generic application"
    
    async def handle_agent_request(self, request: AgentRequest) -> AgentResponse:
        """Handle agent request using capability-based routing"""
        started_at = datetime.utcnow()
        
        try:
            # Validate request
            is_valid, error_msg = self.validator.validate_request(request)
            if not is_valid:
                return AgentResponse.failure(
                    error_code="VALIDATION_ERROR",
                    error_message=error_msg or "Request validation failed",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            
            # Validate constraints
            is_valid, error_msg = self._validate_constraints(request)
            if not is_valid:
                return AgentResponse.failure(
                    error_code="POLICY_VIOLATION",
                    error_message=error_msg or "Constraint validation failed",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            
            # Generate idempotency key
            idempotency_key = request.generate_idempotency_key(self.name)
            
            # Route to capability via Loader
            action = request.action
            if not self.capability_loader:
                return AgentResponse.failure(
                    error_code="LOADER_NOT_INITIALIZED",
                    error_message="Capability loader not initialized",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            
            try:
                # Execute capability via Loader
                # Map action to capability if needed
                capability_name = action
                if action == 'build.artifact':
                    # build.artifact expects requirements dict directly
                    result = await self.capability_loader.execute(action, self, request.payload.get('requirements', request.payload))
                elif action in ['manifest.generate', 'docker.build', 'docker.deploy', 'version.archive']:
                    # These capabilities expect (task_id, requirements) as arguments
                    task_id = request.payload.get('task_id', 'unknown')
                    requirements = request.payload.get('requirements', request.payload)
                    result = await self.capability_loader.execute(action, self, task_id, requirements)
                else:
                    # Default: pass payload as-is
                    result = await self.capability_loader.execute(action, self, request.payload)
            except ValueError as e:
                # Capability not found in Loader
                return AgentResponse.failure(
                    error_code="UNKNOWN_CAPABILITY",
                    error_message=f"Unknown capability: {action}",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            except Exception as e:
                logger.error(f"{self.name}: Capability execution error: {e}", exc_info=True)
                return AgentResponse.failure(
                    error_code="CAPABILITY_EXECUTION_ERROR",
                    error_message=str(e),
                    retryable=True,
                    timing=Timing.create(started_at)
                )
            
            # Validate result keys
            is_valid, error_msg = self.validator.validate_result_keys(action, result)
            if not is_valid:
                logger.warning(f"{self.name}: Result validation warning: {error_msg}")
            
            # Create success response
            ended_at = datetime.utcnow()
            return AgentResponse.success(
                result=result,
                idempotency_key=idempotency_key,
                timing=Timing.create(started_at, ended_at)
            )
            
        except Exception as e:
            logger.error(f"{self.name}: Error handling request: {e}", exc_info=True)
            return AgentResponse.failure(
                error_code="INTERNAL_ERROR",
                error_message=str(e),
                retryable=True,
                timing=Timing.create(started_at)
            )
    
    # _handle_build_artifact removed - build.artifact is handled via process_task
    # All build logic is in process_task methods, no duplicate code needed
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process development tasks using capabilities via loader"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', task.get('task_type', 'unknown'))
        
        logger.info(f"DevAgent processing {task_type} task: {task_id}")
        
        try:
            # Check if this is a new SIP-046 AgentRequest format
            if 'action' in task:
                # Let BaseAgent handle the conversion to AgentRequest
                return await super().process_task(task)
            
            # Old format handling - route to capabilities via loader
            if task_type == "development":
                return await self._handle_development_task(task)
            else:
                # Unknown task type - return error
                logger.warning(f"DevAgent received unknown task type: {task_type}")
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': f'Unknown task type: {task_type}'
                }
                
        except Exception as e:
            logger.error(f"DevAgent failed to process task {task_id}: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e)
            }
    
    async def _handle_development_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle generic development tasks using capabilities"""
        task_id = task.get('task_id', 'unknown')
        requirements = task.get('requirements', {})
        action = requirements.get('action', 'unknown')
        
        logger.info(f"DevAgent handling development task: {action}")
        
        # Store requirements for component access
        self.current_task_requirements = requirements
        
        # Route to capabilities via loader
        if not self.capability_loader:
            logger.error(f"DevAgent: Capability loader not initialized")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': 'Capability loader not initialized'
            }
        
        try:
            # Map action to capability
            capability_map = {
                'archive': 'version.archive',
                'design_manifest': 'manifest.generate',
                'build': 'docker.build',
                'deploy': 'docker.deploy'
            }
            
            capability_name = capability_map.get(action)
            if not capability_name:
                # Unknown action - return error
                logger.warning(f"DevAgent received unknown action: {action}")
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': f'Unknown action: {action}'
                }
            
            # Execute capability via loader
            result = await self.capability_loader.execute(capability_name, self, task_id, requirements)
            return result
            
        except ValueError as e:
            # Capability not found
            logger.error(f"DevAgent: Capability not found: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': f'Capability not found: {e}'
            }
        except Exception as e:
            logger.error(f"DevAgent: Capability execution error: {e}", exc_info=True)
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e)
            }
    
    # Removed unused _handle_* methods - replaced by capabilities:
    # - _handle_archive_task -> version.archive capability
    # - _handle_design_manifest_task -> manifest.generate capability
    # - _handle_build_task -> docker.build capability
    # - _handle_deploy_task -> docker.deploy capability
    # - _handle_technical_task -> unused
    # - _handle_code_generation_task -> unused
    # - _handle_docker_task -> unused
    # - _handle_version_task -> unused
    # - _handle_generic_task -> unused
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle incoming messages"""
        logger.info(f"DevAgent received message: {message.message_type} from {message.sender}")
        
        if message.message_type == "task_delegation":
            await self._handle_task_delegation(message)
        elif message.message_type == "task_acknowledgment":
            await self._handle_task_acknowledgment(message)
        elif message.message_type == "task_error":
            await self._handle_task_error(message)
        else:
            logger.info(f"DevAgent received unknown message type: {message.message_type}")
    
    async def _handle_task_delegation(self, message: AgentMessage):
        """Handle task delegation messages"""
        try:
            task_payload = message.payload
            task_id = task_payload.get('task_id', 'unknown')
            ecid = task_payload.get('ecid', 'unknown')
            
            logger.info(f"DevAgent received task delegation: {task_id} from {message.sender}")
            
            # Set current ECID for AppBuilder token metrics (Fix: Token aggregation)
            self.current_ecid = ecid
            logger.debug(f"{self.name} set current_ecid: {ecid}")
            
            # Track task start time for duration calculation (Task 3.1)
            from datetime import datetime
            self.task_start_times[task_id] = datetime.utcnow()
            
            # Task already exists (created by Max), just update status to 'in_progress'
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.put(
                        f"{self.task_api_url}/api/v1/tasks/{task_id}",
                        json={"status": "in_progress"}
                    ) as resp:
                        if resp.status == 200:
                            logger.info(f"{self.name} marked task {task_id} as in_progress")
                        elif resp.status == 404:
                            # Task doesn't exist, log it
                            await self.log_task_start(task_id, ecid, 
                                task_payload.get('description', 'Unknown task'),
                                task_payload.get('priority', 'MEDIUM'))
                        else:
                            logger.warning(f"Failed to update task status: {await resp.text()}")
            except Exception as e:
                logger.warning(f"Failed to update task {task_id}: {e}, continuing anyway")
            
            # Process the delegated task
            result = await self.process_task(task_payload)
            
            # Log completion with artifacts
            artifacts = {
                'action': result.get('action'),
                'files_created': result.get('files_created', []),
                'containers_deployed': result.get('containers_deployed', []),
                'status': result.get('status', 'unknown')
            }
            await self.log_task_completion(task_id, artifacts)
            
            # Send acknowledgment back to sender
            await self.send_message(
                message.sender,
                "task_acknowledgment",
                {
                    'task_id': task_id,
                    'status': result.get('status', 'unknown'),
                    'result': result,
                    'processed_by': self.name
                }
            )
            
            # Emit developer completion event (SIP-027 Phase 1)
            await self._emit_developer_completion_event(task_id, ecid, result)
            
            # Create documentation if requested
            if task_payload.get('create_documentation', False):
                await self._create_documentation(task_id, result)
            
        except Exception as e:
            logger.error(f"DevAgent failed to handle task delegation: {e}")
            
            # Log task failure
            task_id = task_payload.get('task_id', 'unknown')
            await self.log_task_failure(task_id, str(e))
            
            # Send error back to sender
            await self.send_message(
                message.sender,
                "task_error",
                {
                    'task_id': task_id,
                    'error': str(e),
                    'processed_by': self.name
                }
            )
    
    async def _handle_task_acknowledgment(self, message: AgentMessage):
        """Handle task acknowledgment messages"""
        logger.info(f"DevAgent received task acknowledgment from {message.sender}")
    
    async def _handle_task_error(self, message: AgentMessage):
        """Handle task error messages"""
        logger.error(f"DevAgent received task error from {message.sender}: {message.payload}")
    
    async def _emit_developer_completion_event(self, task_id: str, ecid: str, result: Dict[str, Any]):
        """
        Emit developer completion event for WarmBoot wrap-up (SIP-027 Phase 1)
        This signals Max that development tasks are complete and wrap-up should be generated
        """
        try:
            from datetime import datetime
            import time
            import hashlib
            import os
            
            # Calculate task duration (Task 3.1)
            duration_seconds = 0
            if hasattr(self, 'task_start_times') and task_id in self.task_start_times:
                start_time = self.task_start_times[task_id]
                duration_seconds = (datetime.utcnow() - start_time).total_seconds()
                # Clean up start time after calculation
                del self.task_start_times[task_id]
            
            # Build list of artifacts with actual hashes (Task 3.3)
            artifacts = []
            if 'created_files' in result:
                for file_path in result['created_files']:
                    artifact_hash = "sha256:no_hash"
                    try:
                        if os.path.exists(file_path):
                            with open(file_path, 'rb') as f:
                                file_hash = hashlib.sha256(f.read()).hexdigest()
                                artifact_hash = f"sha256:{file_hash}"
                    except Exception as e:
                        logger.debug(f"{self.name} failed to hash artifact {file_path}: {e}")
                    
                    artifacts.append({
                        'path': file_path,
                        'hash': artifact_hash  # Task 3.3: Actual SHA256 hash
                    })
            
            # Determine tasks completed based on action
            action = result.get('action', 'unknown')
            tasks_completed = []
            if action == 'archive':
                tasks_completed = ['archive']
            elif action == 'build':
                tasks_completed = ['scaffold', 'implement', 'test']
            elif action == 'deploy':
                tasks_completed = ['deploy']
            else:
                tasks_completed = [action]
            
            # Extract reasoning summary from communication log for this task/ecid
            reasoning_summary = self._extract_reasoning_summary_for_task(ecid, action)
            
            # Create completion event payload
            completion_event = {
                'event_type': 'task.developer.completed',
                'sender_agent': self.name,
                'sender_role': 'developer',
                'ecid': ecid,
                'timestamp': datetime.utcnow().isoformat(),
                'payload': {
                    'task_id': task_id,
                    'task_group': 'code_generation',
                    'tasks_completed': tasks_completed,
                    'artifacts': artifacts,
                    'metrics': {
                        'duration_seconds': round(duration_seconds, 2),  # Task 3.1: Track actual duration
                        'tokens_used': self._calculate_total_tokens_used(),  # Task 1.3: Track tokens from communication log
                        'tests_passed': result.get('tests_passed', 0),
                        'tests_failed': result.get('tests_failed', 0)
                    },
                    'reasoning_summary': reasoning_summary,  # Include reasoning summary
                    'status': result.get('status', 'unknown')
                }
            }
            
            # Send completion event to Max
            await self.send_message(
                recipient='max',
                message_type='task.developer.completed',
                payload=completion_event['payload'],
                context={
                    'event_type': completion_event['event_type'],
                    'sender_role': completion_event['sender_role'],
                    'ecid': ecid
                }
            )
            
            logger.info(f"{self.name} emitted developer completion event for task {task_id}, ECID {ecid}")
            
        except Exception as e:
            logger.error(f"{self.name} failed to emit developer completion event: {e}")
    
    async def _create_documentation(self, task_id: str, result: Dict[str, Any]):
        """Create documentation for the task"""
        try:
            # Create runs directory if it doesn't exist
            runs_dir = "warm-boot/runs"
            # Use write_file from BaseAgent instead of file_manager
            await self.write_file(f"{runs_dir}/.gitkeep", "")
            
            # Create task-specific directory
            task_dir = f"{runs_dir}/{task_id}"
            
            # Generate documentation content
            doc_content = f"""# Task Documentation: {task_id}

**Processed by**: {self.name} (DevAgent)
**Timestamp**: {asyncio.get_event_loop().time()}
**Status**: {result.get('status', 'unknown')}

## Task Details
- **Task ID**: {task_id}
- **Action**: {result.get('action', 'unknown')}
- **App Name**: {result.get('app_name', 'N/A')}
- **Version**: {result.get('version', 'N/A')}

## Results
{json.dumps(result, indent=2)}

## Capabilities Used
- **manifest.generate**: {result.get('created_files', [])}
- **docker.build**: {result.get('image', 'N/A')}
- **docker.deploy**: {result.get('container_name', 'N/A')}
- **version.archive**: {result.get('archived_version', 'N/A')}

## Notes
This task was processed using the refactored Dev Agent with capabilities.
Each capability handles a specific aspect of the development workflow.
"""
            
            # Write documentation file
            doc_file = f"{task_dir}/task-summary.md"
            await self.write_file(doc_file, doc_content)
            
            logger.info(f"DevAgent created documentation: {doc_file}")
            
        except Exception as e:
            logger.error(f"DevAgent failed to create documentation: {e}")
    
    async def get_component_status(self) -> Dict[str, Any]:
        """Get status of all capabilities"""
        try:
            return {
                'status': 'healthy',
                'capabilities': {
                    'manifest.generate': {
                        'status': 'ready',
                        'description': 'Generate architecture manifests and create initial files'
                    },
                    'docker.build': {
                        'status': 'ready',
                        'description': 'Build Docker images from source'
                    },
                    'docker.deploy': {
                        'status': 'ready',
                        'description': 'Deploy containers'
                    },
                    'version.archive': {
                        'status': 'ready',
                        'description': 'Archive existing versions'
                    },
                    'build.artifact': {
                        'status': 'ready',
                        'description': 'Build application artifacts from specifications'
                    }
                },
                'agent_info': {
                    'name': self.name,
                    'agent_type': self.agent_type,
                    'reasoning_style': self.reasoning_style,
                    'current_run_id': self.current_run_id
                }
            }
            
        except Exception as e:
            logger.error(f"DevAgent failed to get component status: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _calculate_total_tokens_used(self) -> int:
        """
        Calculate total tokens used from communication log entries (Task 1.3)
        
        Returns:
            Total number of tokens used across all LLM calls in the communication log
        """
        total_tokens = 0
        for entry in self.communication_log:
            if 'token_usage' in entry and isinstance(entry['token_usage'], dict):
                token_usage = entry['token_usage']
                total_tokens += token_usage.get('total_tokens', 0)
        return total_tokens
    
    def _extract_reasoning_summary_for_task(self, ecid: str, action: str) -> Dict[str, Any]:
        """
        Extract reasoning summary from communication log for a specific task/action
        
        Args:
            ecid: Execution cycle identifier
            action: Task action (manifest_generation, build, deploy)
            
        Returns:
            Dictionary with reasoning summary for the task
        """
        reasoning_events = []
        
        # Map action to context
        context_map = {
            'archive': 'archive',
            'design_manifest': 'manifest_generation',
            'build': 'build',
            'deploy': 'deploy'
        }
        
        target_context = context_map.get(action, action)
        
        # Find reasoning events in communication log for this ECID and context
        for entry in self.communication_log:
            entry_ecid = entry.get('ecid')
            entry_type = entry.get('message_type', '')
            
            # Check for LLM reasoning entries
            if entry_ecid == ecid and entry_type == 'llm_reasoning':
                description = entry.get('description', '')
                # Match context more precisely - check for context word in description
                # e.g., "AppBuilder build:" or "manifest_generation:" or "deploy:"
                description_lower = description.lower()
                context_patterns = [
                    f"{target_context}:",  # "build:" or "manifest_generation:"
                    f"appbuilder {target_context}",  # "appbuilder build"
                    f"{target_context} "  # "build " (space after)
                ]
                if any(pattern in description_lower for pattern in context_patterns):
                    reasoning_events.append({
                        'timestamp': entry.get('timestamp'),
                        'summary': description[:200] + ('...' if len(description) > 200 else ''),
                        'context': target_context
                    })
        
        # Build summary
        if reasoning_events:
            return {
                'context': target_context,
                'event_count': len(reasoning_events),
                'key_decisions': [event['summary'] for event in reasoning_events[:3]],  # Top 3
                'reasoning_available': True
            }
        else:
            return {
                'context': target_context,
                'event_count': 0,
                'key_decisions': [],
                'reasoning_available': False,
                'note': 'No reasoning events found for this task'
            }

async def main():
    """Main entry point for DevAgent"""
    import os
    from config.unified_config import get_config
    config = get_config()
    identity = config.get_agent_id()
    agent = DevAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
