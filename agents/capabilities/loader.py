#!/usr/bin/env python3
"""
SquadOps Capability Loader
Loads capability catalog, agent configs, and capability bindings
"""

import yaml
import logging
import importlib
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Type, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Capability:
    """Capability definition from catalog"""
    name: str
    capability_version: str
    description: str
    result: Dict[str, Any]

@dataclass
class AgentConfig:
    """Agent configuration from config.yaml"""
    agent_id: str
    role: str
    spec_version: str
    implements: List[Dict[str, Any]]
    constraints: Dict[str, Any]
    defaults: Dict[str, Any]

class CapabilityLoader:
    """Loader for capability catalog, agent configs, and bindings"""
    
    # Mapping from capability names to (module_path, class_name, method_name) tuples
    CAPABILITY_MAP = {
        'task.create': ('agents.capabilities.task_creator', 'TaskCreator', 'create'),
        'prd.read': ('agents.capabilities.prd_processor', 'PRDReader', 'read'),
        'prd.analyze': ('agents.capabilities.prd_processor', 'PRDAnalyzer', 'analyze'),
        'prd.process': ('agents.capabilities.prd_processor', 'PRDProcessor', 'process'),
        'task.delegate': ('agents.capabilities.task_delegator', 'TaskDelegator', 'delegate'),
        'task.determine_target': ('agents.capabilities.task_delegator', 'TaskDelegator', 'determine_target'),
        'build.requirements.generate': ('agents.capabilities.build_requirements_generator', 'BuildRequirementsGenerator', 'generate'),
        'build.artifact': ('agents.capabilities.build_artifact', 'BuildArtifact', 'build'),
        'manifest.generate': ('agents.capabilities.manifest_generator', 'ManifestGenerator', 'generate'),
        'docker.build': ('agents.capabilities.docker_builder', 'DockerBuilder', 'build'),
        'docker.deploy': ('agents.capabilities.docker_deployer', 'DockerDeployer', 'deploy'),
        'version.archive': ('agents.capabilities.version_archiver', 'VersionArchiver', 'archive'),
        'task.completion.handle': ('agents.capabilities.task_completion_handler', 'TaskCompletionHandler', 'handle_completion'),
        'task.completion.emit': ('agents.capabilities.task_completion_emitter', 'TaskCompletionEmitter', 'emit'),
        'warmboot.wrapup': ('agents.capabilities.wrapup_generator', 'WrapupGenerator', 'generate_wrapup'),
        'warmboot.memory': ('agents.capabilities.warmboot_memory_handler', 'WarmBootMemoryHandler', 'load_memories'),
        'validate.warmboot': ('agents.capabilities.warmboot_validator', 'WarmBootValidator', 'validate'),
        'telemetry.collect': ('agents.capabilities.telemetry_collector', 'TelemetryCollector', 'collect'),
        'governance.approval': ('agents.capabilities.governance_approval', 'GovernanceApproval', 'approve'),
        'governance.escalation': ('agents.capabilities.governance_escalation', 'GovernanceEscalation', 'escalate'),
        'governance.task_coordination': ('agents.capabilities.governance_task_coordination', 'GovernanceTaskCoordination', 'coordinate'),
        'comms.documentation': ('agents.capabilities.documentation_creator', 'DocumentationCreator', 'create'),
        'comms.reasoning.emit': ('agents.capabilities.reasoning_event_emitter', 'ReasoningEventEmitter', 'emit'),
    }
    
    # Mapping from task_type and requirements.action values to capability names
    # This allows generic task routing without hardcoded checks in agents
    TASK_TO_CAPABILITY_MAP = {
        # task_type mappings
        'warmboot_wrapup': 'warmboot.wrapup',
        'governance': 'governance.task_coordination',
        'governance_prd': 'prd.process',  # PRD processing tasks
        # requirements.action mappings (for development tasks)
        'archive': 'version.archive',
        'design_manifest': 'manifest.generate',
        'build': 'docker.build',
        'deploy': 'docker.deploy',
    }
    
    # Capabilities that accept task dictionary as first parameter (for generic routing)
    # All other capabilities accept (task_id, requirements)
    TASK_DICT_CAPABILITIES = {
        'warmboot.wrapup',  # Accepts task dict, extracts ecid, task_id, completion_payload, etc.
        'prd.process',  # Accepts task dict, extracts prd_path and ecid
    }
    
    # Calling convention metadata for capabilities
    # Describes how to call each capability from AgentRequest payload
    CALLING_CONVENTIONS = {
        # Convention: 'task_dict' - pass full payload as task dict
        'task_dict': {
            'warmboot.wrapup',
            'prd.process',
        },
        # Convention: 'requirements_only' - extract requirements from payload
        'requirements_only': {
            'build.artifact',
        },
        # Convention: 'task_id_requirements' - extract task_id and requirements from payload
        'task_id_requirements': {
            'manifest.generate',
            'docker.build',
            'docker.deploy',
            'version.archive',
        },
        # Convention: 'payload_and_metadata' - pass payload and metadata (for capabilities that need both)
        'payload_and_metadata': {
            'governance.task_coordination',
            'validate.warmboot',
        },
        # Convention: 'payload_as_is' - pass payload as-is (default)
        # All other capabilities use this convention
    }
    
    def __init__(self, base_path: Optional[Path] = None):
        """Initialize loader with base path"""
        if base_path is None:
            base_path = Path(__file__).parent.parent.parent
        self.base_path = Path(base_path)
        self.catalog_path = self.base_path / "agents" / "capabilities" / "catalog.yaml"
        self.bindings_path = self.base_path / "agents" / "capability_bindings.yaml"
        self.roles_path = self.base_path / "agents" / "roles"
        
        self._catalog: Optional[Dict[str, Capability]] = None
        self._bindings: Optional[Dict[str, str]] = None
        self._class_cache: Dict[str, Type] = {}  # Cache for capability classes
    
    def load_catalog(self) -> Dict[str, Capability]:
        """Load capability catalog"""
        if self._catalog is not None:
            return self._catalog
        
        try:
            with open(self.catalog_path, 'r') as f:
                data = yaml.safe_load(f)
            
            catalog = {}
            for cap_data in data.get('capabilities', []):
                capability = Capability(
                    name=cap_data['name'],
                    capability_version=cap_data.get('capability_version', '1.0.0'),
                    description=cap_data.get('description', ''),
                    result=cap_data.get('result', {})
                )
                catalog[capability.name] = capability
            
            self._catalog = catalog
            logger.info(f"Loaded {len(catalog)} capabilities from catalog")
            return catalog
            
        except Exception as e:
            logger.error(f"Failed to load capability catalog: {e}")
            raise
    
    def load_agent_config(self, role: str) -> Optional[AgentConfig]:
        """Load agent config.yaml for a role"""
        config_path = self.roles_path / role / "config.yaml"
        
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}")
            return None
        
        try:
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)
            
            config = AgentConfig(
                agent_id=data.get('agent_id', ''),
                role=data.get('role', role),
                spec_version=data.get('spec_version', '1.0.0'),
                implements=data.get('implements', []),
                constraints=data.get('constraints', {}),
                defaults=data.get('defaults', {})
            )
            
            logger.info(f"Loaded config for agent {config.agent_id} (role: {role})")
            return config
            
        except Exception as e:
            logger.error(f"Failed to load agent config for role {role}: {e}")
            raise
    
    def load_bindings(self) -> Dict[str, str]:
        """Load capability bindings"""
        if self._bindings is not None:
            return self._bindings
        
        # Return empty dict if file doesn't exist (graceful degradation)
        if not self.bindings_path.exists():
            logger.warning(f"Capability bindings file not found: {self.bindings_path}. Using empty bindings.")
            self._bindings = {}
            return self._bindings
        
        try:
            with open(self.bindings_path, 'r') as f:
                data = yaml.safe_load(f)
            
            bindings = data.get('bindings', {})
            self._bindings = bindings
            logger.info(f"Loaded {len(bindings)} capability bindings")
            return bindings
            
        except Exception as e:
            logger.error(f"Failed to load capability bindings: {e}")
            # Return empty dict instead of raising (graceful degradation)
            self._bindings = {}
            return self._bindings
    
    def get_agent_for_capability(self, capability: str) -> Optional[str]:
        """Resolve capability to agent ID"""
        bindings = self.load_bindings()
        return bindings.get(capability)
    
    def validate_capability(self, capability: str, version: Optional[str] = None) -> bool:
        """Validate capability exists in catalog"""
        catalog = self.load_catalog()
        
        if capability not in catalog:
            return False
        
        if version is not None:
            cap = catalog[capability]
            # Simple version check - can be enhanced
            return cap.capability_version == version
        
        return True
    
    def get_capability(self, capability: str) -> Optional[Capability]:
        """Get capability definition from catalog"""
        catalog = self.load_catalog()
        return catalog.get(capability)
    
    def get_agent_capabilities(self, role: str) -> List[str]:
        """Get list of capabilities implemented by an agent"""
        config = self.load_agent_config(role)
        if config is None:
            return []
        
        return [impl['capability'] for impl in config.implements]
    
    def get_capability_for_task(self, task: Dict[str, Any]) -> Optional[str]:
        """
        Determine capability name for a task based on task_type or requirements.action.
        
        Checks in order:
        1. If task has explicit 'capability' field, use it
        2. If task has 'prd_path', route to 'prd.process'
        3. If task_type maps to a capability, use it
        4. If requirements.action maps to a capability, use it
        5. Return None if no mapping found
        
        Args:
            task: Task dictionary with 'task_type', 'type', 'capability', 'prd_path', and/or 'requirements' keys
            
        Returns:
            Capability name (e.g., 'docker.build') or None if no mapping found
        """
        # Check for explicit capability field first
        if 'capability' in task and task['capability']:
            return task['capability']
        
        # Check for PRD path - route to prd.process capability
        if task.get('prd_path'):
            return 'prd.process'
        
        # Check task_type mapping (supports both 'task_type' and 'type' keys)
        task_type = task.get('task_type') or task.get('type')
        if task_type and task_type in self.TASK_TO_CAPABILITY_MAP:
            return self.TASK_TO_CAPABILITY_MAP[task_type]
        
        # Check requirements.action mapping
        requirements = task.get('requirements', {})
        action = requirements.get('action')
        if action and action in self.TASK_TO_CAPABILITY_MAP:
            return self.TASK_TO_CAPABILITY_MAP[action]
        
        # No mapping found
        return None
    
    def accepts_task_dict(self, capability_name: str) -> bool:
        """
        Check if a capability accepts task dictionary as first parameter.
        
        Args:
            capability_name: Capability name (e.g., 'warmboot.wrapup')
            
        Returns:
            True if capability accepts task dict, False otherwise
        """
        return capability_name in self.TASK_DICT_CAPABILITIES
    
    def get_calling_convention(self, capability_name: str) -> str:
        """
        Get the calling convention for a capability.
        
        Args:
            capability_name: Capability name (e.g., 'docker.build')
            
        Returns:
            Calling convention: 'task_dict', 'requirements_only', 'task_id_requirements', 
            'payload_and_metadata', or 'payload_as_is'
        """
        if capability_name in self.CALLING_CONVENTIONS['task_dict']:
            return 'task_dict'
        elif capability_name in self.CALLING_CONVENTIONS['requirements_only']:
            return 'requirements_only'
        elif capability_name in self.CALLING_CONVENTIONS['task_id_requirements']:
            return 'task_id_requirements'
        elif capability_name in self.CALLING_CONVENTIONS['payload_and_metadata']:
            return 'payload_and_metadata'
        else:
            return 'payload_as_is'
    
    def prepare_capability_args(self, capability_name: str, payload: Dict[str, Any], 
                                metadata: Dict[str, Any] = None) -> tuple:
        """
        Prepare arguments for capability execution based on calling convention.
        
        Args:
            capability_name: Capability name (e.g., 'docker.build')
            payload: Request payload dictionary
            metadata: Optional request metadata dictionary
            
        Returns:
            Tuple of arguments to pass to capability.execute()
        """
        convention = self.get_calling_convention(capability_name)
        
        if convention == 'task_dict':
            # Pass full payload as task dict
            return (payload,)
        elif convention == 'requirements_only':
            # Extract requirements from payload
            requirements = payload.get('requirements', payload)
            return (requirements,)
        elif convention == 'task_id_requirements':
            # Extract task_id and requirements from payload
            task_id = payload.get('task_id', 'unknown')
            requirements = payload.get('requirements', payload)
            return (task_id, requirements)
        elif convention == 'payload_and_metadata':
            # Pass payload and metadata (metadata can be None)
            return (payload, metadata)
        else:  # payload_as_is
            # Pass payload as-is
            return (payload,)
    
    def resolve(self, capability_name: str) -> Optional[Type]:
        """
        Resolve capability name to capability class.
        
        Args:
            capability_name: Name of the capability (e.g., 'task.create')
            
        Returns:
            Capability class if found, None otherwise
        """
        # Check cache first
        if capability_name in self._class_cache:
            return self._class_cache[capability_name]
        
        # Look up in capability map
        if capability_name not in self.CAPABILITY_MAP:
            logger.warning(f"Capability '{capability_name}' not found in capability map")
            return None
        
        module_path, class_name, _ = self.CAPABILITY_MAP[capability_name]
        
        try:
            # Import the module
            module = importlib.import_module(module_path)
            # Get the class
            capability_class = getattr(module, class_name)
            # Cache it
            self._class_cache[capability_name] = capability_class
            logger.debug(f"Resolved capability '{capability_name}' to {capability_class.__name__}")
            return capability_class
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to resolve capability '{capability_name}': {e}")
            return None
    
    async def execute(self, capability_name: str, agent_instance: Any, 
                     *args, **kwargs) -> Any:
        """
        Execute a capability with the given agent instance.
        
        Args:
            capability_name: Name of the capability (e.g., 'task.create')
            agent_instance: Agent instance to pass to capability
            *args: Positional arguments for the capability method
            **kwargs: Keyword arguments for the capability method
            
        Returns:
            Result from capability execution
        """
        # Resolve capability class
        capability_class = self.resolve(capability_name)
        if capability_class is None:
            raise ValueError(f"Capability '{capability_name}' could not be resolved")
        
        # Get method name from map
        if capability_name not in self.CAPABILITY_MAP:
            raise ValueError(f"Capability '{capability_name}' not found in capability map")
        
        _, _, method_name = self.CAPABILITY_MAP[capability_name]
        
        try:
            # Instantiate capability with agent instance
            capability_instance = capability_class(agent_instance)
            
            # Special handling for TaskCreator - set build_requirements_generator if available
            if capability_name == 'task.create' and hasattr(capability_instance, 'set_build_requirements_generator'):
                # Try to get build_requirements_generator from agent or create it
                if hasattr(agent_instance, 'capability_loader'):
                    try:
                        build_req_gen_class = self.resolve('build.requirements.generate')
                        if build_req_gen_class:
                            build_req_gen = build_req_gen_class(agent_instance)
                            capability_instance.set_build_requirements_generator(build_req_gen)
                    except Exception as e:
                        logger.debug(f"Could not set build_requirements_generator for TaskCreator: {e}")
            
            # Get the method
            method = getattr(capability_instance, method_name)
            
            # Execute the method
            if asyncio.iscoroutinefunction(method):
                result = await method(*args, **kwargs)
            else:
                result = method(*args, **kwargs)
            
            logger.debug(f"Executed capability '{capability_name}' via {method_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute capability '{capability_name}': {e}", exc_info=True)
            raise

