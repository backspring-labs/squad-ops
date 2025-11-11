#!/usr/bin/env python3
"""
Docker Deployer Capability Handler
Implements docker.deploy capability for deploying containers.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DockerDeployer:
    """
    Docker Deployer - Implements docker.deploy capability
    
    Deploys containers using DockerManager.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize DockerDeployer with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        
        # Import DockerManager and AppBuilder as tools
        from agents.tools.docker_manager import DockerManager
        from agents.tools.app_builder import AppBuilder
        
        self.docker_manager = DockerManager()
        self.app_builder = AppBuilder(llm_client=agent_instance.llm_client, agent=agent_instance)
    
    async def deploy(self, task_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deploy container.
        
        Implements the docker.deploy capability.
        
        Args:
            task_id: Task identifier
            requirements: Requirements dictionary containing:
                - application: Application name
                - version: Application version
                - source_dir: Source directory (optional)
                - ecid: Execution cycle ID
                - pid: Process ID
                
        Returns:
            Dictionary containing:
            - task_id: Task identifier
            - status: Completion status
            - action: Action type
            - app_name: Application name
            - version: Application version
            - container_name: Container name
            - image: Docker image name
        """
        try:
            app_name = requirements.get('application', 'Application')
            version = requirements.get('version', '1.0.0')
            app_kebab = self.app_builder._to_kebab_case(app_name)
            source = requirements.get('source_dir', requirements.get('source', f'warm-boot/apps/{app_kebab}/'))
            
            logger.info(f"{self.name} deploying {app_name} v{version}")
            
            # Emit reasoning event about deployment strategy
            ecid = requirements.get('ecid', getattr(self.agent, 'current_ecid', 'unknown'))
            if hasattr(self.agent, 'emit_reasoning_event'):
                await self.agent.emit_reasoning_event(
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
            
            # Build Docker image using DockerManager (if not already built)
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
                if hasattr(self.agent, 'emit_reasoning_event'):
                    await self.agent.emit_reasoning_event(
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
                
                logger.info(f"{self.name} completed deploy task: {task_id}")
                
                # Record memory for deployment success
                if hasattr(self.agent, 'record_memory'):
                    await self.agent.record_memory(
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
            logger.error(f"{self.name} failed to deploy container: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'deploy'
            }

