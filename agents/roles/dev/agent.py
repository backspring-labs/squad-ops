#!/usr/bin/env python3
"""
Refactored Dev Agent - Dev Role with Specialized Components
Uses composition pattern with specialized managers for different responsibilities
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from ...base_agent import BaseAgent, AgentMessage
import sys
import os
import aiohttp

# Import specialized components
from .app_builder import AppBuilder
from .docker_manager import DockerManager
from .version_manager import VersionManager
from .file_manager import FileManager
from agents.contracts.task_spec import TaskSpec
from agents.contracts.build_manifest import BuildManifest

# Add config path
sys.path.append('/app')
from config.deployment_config import get_deployment_config, get_docker_config
from config.version import get_framework_version

logger = logging.getLogger(__name__)

class DevAgent(BaseAgent):
    """Dev Agent using composition with specialized components"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="code",
            reasoning_style="deductive"
        )
        
        # Initialize specialized components
        self.app_builder = AppBuilder(llm_client=self.llm_client)
        self.docker_manager = DockerManager()
        self.version_manager = VersionManager()
        self.file_manager = FileManager()
        
        # Task processing state
        self.current_task_requirements = {}
        self.current_run_id = "run-001"
    
    async def _create_technical_task_spec(self, requirements: Dict[str, Any]) -> TaskSpec:
        """Neo creates TaskSpec for technical tasks"""
        logger.info(f"{self.name} creating technical TaskSpec")
        
        prompt = f"""
        You are a senior software engineer creating a TaskSpec for a technical development task.
        
        TASK REQUIREMENTS:
        {requirements}
        
        Create a comprehensive TaskSpec that includes:
        
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
        
        Return the TaskSpec in YAML format:
        
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
            cleaned_response = clean_yaml_response(response)
            task_spec = TaskSpec.from_yaml(cleaned_response)
            logger.info(f"{self.name} created technical TaskSpec with {len(task_spec.features)} features")
            
            return task_spec
            
        except Exception as e:
            logger.error(f"{self.name} failed to create technical TaskSpec: {e}")
            # Fallback to basic TaskSpec
            return TaskSpec(
                app_name="TechnicalTask",
                version="1.0.0",
                run_id=self.current_run_id,
                prd_analysis=f"Technical task - TaskSpec generation failed: {e}",
                features=[],
                constraints={},
                success_criteria=["Task completes successfully"]
            )
    
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
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process development tasks using specialized components"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', task.get('task_type', 'unknown'))
        
        logger.info(f"DevAgent processing {task_type} task: {task_id}")
        
        try:
            # Route to appropriate handler based on task type
            if task_type == "development":
                return await self._handle_development_task(task)
            elif task_type == "code_generation":
                return await self._handle_code_generation_task(task)
            elif task_type == "docker_operations":
                return await self._handle_docker_task(task)
            elif task_type == "version_management":
                return await self._handle_version_task(task)
            else:
                return await self._handle_generic_task(task)
                
        except Exception as e:
            logger.error(f"DevAgent failed to process task {task_id}: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e)
            }
    
    async def _handle_development_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle generic development tasks"""
        task_id = task.get('task_id', 'unknown')
        requirements = task.get('requirements', {})
        action = requirements.get('action', 'unknown')
        
        logger.info(f"DevAgent handling development task: {action}")
        
        # Store requirements for component access
        self.current_task_requirements = requirements
        
        if action == "archive":
            return await self._handle_archive_task(task_id, requirements)
        elif action == "design_manifest":
            return await self._handle_design_manifest_task(task_id, requirements)
        elif action == "build":
            return await self._handle_build_task(task_id, requirements)
        elif action == "deploy":
            return await self._handle_deploy_task(task_id, requirements)
        else:
            # Handle technical tasks with Neo's own TaskSpec
            return await self._handle_technical_task(task_id, requirements)
    
    async def _handle_archive_task(self, task_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Handle archive task using VersionManager"""
        try:
            app_name = requirements.get('application', 'application')
            app_kebab = self.app_builder._to_kebab_case(app_name)
            new_version = requirements.get('version', 'unknown')
            source_dir = f"warm-boot/apps/{app_kebab}"
            
            logger.info(f"DevAgent handling archive task: {app_name}")
            
            # Use VersionManager to archive existing version
            archive_result = await self.version_manager.archive_existing_version(
                app_name, source_dir, new_version
            )
            
            if archive_result['status'] == 'success':
                logger.info(f"DevAgent completed archive task: {task_id}")
                return {
                    'task_id': task_id,
                    'status': 'completed',
                    'action': 'archive',
                    'app_name': app_name,
                    'archived_version': archive_result['archived_version'],
                    'archive_dir': archive_result['archive_dir']
                }
            else:
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': archive_result.get('error', 'Archive failed'),
                    'action': 'archive'
                }
                
        except Exception as e:
            logger.error(f"DevAgent failed to handle archive task: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'archive'
            }
    
    async def _handle_design_manifest_task(self, task_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Handle design manifest task using JSON-based Ollama call"""
        try:
            logger.info(f"{self.name} handling design manifest task: {task_id}")
            
            # Extract TaskSpec from requirements
            if 'task_spec' in requirements:
                task_spec = TaskSpec.from_dict(requirements['task_spec'])
                logger.info(f"{self.name} using provided TaskSpec with {len(task_spec.features)} features")
            else:
                logger.error(f"{self.name} design manifest task missing TaskSpec")
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': 'Design manifest task requires TaskSpec',
                    'action': 'design_manifest'
                }
            
            # Generate manifest using JSON method
            manifest = await self.app_builder.generate_manifest_json(task_spec)
            
            logger.info(f"{self.name} generated manifest JSON: {manifest.architecture_type} with {len(manifest.files)} files")
            
            return {
                'task_id': task_id,
                'status': 'completed',
                'action': 'design_manifest',
                'manifest': manifest.to_dict(),
                'architecture_type': manifest.architecture_type,
                'file_count': len(manifest.files)
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to handle design manifest task: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'design_manifest'
            }
    
    async def _handle_build_task(self, task_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Handle build task using AppBuilder with JSON workflow"""
        try:
            app_name = requirements.get('application', 'Application')
            version = requirements.get('version', '1.0.0')
            features = requirements.get('features', [])
            
            # Store current run_id for use in templates
            self.current_run_id = requirements.get('warm_boot_sequence', '001')
            if not self.current_run_id.startswith('run-'):
                self.current_run_id = f"run-{self.current_run_id}"
            
            logger.info(f"{self.name} handling build task: {app_name} v{version}")
            
            # JSON workflow: manifest is required
            if 'manifest' not in requirements:
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': 'Manifest is required for build task',
                    'action': 'build'
                }
            
            # Use provided manifest for JSON workflow
            logger.info(f"{self.name} using provided manifest for JSON workflow")
            manifest = BuildManifest.from_dict(requirements['manifest'])
            task_spec = requirements.get('task_spec')
            if task_spec:
                task_spec = TaskSpec.from_dict(task_spec)
            else:
                # Create TaskSpec from requirements
                task_spec = TaskSpec(
                    app_name=app_name,
                    version=version,
                    run_id=self.current_run_id,
                    prd_analysis=requirements.get('prd_analysis', 'Application build'),
                    features=features or [],
                    constraints={},
                    success_criteria=["Application deploys successfully"]
                )
            
            # Generate files using JSON method
            files = await self.app_builder.generate_files_json(task_spec, manifest)
            
            # Create all files
            created_files = []
            for file_info in files:
                if file_info['type'] == 'create_file':
                    result = await self.file_manager.create_file(
                        file_info['file_path'],
                        file_info['content'],
                        file_info.get('directory')
                    )
                    if result['status'] == 'success':
                        created_files.append(file_info['file_path'])
            
            logger.info(f"{self.name} created {len(created_files)} files using JSON workflow")
            
            return {
                'task_id': task_id,
                'status': 'completed',
                'action': 'build',
                'app_name': app_name,
                'version': version,
                'created_files': created_files,
                'manifest': manifest.to_dict(),
                'target_directory': f'warm-boot/apps/{app_name.lower().replace(" ", "-")}/'
            }
            
        except Exception as e:
            logger.error(f"DevAgent failed to handle build task: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'build'
            }
    
    async def _handle_technical_task(self, task_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Handle technical tasks using Neo's own TaskSpec generation"""
        try:
            logger.info(f"{self.name} handling technical task: {task_id}")
            
            # Create technical TaskSpec
            task_spec = await self._create_technical_task_spec(requirements)
            
            # Log the technical TaskSpec for telemetry
            logger.info(f"{self.name} generated technical TaskSpec: {task_spec.to_dict()}")
            
            # For now, just log the technical task (future: implement actual technical task execution)
            return {
                'task_id': task_id,
                'status': 'completed',
                'action': 'technical',
                'task_spec': task_spec.to_dict(),
                'message': 'Technical task processed with Neo-generated TaskSpec'
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to handle technical task: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'technical'
            }
    
    async def _handle_deploy_task(self, task_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Handle deploy task using DockerManager"""
        try:
            app_name = requirements.get('application', 'Application')
            version = requirements.get('version', '1.0.0')
            app_kebab = self.app_builder._to_kebab_case(app_name)
            source = requirements.get('source_dir', requirements.get('source', f'warm-boot/apps/{app_kebab}/'))
            
            logger.info(f"DevAgent handling deploy task: {app_name} v{version}")
            
            # Build Docker image using DockerManager
            build_result = await self.docker_manager.build_image(app_name, version, source)
            
            if build_result['status'] != 'success':
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': build_result.get('error', 'Docker build failed'),
                    'action': 'deploy'
                }
            
            # Deploy container using DockerManager
            deploy_result = await self.docker_manager.deploy_container(app_name, version)
            
            if deploy_result['status'] == 'success':
                logger.info(f"DevAgent completed deploy task: {task_id}")
                return {
                    'task_id': task_id,
                    'status': 'completed',
                    'action': 'deploy',
                    'app_name': app_name,
                    'version': version,
                    'container_name': deploy_result['container_name'],
                    'image': deploy_result['image']
                }
            else:
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': deploy_result.get('error', 'Container deployment failed'),
                    'action': 'deploy'
                }
                
        except Exception as e:
            logger.error(f"DevAgent failed to handle deploy task: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'deploy'
            }
    
    async def _handle_code_generation_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle code generation tasks"""
        task_id = task.get('task_id', 'unknown')
        requirements = task.get('requirements', {})
        
        try:
            app_name = requirements.get('application', 'Application')
            version = requirements.get('version', '1.0.0')
            features = requirements.get('features', [])
            
            # Generate custom files based on requirements
            custom_files = await self.code_generator.generate_custom_files(app_name, requirements)
            
            # Create files using FileManager
            created_files = []
            for file_info in custom_files:
                result = await self.file_manager.create_file(
                    file_info['file_path'],
                    file_info['content'],
                    file_info.get('directory')
                )
                if result['status'] == 'success':
                    created_files.append(file_info['file_path'])
            
            return {
                'task_id': task_id,
                'status': 'completed',
                'action': 'code_generation',
                'app_name': app_name,
                'created_files': created_files
            }
            
        except Exception as e:
            logger.error(f"DevAgent failed to handle code generation task: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'code_generation'
            }
    
    async def _handle_docker_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Docker-specific tasks"""
        task_id = task.get('task_id', 'unknown')
        requirements = task.get('requirements', {})
        action = requirements.get('docker_action', 'unknown')
        
        try:
            if action == 'build':
                app_name = requirements.get('application', 'Application')
                version = requirements.get('version', '1.0.0')
                source_dir = requirements.get('source_dir', f'warm-boot/apps/{app_name.lower()}/')
                
                result = await self.docker_manager.build_image(app_name, version, source_dir)
                return {
                    'task_id': task_id,
                    'status': result['status'],
                    'action': 'docker_build',
                    'result': result
                }
                
            elif action == 'deploy':
                app_name = requirements.get('application', 'Application')
                version = requirements.get('version', '1.0.0')
                
                result = await self.docker_manager.deploy_container(app_name, version)
                return {
                    'task_id': task_id,
                    'status': result['status'],
                    'action': 'docker_deploy',
                    'result': result
                }
                
            elif action == 'status':
                container_name = requirements.get('container_name', '')
                
                result = await self.docker_manager.get_container_status(container_name)
                return {
                    'task_id': task_id,
                    'status': result['status'],
                    'action': 'docker_status',
                    'result': result
                }
                
            else:
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': f'Unknown Docker action: {action}'
                }
                
        except Exception as e:
            logger.error(f"DevAgent failed to handle Docker task: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'docker_operations'
            }
    
    async def _handle_version_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle version management tasks"""
        task_id = task.get('task_id', 'unknown')
        requirements = task.get('requirements', {})
        action = requirements.get('version_action', 'unknown')
        
        try:
            if action == 'detect':
                source_dir = requirements.get('source_dir', '')
                
                version = await self.version_manager.detect_existing_version(source_dir)
                return {
                    'task_id': task_id,
                    'status': 'completed',
                    'action': 'version_detect',
                    'detected_version': version,
                    'source_dir': source_dir
                }
                
            elif action == 'calculate':
                framework_version = requirements.get('framework_version', get_framework_version())
                run_id = requirements.get('run_id', 'run-001')
                
                new_version = await self.version_manager.calculate_new_version(framework_version, run_id)
                return {
                    'task_id': task_id,
                    'status': 'completed',
                    'action': 'version_calculate',
                    'new_version': new_version,
                    'framework_version': framework_version,
                    'run_id': run_id
                }
                
            elif action == 'update':
                app_dir = requirements.get('app_dir', '')
                new_version = requirements.get('new_version', '1.0.0')
                
                result = await self.version_manager.update_version_in_files(app_dir, new_version)
                return {
                    'task_id': task_id,
                    'status': result['status'],
                    'action': 'version_update',
                    'result': result
                }
                
            else:
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': f'Unknown version action: {action}'
                }
                
        except Exception as e:
            logger.error(f"DevAgent failed to handle version task: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'version_management'
            }
    
    async def _handle_generic_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle generic tasks - reject governance tasks as they should only go to Max"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', task.get('task_type', 'unknown'))
        
        logger.info(f"DevAgent handling generic task: {task_id} (type: {task_type})")
        
        # Reject governance tasks - they should only be handled by Max
        if task_type == "governance":
            logger.warning(f"DevAgent rejecting governance task {task_id} - governance tasks should only go to Max")
            return {
                'task_id': task_id,
                'status': 'rejected',
                'action': 'governance_rejection',
                'message': 'Development agent cannot handle governance tasks - these should only go to Max (Lead Agent)',
                'error': 'Incorrect task routing: governance tasks should not be sent to development agents'
            }
        
        return {
            'task_id': task_id,
            'status': 'completed',
            'action': 'generic',
            'message': 'Generic task processed by DevAgent'
        }
    
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
            
            # Build list of artifacts
            artifacts = []
            if 'created_files' in result:
                for file_path in result['created_files']:
                    artifacts.append({
                        'path': file_path,
                        'hash': f"sha256:placeholder"  # TODO: implement actual hashing
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
                        'duration_seconds': 0,  # TODO: track actual duration
                        'tokens_used': 0,  # TODO: track tokens if using LLM
                        'tests_passed': result.get('tests_passed', 0),
                        'tests_failed': result.get('tests_failed', 0)
                    },
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
            await self.file_manager.create_directory(runs_dir)
            
            # Create task-specific directory
            task_dir = f"{runs_dir}/{task_id}"
            await self.file_manager.create_directory(task_dir)
            
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

## Components Used
- **CodeGenerator**: {result.get('created_files', [])}
- **DockerManager**: {result.get('container_name', 'N/A')}
- **VersionManager**: {result.get('archived_version', 'N/A')}
- **FileManager**: File operations completed

## Notes
This task was processed using the refactored Dev Agent with specialized components.
Each component handles a specific aspect of the development workflow.
"""
            
            # Write documentation file
            doc_file = f"{task_dir}/task-summary.md"
            await self.file_manager.create_file(doc_file, doc_content)
            
            logger.info(f"DevAgent created documentation: {doc_file}")
            
        except Exception as e:
            logger.error(f"DevAgent failed to create documentation: {e}")
    
    async def get_component_status(self) -> Dict[str, Any]:
        """Get status of all specialized components"""
        try:
            # Get Docker health status
            docker_health = await self.docker_manager.health_check()
            
            # Get file operation history
            file_history = await self.file_manager.get_operation_history()
            
            return {
                'status': 'healthy',
                'components': {
                    'code_generator': {
                        'status': 'ready',
                        'templates_loaded': len(self.code_generator.templates),
                        'generated_files': len(self.code_generator.generated_files)
                    },
                    'docker_manager': {
                        'status': docker_health['status'],
                        'docker_available': docker_health.get('docker_available', False),
                        'daemon_running': docker_health.get('daemon_running', False)
                    },
                    'version_manager': {
                        'status': 'ready',
                        'version_cache': len(self.version_manager.version_cache),
                        'archive_history': len(self.version_manager.archive_history)
                    },
                    'file_manager': {
                        'status': 'ready',
                        'cached_files': file_history['cached_files'],
                        'total_operations': file_history['total_operations']
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

async def main():
    """Main entry point for DevAgent"""
    import os
    identity = os.getenv('AGENT_ID', 'refactored_dev_agent')
    agent = DevAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
