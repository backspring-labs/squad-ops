#!/usr/bin/env python3
"""
Enhanced Role Factory - Hybrid Approach
Combines template generation with role-specific customization
"""

import yaml
import logging
from typing import Dict, Any, List
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RoleDefinition:
    """Enhanced role definition with customization support"""
    name: str
    display_name: str
    agent_type: str
    reasoning_style: str
    capabilities: List[str]
    task_types: List[str]
    metrics: Dict[str, str]
    description: str
    # NEW: Role-specific customizations
    custom_methods: List[str] = None
    custom_attributes: Dict[str, Any] = None
    custom_imports: List[str] = None
    template_type: str = "standard"  # standard, custom, hybrid

class EnhancedRoleFactory:
    """Enhanced factory that supports both templates and customizations"""
    
    def __init__(self, registry_file: str = "agents/roles/registry.yaml"):
        self.registry_file = registry_file
        self.roles = self._load_roles()
    
    def _load_roles(self) -> Dict[str, RoleDefinition]:
        """Load enhanced role definitions"""
        try:
            with open(self.registry_file, 'r') as f:
                data = yaml.safe_load(f)
            
            roles = {}
            for role_name, role_data in data.get('roles', {}).items():
                roles[role_name] = RoleDefinition(
                    name=role_name,
                    display_name=role_data.get('display_name', role_name.title()),
                    agent_type=role_data.get('agent_type', role_name),
                    reasoning_style=role_data.get('reasoning_style', 'logical'),
                    capabilities=role_data.get('capabilities', []),
                    task_types=role_data.get('task_types', []),
                    metrics=role_data.get('metrics', {}),
                    description=role_data.get('description', f'{role_name.title()} role'),
                    # NEW: Load customizations
                    custom_methods=role_data.get('custom_methods', []),
                    custom_attributes=role_data.get('custom_attributes', {}),
                    custom_imports=role_data.get('custom_imports', []),
                    template_type=role_data.get('template_type', 'standard')
                )
            
            logger.info(f"Loaded {len(roles)} enhanced roles from registry")
            return roles
            
        except Exception as e:
            logger.error(f"Failed to load roles from {self.registry_file}: {e}")
            return {}
    
    def generate_agent_class(self, role_name: str) -> str:
        """Generate agent class with role-specific customizations"""
        role = self.get_role(role_name)
        if not role:
            raise ValueError(f"Role '{role_name}' not found in registry")
        
        # Choose template based on role type
        if role.template_type == "custom":
            return self._generate_custom_agent(role)
        elif role.template_type == "hybrid":
            return self._generate_hybrid_agent(role)
        else:
            return self._generate_standard_agent(role)
    
    def _generate_standard_agent(self, role: RoleDefinition) -> str:
        """Generate standard template-based agent"""
        # Use existing template logic
        template_path = Path("agents/templates/agent_template.py")
        with open(template_path, 'r') as f:
            template = f.read()
        
        class_name = f"{role.name.title()}Agent"
        agent_code = template.replace("{{ROLE_NAME}}", role.name)
        agent_code = agent_code.replace("{{CLASS_NAME}}", class_name)
        agent_code = agent_code.replace("{{AGENT_TYPE}}", role.agent_type)
        agent_code = agent_code.replace("{{REASONING_STYLE}}", role.reasoning_style)
        agent_code = agent_code.replace("{{DESCRIPTION}}", role.description)
        
        return agent_code
    
    def _generate_custom_agent(self, role: RoleDefinition) -> str:
        """Generate custom agent from existing file"""
        custom_file = f"agents/roles/{role.name}/agent.py"
        if Path(custom_file).exists():
            with open(custom_file, 'r') as f:
                return f.read()
        else:
            logger.warning(f"Custom agent file not found for {role.name}, falling back to standard")
            return self._generate_standard_agent(role)
    
    def _generate_hybrid_agent(self, role: RoleDefinition) -> str:
        """Generate hybrid agent with customizations"""
        # Start with standard template
        base_code = self._generate_standard_agent(role)
        
        # Add custom imports
        if role.custom_imports:
            import_section = "\n".join([f"from {imp}" for imp in role.custom_imports])
            base_code = base_code.replace("from base_agent import BaseAgent, AgentMessage", 
                                        f"from base_agent import BaseAgent, AgentMessage\n{import_section}")
        
        # Add custom attributes to __init__
        if role.custom_attributes:
            custom_attrs = "\n        ".join([f"self.{k} = {v}" for k, v in role.custom_attributes.items()])
            base_code = base_code.replace("self.processing_queue = []", 
                                        f"self.processing_queue = []\n        {custom_attrs}")
        
        # Add custom methods
        if role.custom_methods:
            # This would require more sophisticated template processing
            # For now, we'll append custom methods at the end
            custom_methods_code = "\n\n    ".join(role.custom_methods)
            base_code = base_code.replace("if __name__ == \"__main__\":", 
                                        f"{custom_methods_code}\n\nif __name__ == \"__main__\":")
        
        return base_code

if __name__ == "__main__":
    factory = EnhancedRoleFactory()
    
    print("🔍 Enhanced Role Factory")
    print("=" * 40)
    
    for role_name, role in factory.get_all_roles().items():
        print(f"  - {role_name}: {role.template_type} template")
        if role.custom_methods:
            print(f"    Custom methods: {len(role.custom_methods)}")
        if role.custom_attributes:
            print(f"    Custom attributes: {len(role.custom_attributes)}")
