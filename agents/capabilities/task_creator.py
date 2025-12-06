#!/usr/bin/env python3
"""
Task Creator Capability Handler
Implements task.create capability for creating development tasks from PRD analysis.
"""

import logging
import re
import time
from typing import Any

logger = logging.getLogger(__name__)


class TaskCreator:
    """
    Task Creator - Implements task.create capability
    
    Creates development tasks based on PRD analysis, including:
    - Archive tasks
    - Design manifest tasks
    - Build tasks
    - Deploy tasks
    """
    
    def __init__(self, agent_instance):
        """
        Initialize TaskCreator with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        self.log_task_start = agent_instance.log_task_start if hasattr(agent_instance, 'log_task_start') else None
        self.current_cycle_id = getattr(agent_instance, 'current_cycle_id', 'CYCLE-WB-001')
        self.build_requirements_generator = None  # Will be set if available
    
    def set_build_requirements_generator(self, generator):
        """Set the build requirements generator to use."""
        self.build_requirements_generator = generator
    
    def _convert_to_kebab_case(self, name: str) -> str:
        """Convert CamelCase to kebab-case (e.g., HelloSquad -> hello-squad)"""
        kebab = re.sub(r'(?<!^)(?=[A-Z])', '-', name)
        return kebab.lower()
    
    async def create(self, prd_analysis: dict[str, Any], app_name: str = "application", cycle_id: str = None, 
                     build_requirements: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Create development tasks from PRD analysis.
        
        Implements the task.create capability.
        
        Args:
            prd_analysis: PRD analysis dictionary with core_features, technical_requirements, etc.
            app_name: Application name
            cycle_id: Execution cycle ID
            build_requirements: Optional pre-generated build requirements (if not provided, will be generated)
            
        Returns:
            Dictionary containing:
            - tasks: List of task dictionaries
            - app_name: Application name
            - app_version: Application version
            - task_count: Number of tasks created
        """
        try:
            # Import version info
            import sys
            sys.path.append('/app')
            from config.version import get_framework_version
            
            app_kebab = self._convert_to_kebab_case(app_name)
            
            # Get framework version and determine warm-boot sequence
            framework_version = get_framework_version()  # e.g., "0.1.4"
            
            # Extract warm-boot sequence from the current cycle_id
            # The cycle_id format: "CYCLE-WB-###-description" -> extract "###"
            current_cycle_id = getattr(self.agent, 'current_cycle_id', self.current_cycle_id)
            cycle_id_parts = current_cycle_id.split("-")
            # For CYCLE-WB-027-test-harness-validation, get index 2 which is "027"
            warm_boot_sequence = cycle_id_parts[2] if len(cycle_id_parts) > 2 else "001"
            
            app_version = f"{framework_version}.{warm_boot_sequence}"  # e.g., "0.1.4.008"
            
            # Use provided cycle_id or fall back to current_cycle_id for run_id
            run_id = cycle_id if cycle_id else current_cycle_id
            
            # Generate build requirements if not provided
            if build_requirements is None:
                if self.build_requirements_generator:
                    build_requirements = await self.build_requirements_generator.generate(
                        prd_content=prd_analysis.get("full_analysis", "Team Status Dashboard with activity feed and project progress tracking"),
                        app_name=app_name,
                        version=app_version,
                        run_id=run_id,
                        features=prd_analysis.get("core_features", [])
                    )
                else:
                    # Fallback if generator not available
                    build_requirements = {
                        'app_name': app_name,
                        'version': app_version,
                        'run_id': run_id,
                        'prd_analysis': prd_analysis.get("full_analysis", ""),
                        'features': prd_analysis.get("core_features", []),
                        'constraints': {},
                        'success_criteria': ["Application deploys successfully"]
                    }
            
            # Create three-task sequence: archive -> design_manifest -> build -> deploy
            tasks = [
                {
                    "task_id": f"{app_kebab}-archive-{int(time.time())}",
                    "task_type": "development",
                    "cycle_id": cycle_id,
                    "description": f"Archive any existing {app_name} application to ensure clean slate build for version {app_version}",
                    "capability": "version.archive",  # Optional: explicit capability (takes precedence over action mapping)
                    "requirements": {
                        "action": "archive",
                        "application": app_name,
                        "version": app_version,
                        "framework_version": framework_version,
                        "warm_boot_sequence": warm_boot_sequence,
                        "clean_slate": True,
                        "create_documentation": True
                    },
                    "complexity": 0.3,
                    "priority": "HIGH"
                },
                {
                    "task_id": f"{app_kebab}-design-{int(time.time())}",
                    "task_type": "development",
                    "cycle_id": cycle_id,
                    "description": f"Design architecture manifest for {app_name} application version {app_version}",
                    "capability": "manifest.generate",  # Optional: explicit capability (takes precedence over action mapping)
                    "requirements": {
                        "action": "design_manifest",
                        "application": app_name,
                        "version": app_version,
                        "framework_version": framework_version,
                        "warm_boot_sequence": warm_boot_sequence,
                        "target_directory": f"warm-boot/apps/{app_kebab}/",
                        # Flatten build requirements directly into requirements
                        "app_name": build_requirements.get("app_name", app_name),
                        "run_id": build_requirements.get("run_id", cycle_id),
                        "prd_analysis": build_requirements.get("prd_analysis", ""),
                        "features": build_requirements.get("features", []),
                        "constraints": build_requirements.get("constraints", {}),
                        "success_criteria": build_requirements.get("success_criteria", [])
                    },
                    "complexity": 0.4,
                    "priority": "HIGH"
                },
                {
                    "task_id": f"{app_kebab}-build-{int(time.time())}",
                    "task_type": "development",
                    "cycle_id": cycle_id,
                    "description": f"Build {app_name} application version {app_version} using JSON workflow",
                    "capability": "docker.build",  # Optional: explicit capability (takes precedence over action mapping)
                    "requirements": {
                        "action": "build",
                        "application": app_name,
                        "version": app_version,
                        "framework_version": framework_version,
                        "warm_boot_sequence": warm_boot_sequence,
                        "features": prd_analysis.get("core_features", []),
                        "technical_requirements": prd_analysis.get("technical_requirements", []),
                        "target_directory": f"warm-boot/apps/{app_kebab}/",
                        "from_scratch": True,
                        # Flatten build requirements directly into requirements
                        "app_name": build_requirements.get("app_name", app_name),
                        "run_id": build_requirements.get("run_id", cycle_id),
                        "prd_analysis": build_requirements.get("prd_analysis", prd_analysis.get("full_analysis", "")),
                        "constraints": build_requirements.get("constraints", {}),
                        "success_criteria": build_requirements.get("success_criteria", []),
                        "manifest": None  # Will be populated by design_manifest completion handler
                    },
                    "complexity": 0.8,
                    "priority": "HIGH"
                },
                {
                    "task_id": f"{app_kebab}-deploy-{int(time.time())}",
                    "task_type": "development",
                    "cycle_id": cycle_id,
                    "description": f"Deploy {app_name} application version {app_version} with proper versioning",
                    "capability": "docker.deploy",  # Optional: explicit capability (takes precedence over action mapping)
                    "requirements": {
                        "action": "deploy",
                        "application": app_name,
                        "version": app_version,
                        "framework_version": framework_version,
                        "warm_boot_sequence": warm_boot_sequence,
                        "source_dir": f"warm-boot/apps/{app_kebab}/",
                        "versioning": True,
                        "traceability": True
                    },
                    "complexity": 0.5,
                    "priority": "MEDIUM"
                }
            ]
            
            # Log task creation for each task
            if self.log_task_start:
                for task in tasks:
                    await self.log_task_start(
                        task['task_id'], 
                        cycle_id, 
                        task['description'],
                        task['priority'],
                        task.get('dependencies', [])
                    )
            
            logger.info(f"{self.name} created {len(tasks)} development tasks for {app_name} version {app_version}")
            
            return {
                'tasks': tasks,
                'app_name': app_name,
                'app_version': app_version,
                'task_count': len(tasks)
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to create development tasks: {e}")
            return {
                'tasks': [],
                'app_name': app_name,
                'app_version': 'unknown',
                'task_count': 0,
                'error': str(e)
            }

