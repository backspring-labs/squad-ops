#!/usr/bin/env python3
"""
SquadOps Capability Loader
Loads capability catalog, agent configs, and capability bindings
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
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
        
        try:
            with open(self.bindings_path, 'r') as f:
                data = yaml.safe_load(f)
            
            bindings = data.get('bindings', {})
            self._bindings = bindings
            logger.info(f"Loaded {len(bindings)} capability bindings")
            return bindings
            
        except Exception as e:
            logger.error(f"Failed to load capability bindings: {e}")
            raise
    
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

