#!/usr/bin/env python3
"""
Docker Builder Capability Handler
Implements docker.build capability for building Docker images from source.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DockerBuilder:
    """
    Docker Builder - Implements docker.build capability
    
    Builds Docker images from source using DockerManager.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize DockerBuilder with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        
        # Import DockerManager and FileManager as tools
        from agents.tools.docker_manager import DockerManager
        from agents.tools.file_manager import FileManager
        
        self.docker_manager = DockerManager()
        self.file_manager = FileManager()
    
    async def build(self, task_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build Docker image from source.
        
        Implements the docker.build capability.
        
        Args:
            task_id: Task identifier
            requirements: Requirements dictionary containing:
                - application: Application name
                - version: Application version
                - manifest: Architecture manifest (required)
                - features: List of features
                - prd_analysis: PRD analysis content
                - constraints: Build constraints
                - success_criteria: Success criteria
                - ecid: Execution cycle ID
                - pid: Process ID
                
        Returns:
            Dictionary containing:
            - task_id: Task identifier
            - status: Completion status
            - action: Action type
            - app_name: Application name
            - version: Application version
            - created_files: List of created file paths
            - manifest: Architecture manifest
            - target_directory: Source directory
            - image: Docker image name
            - image_version: Docker image version tag
        """
        try:
            app_name = requirements.get('application', 'Application')
            version = requirements.get('version', '1.0.0')
            features = requirements.get('features', [])
            
            logger.info(f"{self.name} building Docker image for {app_name} v{version}")
            
            # JSON workflow: manifest is required
            manifest = requirements.get('manifest')
            if manifest is None or (isinstance(manifest, dict) and not manifest):
                return {
                    'task_id': task_id,
                    'status': 'error',
                    'error': 'Manifest is required for build task. Manifest is missing or empty.',
                    'action': 'build'
                }
            
            # Use provided manifest for JSON workflow
            logger.info(f"{self.name} using provided manifest for JSON workflow")
            if not isinstance(manifest, dict):
                manifest = manifest.to_dict() if hasattr(manifest, 'to_dict') else {}
            logger.info(f"{self.name} parsed manifest: {manifest.get('architecture_type', 'unknown')}")
            
            # Build requirements dict from flattened requirements
            build_requirements = {
                'app_name': requirements.get('app_name', app_name),
                'version': version,
                'run_id': requirements.get('run_id', requirements.get('ecid', 'unknown')),
                'prd_analysis': requirements.get('prd_analysis', 'Application build'),
                'features': features or [],
                'constraints': requirements.get('constraints', {}),
                'success_criteria': requirements.get('success_criteria', ["Application deploys successfully"])
            }
            
            # Check if files already exist (created by design task)
            app_dir = f"warm-boot/apps/{app_name.lower().replace(' ', '-')}/"
            logger.debug(f"{self.name} checking app directory: {app_dir}")
            
            # If files don't exist, create them (fallback for robustness)
            created_files = []
            if not await self.file_manager.directory_exists(app_dir):
                logger.info(f"{self.name} app directory doesn't exist, creating files from manifest")
                # Compose Skills + Tools: Load prompts using Skills, then pass to Tool
                from agents.skills.dev.developer_prompt import DeveloperPrompt
                from agents.skills.dev.squadops_constraints import SquadOpsConstraints
                from agents.tools.app_builder import AppBuilder
                import yaml
                import re
                
                app_builder = AppBuilder(llm_client=self.agent.llm_client, agent=self.agent)
                
                # Convert app name to kebab-case for nginx subpath
                app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', build_requirements.get('app_name', 'application')).lower().replace(' ', '-')
                
                # Load SquadOps constraints using Skill
                constraints_skill = SquadOpsConstraints()
                constraints = constraints_skill.load(
                    version=build_requirements.get('version', '1.0.0'),
                    run_id=build_requirements.get('run_id', 'unknown'),
                    app_name_kebab=app_name_kebab
                )
                
                # Load developer prompt using Skill
                developer_prompt_skill = DeveloperPrompt()
                developer_prompt = developer_prompt_skill.load(
                    app_name=build_requirements.get('app_name', 'unknown'),
                    app_name_kebab=app_name_kebab,
                    version=build_requirements.get('version', '1.0.0'),
                    run_id=build_requirements.get('run_id', 'unknown'),
                    prd_analysis=build_requirements.get('prd_analysis', ''),
                    features=', '.join(build_requirements.get('features', [])) if build_requirements.get('features') else 'General web application',
                    constraints=yaml.dump(build_requirements.get('constraints', {})) if build_requirements.get('constraints') else 'None',
                    manifest_summary=yaml.dump(manifest),
                    output_format='json',
                    squadops_constraints=constraints  # Inject constraints
                )
                
                # Replace $squadops_constraints placeholder if present
                developer_prompt = developer_prompt.replace('$squadops_constraints', constraints)
                
                # Generate files using Tool with prompt from Skill
                files = await app_builder.generate_files_json(developer_prompt, build_requirements, manifest)
                
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
            ecid = requirements.get('ecid', getattr(self.agent, 'current_ecid', 'unknown'))
            if hasattr(self.agent, 'emit_reasoning_event'):
                await self.agent.emit_reasoning_event(
                    task_id=task_id,
                    ecid=ecid,
                    reason_step='decision',
                    summary=f"Building Docker image for {app_name} v{version} using {manifest.get('architecture_type', 'unknown')} architecture",
                    context='build',
                    key_points=[
                        f"Application: {app_name}",
                        f"Version: {version}",
                        f"Architecture: {manifest.get('architecture_type', 'unknown')}",
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
            if hasattr(self.agent, 'emit_reasoning_event'):
                await self.agent.emit_reasoning_event(
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
            if hasattr(self.agent, 'record_memory'):
                await self.agent.record_memory(
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
            logger.error(f"{self.name} failed to build Docker image: {e}", exc_info=True)
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'build'
            }

