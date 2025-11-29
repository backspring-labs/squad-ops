#!/usr/bin/env python3
"""
SquadOps Role Factory
Unified role management system that eliminates folder duplication
"""

import yaml
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class RoleDefinition:
    """Role definition from registry"""
    name: str
    display_name: str
    agent_type: str
    reasoning_style: str
    capabilities: List[str]
    task_types: List[str]
    metrics: Dict[str, str]
    description: str

class RoleFactory:
    """Factory for managing roles and generating agent configurations"""
    
    def __init__(self, registry_file: str = "agents/roles/registry.yaml", 
                 file_reader: Optional[Callable] = None):
        self.registry_file = registry_file
        self.file_reader = file_reader or self._default_file_reader
        self.roles = self._load_roles()
    
    def _default_file_reader(self, path: str) -> str:
        """Default file reader - can be mocked in tests"""
        with open(path, 'r') as f:
            return f.read()
    
    def _load_roles(self) -> Dict[str, RoleDefinition]:
        """Load role definitions from registry"""
        try:
            content = self.file_reader(self.registry_file)
            data = yaml.safe_load(content)
            
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
                    description=role_data.get('description', f'{role_name.title()} role')
                )
            
            logger.info(f"Loaded {len(roles)} roles from registry")
            return roles
            
        except Exception as e:
            logger.error(f"Failed to load roles from {self.registry_file}: {e}")
            return {}
    
    def get_role(self, role_name: str) -> RoleDefinition:
        """Get role definition by name"""
        return self.roles.get(role_name)
    
    def get_all_roles(self) -> Dict[str, RoleDefinition]:
        """Get all available roles"""
        return self.roles
    
    def generate_agent_class(self, role_name: str) -> str:
        """Generate agent class code for a role"""
        role = self.get_role(role_name)
        if not role:
            raise ValueError(f"Role '{role_name}' not found in registry")
        
        # Read template
        template_path = Path("agents/templates/agent_template.py")
        if not template_path.exists():
            raise FileNotFoundError("Agent template not found")
        
        with open(template_path, 'r') as f:
            template = f.read()
        
        # Replace placeholders
        class_name = f"{role_name.title()}Agent"
        agent_code = template.replace("{{ROLE_NAME}}", role_name)
        agent_code = agent_code.replace("{{CLASS_NAME}}", class_name)
        agent_code = agent_code.replace("{{AGENT_TYPE}}", role.agent_type)
        agent_code = agent_code.replace("{{REASONING_STYLE}}", role.reasoning_style)
        agent_code = agent_code.replace("{{DESCRIPTION}}", role.description)
        
        return agent_code
    
    def generate_config(self, role_name: str) -> str:
        """Generate config file for a role"""
        role = self.get_role(role_name)
        if not role:
            raise ValueError(f"Role '{role_name}' not found in registry")
        
        # Read template
        template_path = Path("agents/templates/config_template.py")
        if not template_path.exists():
            raise FileNotFoundError("Config template not found")
        
        with open(template_path, 'r') as f:
            template = f.read()
        
        # Replace placeholders
        config_code = template.replace("{{ROLE_NAME}}", role_name)
        config_code = config_code.replace("{{DISPLAY_NAME}}", role.display_name)
        config_code = config_code.replace("{{AGENT_TYPE}}", role.agent_type)
        config_code = config_code.replace("{{REASONING_STYLE}}", role.reasoning_style)
        
        # Format capabilities list
        capabilities_str = "[\n    " + ",\n    ".join([f'"{cap}"' for cap in role.capabilities]) + "\n]"
        config_code = config_code.replace("{{CAPABILITIES}}", capabilities_str)
        
        # Format task types list
        task_types_str = "[\n    " + ",\n    ".join([f'"{task}"' for task in role.task_types]) + "\n]"
        config_code = config_code.replace("{{TASK_TYPES}}", task_types_str)
        
        return config_code
    
    def generate_dockerfile(self, role_name: str) -> str:
        """Generate Dockerfile for a role"""
        # Read template
        template_path = Path("agents/templates/Dockerfile.template")
        if not template_path.exists():
            raise FileNotFoundError("Dockerfile template not found")
        
        with open(template_path, 'r') as f:
            template = f.read()
        
        # Replace placeholders
        dockerfile = template.replace("{{ROLE_NAME}}", role_name)
        
        return dockerfile
    
    def create_role_files(self, role_name: str, output_dir: str = None):
        """Create all files for a role"""
        if not output_dir:
            output_dir = f"agents/roles/{role_name}"
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate and save files
        agent_code = self.generate_agent_class(role_name)
        config_code = self.generate_config(role_name)
        dockerfile = self.generate_dockerfile(role_name)
        
        # Save files
        with open(f"{output_dir}/agent.py", 'w') as f:
            f.write(agent_code)
        
        with open(f"{output_dir}/config.py", 'w') as f:
            f.write(config_code)
        
        with open(f"{output_dir}/Dockerfile", 'w') as f:
            f.write(dockerfile)
        
        # Copy requirements.txt (same for all roles)
        requirements_path = Path("agents/templates/requirements.txt")
        if requirements_path.exists():
            import shutil
            shutil.copy(requirements_path, f"{output_dir}/requirements.txt")
        
        logger.info(f"Created role files for '{role_name}' in {output_dir}")
    
    def validate_role_registry(self) -> bool:
        """Validate role registry structure"""
        try:
            roles = self._load_roles()
            
            required_fields = ['agent_type', 'reasoning_style', 'capabilities', 'task_types']
            
            for role_name, role in roles.items():
                for field in required_fields:
                    if not hasattr(role, field) or not getattr(role, field):
                        logger.error(f"Role '{role_name}' missing required field: {field}")
                        return False
            
            logger.info("Role registry validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Role registry validation failed: {e}")
            return False

if __name__ == "__main__":
    # Test the role factory
    factory = RoleFactory()
    
    print("🔍 Available roles:")
    for role_name, role in factory.get_all_roles().items():
        print(f"  - {role_name}: {role.description}")
    
    print(f"\n📝 Role registry validation: {'✅ PASSED' if factory.validate_role_registry() else '❌ FAILED'}")
    
    # Test role generation
    if factory.get_all_roles():
        test_role = list(factory.get_all_roles().keys())[0]
        print(f"\n🧪 Testing role generation for '{test_role}'...")
        try:
            agent_code = factory.generate_agent_class(test_role)
            print(f"✅ Generated agent class ({len(agent_code)} chars)")
        except Exception as e:
            print(f"❌ Failed to generate agent class: {e}")
