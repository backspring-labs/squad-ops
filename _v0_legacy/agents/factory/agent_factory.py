#!/usr/bin/env python3
"""
SquadOps Agent Factory
Dynamic agent instantiation based on role and identity
"""

import importlib
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class AgentInstance:
    """Agent instance configuration"""
    id: str
    display_name: str
    role: str
    model: str
    enabled: bool
    description: str

class AgentFactory:
    """Factory for creating agents based on role and identity"""
    
    @staticmethod
    def create_agent(instance_config: dict[str, Any]):
        """Create an agent instance from configuration"""
        try:
            role = instance_config['role']
            identity = instance_config['id']
            
            logger.info(f"Creating {role} agent with identity: {identity}")
            
            # Dynamic import based on role
            role_module = importlib.import_module(f"agents.roles.{role}.agent")
            agent_class = getattr(role_module, f"{role.title()}Agent")
            
            # Create agent with identity
            agent = agent_class(identity=identity)
            
            logger.info(f"Successfully created {identity} ({role}) agent")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create agent {instance_config.get('id', 'unknown')}: {e}")
            raise
    
    @staticmethod
    def create_agents_from_instances(instances: list[dict[str, Any]]):
        """Create multiple agents from instances configuration"""
        agents = {}
        
        for instance_config in instances:
            if instance_config.get('enabled', False):
                try:
                    agent = AgentFactory.create_agent(instance_config)
                    agents[instance_config['id']] = agent
                except Exception as e:
                    logger.error(f"Failed to create agent {instance_config['id']}: {e}")
                    continue
        
        logger.info(f"Created {len(agents)} agents from instances")
        return agents
    
    @staticmethod
    def get_available_roles(roles_dir: str = "agents/roles"):
        """Get list of available agent roles"""
        import os
        if os.path.exists(roles_dir):
            return [d for d in os.listdir(roles_dir) 
                   if os.path.isdir(os.path.join(roles_dir, d)) 
                   and not d.startswith('_')]
        return []
    
    @staticmethod
    def validate_instance_config(instance_config: dict[str, Any]) -> bool:
        """Validate agent instance configuration"""
        required_fields = ['id', 'display_name', 'role', 'model', 'enabled']
        
        for field in required_fields:
            if field not in instance_config:
                logger.error(f"Missing required field: {field}")
                return False
        
        # Validate role exists
        available_roles = AgentFactory.get_available_roles()
        if instance_config['role'] not in available_roles:
            logger.error(f"Invalid role: {instance_config['role']}. Available: {available_roles}")
            return False
        
        return True

if __name__ == "__main__":
    # Test the factory
    test_instance = {
        'id': 'test_agent',
        'display_name': 'Test Agent',
        'role': 'lead',
        'model': 'llama3-8b',
        'enabled': True,
        'description': 'Test agent for factory validation'
    }
    
    if AgentFactory.validate_instance_config(test_instance):
        print("✅ Agent instance configuration is valid")
    else:
        print("❌ Agent instance configuration is invalid")
