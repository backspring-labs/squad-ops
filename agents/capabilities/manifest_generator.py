#!/usr/bin/env python3
"""
Manifest Generator Capability Handler
Implements manifest.generate capability for generating architecture manifests and creating initial files.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ManifestGenerator:
    """
    Manifest Generator - Implements manifest.generate capability
    
    Generates architecture manifests and creates initial files using AppBuilder and FileManager.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize ManifestGenerator with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        
        # Import Skills (reasoning patterns)
        from agents.skills.dev.architect_prompt import ArchitectPrompt
        from agents.skills.dev.squadops_constraints import SquadOpsConstraints
        
        # Import Tools (integration adapters)
        from agents.tools.app_builder import AppBuilder
        from agents.tools.file_manager import FileManager
        
        # Initialize Skills
        self.architect_prompt_skill = ArchitectPrompt()
        self.squadops_constraints_skill = SquadOpsConstraints()
        
        # Initialize Tools
        self.app_builder = AppBuilder(llm_client=agent_instance.llm_client, agent=agent_instance)
        self.file_manager = FileManager()
    
    async def generate(self, task_id: str, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate architecture manifest and create initial files.
        
        Implements the manifest.generate capability.
        
        Args:
            task_id: Task identifier
            requirements: Requirements dictionary containing:
                - application: Application name
                - version: Application version
                - features: List of features
                - prd_analysis: PRD analysis content
                - constraints: Build constraints
                - success_criteria: Success criteria
                - ecid: Execution cycle ID
                - pid: Process ID
                - target_directory: Target directory for files
                
        Returns:
            Dictionary containing:
            - task_id: Task identifier
            - status: Completion status
            - action: Action type
            - manifest: Architecture manifest
            - architecture_type: Architecture type
            - file_count: Number of files in manifest
            - created_files: List of created file paths
        """
        try:
            logger.info(f"{self.name} generating manifest for task: {task_id}")
            
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
            
            # Compose Skills + Tools: Load prompts using Skills, then pass to Tool
            import yaml
            import re
            
            # Convert app name to kebab-case for nginx subpath
            app_name = build_requirements.get('app_name', 'application')
            app_name_kebab = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', app_name).lower().replace(' ', '-')
            
            # Load SquadOps constraints using Skill
            constraints = self.squadops_constraints_skill.load(
                version=build_requirements.get('version', '1.0.0'),
                run_id=build_requirements.get('run_id', 'unknown'),
                app_name_kebab=app_name_kebab
            )
            
            # Load architect prompt using Skill
            architect_prompt = self.architect_prompt_skill.load(
                app_name=build_requirements.get('app_name', 'unknown'),
                version=build_requirements.get('version', '1.0.0'),
                prd_analysis=build_requirements.get('prd_analysis', ''),
                features=', '.join(build_requirements.get('features', [])) if build_requirements.get('features') else 'General web application',
                constraints=yaml.dump(build_requirements.get('constraints', {})) if build_requirements.get('constraints') else 'None',
                squadops_constraints=constraints,
                output_format='json'
            )
            
            # Generate manifest using Tool with prompt from Skill
            manifest = await self.app_builder.generate_manifest_json(architect_prompt, build_requirements)
            logger.info(f"{self.name} generated manifest JSON: {manifest.get('architecture_type', 'unknown')} with {len(manifest.get('files', []))} files")
            
            # Emit reasoning event about architecture decisions
            ecid = requirements.get('ecid', getattr(self.agent, 'current_ecid', 'unknown'))
            if hasattr(self.agent, 'emit_reasoning_event'):
                await self.agent.emit_reasoning_event(
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
            
            # Compose Skills + Tools: Load developer prompt using Skill, then pass to Tool
            from agents.skills.dev.developer_prompt import DeveloperPrompt
            developer_prompt_skill = DeveloperPrompt()
            
            # Load developer prompt using Skill
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
            files = await self.app_builder.generate_files_json(developer_prompt, build_requirements, manifest)
            
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
            if hasattr(self.agent, 'emit_reasoning_event'):
                await self.agent.emit_reasoning_event(
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
            if hasattr(self.agent, 'record_memory'):
                await self.agent.record_memory(
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
            logger.error(f"{self.name} failed to generate manifest: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'action': 'design_manifest'
            }

