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

# Import specialized components
from code_generator import CodeGenerator
from docker_manager import DockerManager
from version_manager import VersionManager
from file_manager import FileManager

# Add config path
sys.path.append('/app')
from config.deployment_config import get_deployment_config, get_docker_config
from config.version import get_framework_version

logger = logging.getLogger(__name__)

class RefactoredDevAgent(BaseAgent):
    """Refactored Dev Agent using composition with specialized components"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="code",
            reasoning_style="deductive"
        )
        
        # Initialize specialized components
        self.code_generator = CodeGenerator()
        self.docker_manager = DockerManager()
        self.version_manager = VersionManager()
        self.file_manager = FileManager()
        
        # Task processing state
        self.current_task_requirements = {}
        self.current_run_id = "run-001"
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process development tasks using specialized components"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', task.get('task_type', 'unknown'))
        
        logger.info(f"RefactoredDevAgent processing {task_type} task: {task_id}")
        
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
            logger.error(f"RefactoredDevAgent failed to process task {task_id}: {e}")
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
        
        logger.info(f"RefactoredDevAgent handling development task: {action}")
        
        # Store requirements for component access
        self.current_task_requirements = requirements
        
        if action == "archive":
            return await self._handle_archive_task(task_id, requirements)
        elif action == "build":
            return await self._handle_build_task(task_id, requirements)
        elif action == "deploy":
            return await self._handle_deploy_task(task_id, requirements)
        else:
            return {
                'task_id': task_id,
                'status': 'error',
                'error': f'Unknown development action: {action}'
            }
    
    async def _handle_archive_task(self, task_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Handle archive task using VersionManager"""
        try:
            app_name = requirements.get('application', 'application')
            app_kebab = self.code_generator.convert_to_kebab_case(app_name)
            new_version = requirements.get('version', 'unknown')
            source_dir = f"warm-boot/apps/{app_kebab}"
            
            logger.info(f"RefactoredDevAgent handling archive task: {app_name}")
            
            # Use VersionManager to archive existing version
            archive_result = await self.version_manager.archive_existing_version(
                app_name, source_dir, new_version
            )
            
            if archive_result['status'] == 'success':
                logger.info(f"RefactoredDevAgent completed archive task: {task_id}")
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
            logger.error(f"RefactoredDevAgent failed to handle archive task: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'archive'
            }
    
    async def _handle_build_task(self, task_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Handle build task using CodeGenerator and FileManager"""
        try:
            app_name = requirements.get('application', 'Application')
            version = requirements.get('version', '1.0.0')
            app_kebab = self.code_generator.convert_to_kebab_case(app_name)
            target_directory = requirements.get('target_directory', f'warm-boot/apps/{app_kebab}/')
            features = requirements.get('features', [])
            
            # Store current run_id for use in templates
            self.current_run_id = requirements.get('warm_boot_sequence', '001')
            if not self.current_run_id.startswith('run-'):
                self.current_run_id = f"run-{self.current_run_id}"
            
            logger.info(f"RefactoredDevAgent handling build task: {app_name} v{version}")
            
            # Create target directory
            await self.file_manager.create_directory(target_directory)
            
            # Generate application files using CodeGenerator
            files = await self.code_generator.generate_application_files(
                app_name, version, features, self.current_run_id
            )
            
            # Create all files using FileManager
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
            
            logger.info(f"RefactoredDevAgent completed build task: {task_id}")
            
            return {
                'task_id': task_id,
                'status': 'completed',
                'action': 'build',
                'app_name': app_name,
                'version': version,
                'created_files': created_files,
                'target_directory': target_directory
            }
            
        except Exception as e:
            logger.error(f"RefactoredDevAgent failed to handle build task: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'build'
            }
    
    async def _handle_deploy_task(self, task_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Handle deploy task using DockerManager"""
        try:
            app_name = requirements.get('application', 'Application')
            version = requirements.get('version', '1.0.0')
            app_kebab = self.code_generator.convert_to_kebab_case(app_name)
            source = requirements.get('source', f'warm-boot/apps/{app_kebab}/')
            
            logger.info(f"RefactoredDevAgent handling deploy task: {app_name} v{version}")
            
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
                logger.info(f"RefactoredDevAgent completed deploy task: {task_id}")
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
            logger.error(f"RefactoredDevAgent failed to handle deploy task: {e}")
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
            logger.error(f"RefactoredDevAgent failed to handle code generation task: {e}")
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
            logger.error(f"RefactoredDevAgent failed to handle Docker task: {e}")
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
            logger.error(f"RefactoredDevAgent failed to handle version task: {e}")
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
        
        logger.info(f"RefactoredDevAgent handling generic task: {task_id} (type: {task_type})")
        
        # Reject governance tasks - they should only be handled by Max
        if task_type == "governance":
            logger.warning(f"RefactoredDevAgent rejecting governance task {task_id} - governance tasks should only go to Max")
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
            'message': 'Generic task processed by RefactoredDevAgent'
        }
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle incoming messages"""
        logger.info(f"RefactoredDevAgent received message: {message.message_type} from {message.sender}")
        
        if message.message_type == "task_delegation":
            await self._handle_task_delegation(message)
        elif message.message_type == "task_acknowledgment":
            await self._handle_task_acknowledgment(message)
        elif message.message_type == "task_error":
            await self._handle_task_error(message)
        else:
            logger.info(f"RefactoredDevAgent received unknown message type: {message.message_type}")
    
    async def _handle_task_delegation(self, message: AgentMessage):
        """Handle task delegation messages"""
        try:
            task_payload = message.payload
            task_id = task_payload.get('task_id', 'unknown')
            
            logger.info(f"RefactoredDevAgent received task delegation: {task_id} from {message.sender}")
            
            # Process the delegated task
            result = await self.process_task(task_payload)
            
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
            
            # Create documentation if requested
            if task_payload.get('create_documentation', False):
                await self._create_documentation(task_id, result)
            
        except Exception as e:
            logger.error(f"RefactoredDevAgent failed to handle task delegation: {e}")
            
            # Send error back to sender
            await self.send_message(
                message.sender,
                "task_error",
                {
                    'task_id': task_payload.get('task_id', 'unknown'),
                    'error': str(e),
                    'processed_by': self.name
                }
            )
    
    async def _handle_task_acknowledgment(self, message: AgentMessage):
        """Handle task acknowledgment messages"""
        logger.info(f"RefactoredDevAgent received task acknowledgment from {message.sender}")
    
    async def _handle_task_error(self, message: AgentMessage):
        """Handle task error messages"""
        logger.error(f"RefactoredDevAgent received task error from {message.sender}: {message.payload}")
    
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

**Processed by**: {self.name} (RefactoredDevAgent)
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
            
            logger.info(f"RefactoredDevAgent created documentation: {doc_file}")
            
        except Exception as e:
            logger.error(f"RefactoredDevAgent failed to create documentation: {e}")
    
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
            logger.error(f"RefactoredDevAgent failed to get component status: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

async def main():
    """Main entry point for RefactoredDevAgent"""
    import os
    identity = os.getenv('AGENT_ID', 'refactored_dev_agent')
    agent = RefactoredDevAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
