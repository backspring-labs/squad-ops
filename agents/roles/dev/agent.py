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

# Import specialized components - use paths that work in both Docker (flattened) and local
try:
    # Docker container structure (files flattened to /app/)
    from app_builder import AppBuilder
    from docker_manager import DockerManager
    from version_manager import VersionManager
    from file_manager import FileManager
except ImportError:
    # Local development structure
    from agents.roles.dev.app_builder import AppBuilder
    from agents.roles.dev.docker_manager import DockerManager
    from agents.roles.dev.version_manager import VersionManager
    from agents.roles.dev.file_manager import FileManager

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
        
        # Initialize specialized components
        
        # Initialize schema validator
        from pathlib import Path
        base_path = Path(__file__).parent.parent.parent.parent
        self.validator = SchemaValidator(base_path)
        self.app_builder = AppBuilder(llm_client=self.llm_client, agent=self)  # Pass agent for logging (Task 1.1)
        self.docker_manager = DockerManager()
        self.version_manager = VersionManager()
        self.file_manager = FileManager()
        
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
                # build.artifact is now a capability loaded via Loader
                result = await self.capability_loader.execute(action, self, request.payload.get('requirements', request.payload))
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
        """Process development tasks using specialized components - DEPRECATED: Use handle_agent_request instead"""
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
            # Handle technical tasks with Neo's own requirements
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
        """Handle design manifest task - generate manifest AND create initial files"""
        try:
            logger.info(f"{self.name} handling design manifest task: {task_id}")
            
            # Read build requirements directly from requirements dict
            # Ensure features are strings (defensive programming)
            features = requirements.get('features', [])
            if features:
                string_features = []
                for feature in features:
                    if isinstance(feature, str):
                        string_features.append(feature)
                    elif isinstance(feature, dict):
                        # Extract string from dict if needed
                        string_features.append(str(feature.get('name', feature.get('description', str(feature)))))
                    else:
                        string_features.append(str(feature))
                features = string_features
                logger.info(f"{self.name} normalized features to strings: {features}")
            
            # Build requirements dict from flattened requirements
            build_requirements = {
                'app_name': requirements.get('app_name', requirements.get('application', 'Application')),
                'version': requirements.get('version', '1.0.0'),
                'run_id': requirements.get('run_id', requirements.get('ecid', 'unknown')),
                'prd_analysis': requirements.get('prd_analysis', ''),
                'features': features,
                'constraints': requirements.get('constraints', {}),
                'success_criteria': requirements.get('success_criteria', [])
            }
            
            logger.info(f"{self.name} using build requirements with {len(features)} features")
            
            # Generate manifest using JSON method
            manifest = await self.app_builder.generate_manifest_json(build_requirements)
            logger.info(f"{self.name} generated manifest JSON: {manifest.get('architecture_type', 'unknown')} with {len(manifest.get('files', []))} files")
            
            # Emit reasoning event about architecture decisions
            ecid = requirements.get('ecid', getattr(self, 'current_ecid', 'unknown'))
            await self.emit_reasoning_event(
                task_id=task_id,
                ecid=ecid,
                reason_step='decision',
                summary=f"Selected {manifest.get('architecture_type', 'unknown')} architecture with {len(manifest.get('files', []))} files based on build requirements",
                context='manifest_generation',
                key_points=[
                    f"Architecture type: {manifest.get('architecture_type', 'unknown')}",
                    f"File count: {len(manifest.get('files', []))}",
                    f"Features to implement: {len(features)}"
                ],
                confidence=0.85
            )
            
            # Generate files using JSON method
            files = await self.app_builder.generate_files_json(build_requirements, manifest)
            
            # Create all files to ensure directory structure exists
            created_files = []
            # Get target_directory from requirements (set by Max)
            target_directory = requirements.get('target_directory', '')
            logger.info(f"{self.name} target_directory from requirements: '{target_directory}'")
            
            for file_info in files:
                if file_info['type'] == 'create_file':
                    # Ensure directory path is valid
                    # Note: file_info.get('directory') might return None if LLM didn't provide it
                    directory = file_info.get('directory') or ''
                    if not directory or directory == '':
                        # Extract directory from file_path if not provided
                        file_path = file_info['file_path']
                        if '/' in file_path:
                            directory = '/'.join(file_path.split('/')[:-1])
                        else:
                            # Use target_directory from requirements (Max sets this)
                            if target_directory:
                                directory = target_directory.rstrip('/')
                            else:
                                # Fallback to default based on app name
                                app_name = requirements.get('application', 'application')
                                directory = f'warm-boot/apps/{app_name.lower().replace(" ", "-")}'
                    
                    # Final safety check - ensure directory is never empty
                    if not directory or directory == '':
                        # Final fallback - use default
                        app_name = requirements.get('application', 'application')
                        directory = f'warm-boot/apps/{app_name.lower().replace(" ", "-")}'
                        logger.warning(f"{self.name} directory was empty, using fallback: '{directory}'")
                    
                    logger.debug(f"{self.name} creating file {file_info['file_path']} with directory: '{directory}' (from target_directory: '{target_directory}')")
                    result = await self.file_manager.create_file(
                        file_info['file_path'],
                        file_info['content'],
                        directory
                    )
                    if result['status'] == 'success':
                        created_files.append(file_info['file_path'])
                    else:
                        logger.warning(f"{self.name} failed to create file {file_info['file_path']}: {result.get('error', 'Unknown error')}")
            
            logger.info(f"{self.name} created {len(created_files)} files during design phase")
            
            # Emit reasoning event about file creation decisions
            ecid = requirements.get('ecid', getattr(self, 'current_ecid', 'unknown'))
            await self.emit_reasoning_event(
                task_id=task_id,
                ecid=ecid,
                reason_step='checkpoint',
                summary=f"Created {len(created_files)} files with {manifest.get('architecture_type', 'unknown')} structure",
                context='manifest_generation',
                key_points=[
                    f"Files created: {len(created_files)}",
                    f"Target directory: {target_directory or 'default'}",
                    f"Architecture pattern: {manifest.get('architecture_type', 'unknown')}"
                ]
            )
            
            # Record memory for manifest pattern
            await self.record_memory(
                kind="manifest_pattern",
                payload={
                    'task_id': task_id,
                    'architecture_type': manifest.get('architecture_type', 'unknown'),
                    'files_count': len(manifest.get('files', [])),
                    'created_files': created_files,
                    'features': build_requirements.get('features', [])
                },
                importance=0.8,
                task_context={'ecid': ecid, 'pid': requirements.get('pid')}
            )
            
            return {
                'task_id': task_id,
                'status': 'completed',
                'action': 'design_manifest',
                'manifest': manifest if isinstance(manifest, dict) else manifest.to_dict() if hasattr(manifest, 'to_dict') else {},
                'architecture_type': manifest.get('architecture_type', 'unknown') if isinstance(manifest, dict) else getattr(manifest, 'architecture_type', 'unknown'),
                'file_count': len(manifest.get('files', [])) if isinstance(manifest, dict) else len(getattr(manifest, 'files', [])),
                'created_files': created_files
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
            logger.info(f"{self.name} manifest type: {type(requirements.get('manifest'))}, value: {requirements.get('manifest')}")
            if not requirements.get('manifest'):
                logger.error(f"{self.name} manifest is None or missing")
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': 'Manifest is None or missing in requirements',
                    'action': 'build'
                }
            try:
                logger.info(f"{self.name} about to parse manifest...")
                manifest = requirements.get('manifest', {})
                if not isinstance(manifest, dict):
                    manifest = manifest.to_dict() if hasattr(manifest, 'to_dict') else {}
                logger.info(f"{self.name} parsed manifest: {manifest.get('architecture_type', 'unknown')}")
            except Exception as e:
                logger.error(f"{self.name} failed to parse manifest: {e}", exc_info=True)
                raise
            # Build requirements dict from flattened requirements
            build_requirements = {
                'app_name': requirements.get('app_name', app_name),
                'version': version,
                'run_id': requirements.get('run_id', self.current_run_id),
                'prd_analysis': requirements.get('prd_analysis', 'Application build'),
                'features': features or [],
                'constraints': requirements.get('constraints', {}),
                'success_criteria': requirements.get('success_criteria', ["Application deploys successfully"])
            }
            
            # Check if files already exist (created by design task)
            app_dir = f"warm-boot/apps/{app_name.lower().replace(' ', '-')}/"
            logger.debug(f"{self.name} checking app directory: {app_dir}")
            
            # If files don't exist, create them (fallback for robustness)
            if not await self.file_manager.directory_exists(app_dir):
                logger.info(f"{self.name} app directory doesn't exist, creating files from manifest")
                files = await self.app_builder.generate_files_json(build_requirements, manifest)
                
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
                
                logger.info(f"{self.name} created {len(created_files)} files during build phase")
            else:
                logger.info(f"{self.name} app directory exists, files already created by design task")
                # Files already exist, just verify they're there
                created_files = await self.file_manager.list_files(app_dir)
                logger.info(f"{self.name} verified {len(created_files)} existing files")
            
            # Build Docker image (only if files were created successfully)
            if not created_files:
                error_msg = "No files were created - cannot build Docker image. File generation may have failed."
                logger.error(f"{self.name} {error_msg}")
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': error_msg,
                    'action': 'build',
                    'app_name': app_name,
                    'version': version
                }
            
            # Build Docker image
            source_dir = f"warm-boot/apps/{app_name.lower().replace(' ', '-')}/"
            
            # Emit reasoning event about build decisions
            ecid = requirements.get('ecid', getattr(self, 'current_ecid', 'unknown'))
            await self.emit_reasoning_event(
                task_id=task_id,
                ecid=ecid,
                reason_step='decision',
                summary=f"Building Docker image for {app_name} v{version} using {manifest.get('architecture_type', 'unknown') if isinstance(manifest, dict) else getattr(manifest, 'architecture_type', 'unknown')} architecture",
                context='build',
                key_points=[
                    f"Application: {app_name}",
                    f"Version: {version}",
                    f"Architecture: {manifest.get('architecture_type', 'unknown') if isinstance(manifest, dict) else getattr(manifest, 'architecture_type', 'unknown')}",
                    f"Files to containerize: {len(created_files)}"
                ],
                confidence=0.90
            )
            
            build_result = await self.docker_manager.build_image(app_name, version, source_dir)
            
            if build_result.get('status') != 'success':
                error_msg = build_result.get('error', 'Docker build failed')
                logger.error(f"{self.name} Docker build failed: {error_msg}")
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': error_msg,
                    'action': 'build',
                    'app_name': app_name,
                    'version': version
                }
            
            # Emit reasoning event about successful build
            await self.emit_reasoning_event(
                task_id=task_id,
                ecid=ecid,
                reason_step='checkpoint',
                summary=f"Successfully built Docker image {build_result.get('image_name')}:{version}",
                context='build',
                key_points=[
                    f"Image: {build_result.get('image_name')}:{version}",
                    f"Source directory: {source_dir}",
                    f"Files included: {len(created_files)}"
                ]
            )
            
            # Record memory for build success
            await self.record_memory(
                kind="build_success",
                payload={
                    'task_id': task_id,
                    'app_name': app_name,
                    'version': version,
                    'image': build_result.get('image_name'),
                    'created_files_count': len(created_files),
                    'architecture_type': manifest.get('architecture_type', 'unknown')
                },
                importance=0.8,
                task_context={'ecid': ecid, 'pid': requirements.get('pid')}
            )
            
            return {
                'task_id': task_id,
                'status': 'completed',
                'action': 'build',
                'app_name': app_name,
                'version': version,
                'created_files': created_files,
                'manifest': manifest if isinstance(manifest, dict) else manifest.to_dict() if hasattr(manifest, 'to_dict') else {},
                'target_directory': source_dir,
                'image': build_result.get('image_name'),
                'image_version': f"{build_result.get('image_name')}:{version}"
            }
            
        except Exception as e:
            logger.error(f"DevAgent failed to handle build task: {e}", exc_info=True)
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'build'
            }
    
    async def _handle_technical_task(self, task_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Handle technical tasks using Neo's own requirements generation"""
        try:
            logger.info(f"{self.name} handling technical task: {task_id}")
            
            # Create technical requirements
            tech_requirements = await self._create_technical_requirements(requirements)
            
            # Log the technical requirements for telemetry
            logger.info(f"{self.name} generated technical requirements: {tech_requirements}")
            
            # For now, just log the technical task (future: implement actual technical task execution)
            return {
                'task_id': task_id,
                'status': 'completed',
                'action': 'technical',
                'requirements': tech_requirements,
                'message': 'Technical task processed with Neo-generated requirements'
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
            
            # Emit reasoning event about deployment strategy
            ecid = requirements.get('ecid', getattr(self, 'current_ecid', 'unknown'))
            await self.emit_reasoning_event(
                task_id=task_id,
                ecid=ecid,
                reason_step='decision',
                summary=f"Deploying {app_name} v{version} with versioning and traceability enabled",
                context='deploy',
                key_points=[
                    f"Application: {app_name}",
                    f"Version: {version}",
                    f"Source directory: {source}",
                    f"Versioning: {requirements.get('versioning', True)}",
                    f"Traceability: {requirements.get('traceability', True)}"
                ],
                confidence=0.95
            )
            
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
                # Emit reasoning event about successful deployment
                await self.emit_reasoning_event(
                    task_id=task_id,
                    ecid=ecid,
                    reason_step='checkpoint',
                    summary=f"Successfully deployed {app_name} v{version} as container {deploy_result.get('container_name', 'unknown')}",
                    context='deploy',
                    key_points=[
                        f"Container: {deploy_result.get('container_name', 'unknown')}",
                        f"Image: {deploy_result.get('image', 'unknown')}",
                        f"Version: {version}",
                        f"Deployment strategy: Docker container with volume mounts"
                    ]
                )
                
                logger.info(f"DevAgent completed deploy task: {task_id}")
                
                # Record memory for deployment success
                await self.record_memory(
                    kind="deployment_success",
                    payload={
                        'task_id': task_id,
                        'app_name': app_name,
                        'version': version,
                        'container_name': deploy_result['container_name'],
                        'image': deploy_result['image']
                    },
                    importance=0.9,
                    task_context={'ecid': ecid, 'pid': requirements.get('pid')}
                )
                
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
