#!/usr/bin/env python3
"""
Build Artifact Capability Handler
Implements build.artifact capability for building application artifacts from specifications.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class BuildArtifact:
    """
    Build Artifact - Implements build.artifact capability
    
    Builds application artifacts from specifications using AppBuilder.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize BuildArtifact with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        
        # Import AppBuilder and other components
        from agents.roles.dev.app_builder import AppBuilder
        from agents.roles.dev.docker_manager import DockerManager
        from agents.roles.dev.file_manager import FileManager
        
        # Initialize AppBuilder and other components
        self.app_builder = AppBuilder(llm_client=agent_instance.llm_client, agent=agent_instance)
        self.docker_manager = DockerManager()
        self.file_manager = FileManager()
    
    async def build(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build application artifacts from specifications.
        
        Implements the build.artifact capability.
        
        Args:
            requirements: Build requirements dictionary containing:
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
            - artifact_uri: URI to built artifacts
            - commit: Git commit hash (if applicable)
            - files_generated: List of generated file paths
            - manifest_uri: URI to architecture manifest
        """
        try:
            app_name = requirements.get('application', 'Application')
            version = requirements.get('version', '1.0.0')
            manifest = requirements.get('manifest')
            
            if not manifest:
                return {
                    'artifact_uri': f'/artifacts/{app_name}/{version}',
                    'commit': 'unknown',
                    'files_generated': [],
                    'manifest_uri': 'unknown',
                    'error': 'Manifest is required for build.artifact'
                }
            
            # Build requirements dict
            build_requirements = {
                'app_name': requirements.get('app_name', app_name),
                'version': version,
                'run_id': requirements.get('run_id', requirements.get('ecid', 'unknown')),
                'prd_analysis': requirements.get('prd_analysis', 'Application build'),
                'features': requirements.get('features', []),
                'constraints': requirements.get('constraints', {}),
                'success_criteria': requirements.get('success_criteria', ["Application deploys successfully"])
            }
            
            # Check if files already exist
            app_dir = f"warm-boot/apps/{app_name.lower().replace(' ', '-')}/"
            
            # If files don't exist, create them
            created_files = []
            if not await self.file_manager.directory_exists(app_dir):
                logger.info(f"{self.name} creating files from manifest")
                files = await self.app_builder.generate_files_json(build_requirements, manifest)
                
                for file_info in files:
                    if file_info['type'] == 'create_file':
                        result = await self.file_manager.create_file(
                            file_info['file_path'],
                            file_info['content'],
                            file_info.get('directory')
                        )
                        if result['status'] == 'success':
                            created_files.append(file_info['file_path'])
            else:
                # Files already exist
                created_files = await self.file_manager.list_files(app_dir)
            
            if not created_files:
                return {
                    'artifact_uri': f'/artifacts/{app_name}/{version}',
                    'commit': 'unknown',
                    'files_generated': [],
                    'manifest_uri': manifest.get('architecture_type', 'unknown') if isinstance(manifest, dict) else 'unknown',
                    'error': 'No files were created'
                }
            
            # Build Docker image
            source_dir = f"warm-boot/apps/{app_name.lower().replace(' ', '-')}/"
            build_result = await self.docker_manager.build_image(app_name, version, source_dir)
            
            if build_result.get('status') != 'success':
                return {
                    'artifact_uri': f'/artifacts/{app_name}/{version}',
                    'commit': 'unknown',
                    'files_generated': created_files,
                    'manifest_uri': manifest.get('architecture_type', 'unknown') if isinstance(manifest, dict) else 'unknown',
                    'error': build_result.get('error', 'Docker build failed')
                }
            
            logger.info(f"{self.name} built artifact: {app_name} v{version}")
            
            return {
                'artifact_uri': f'/artifacts/{app_name}/{version}',
                'commit': 'unknown',  # TODO: Add Git commit tracking
                'files_generated': created_files,
                'manifest_uri': manifest.get('architecture_type', 'unknown') if isinstance(manifest, dict) else 'unknown'
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to build artifact: {e}")
            return {
                'artifact_uri': f'/artifacts/{requirements.get("application", "unknown")}/{requirements.get("version", "unknown")}',
                'commit': 'unknown',
                'files_generated': [],
                'manifest_uri': 'unknown',
                'error': str(e)
            }

