#!/usr/bin/env python3
"""
SquadOps Docker Compose Generator
Dynamic Docker Compose generation from instances.yaml
"""

import yaml
import logging
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

class DockerComposeGenerator:
    """Generate Docker Compose configuration dynamically"""
    
    def __init__(self, instances_file: str = "agents/instances/instances.yaml"):
        self.instances_file = instances_file
        self.base_compose_template = self._load_base_template()
    
    def _load_base_template(self) -> Dict[str, Any]:
        """Load base Docker Compose template"""
        return {
            'version': '3.8',
            'services': {},
            'volumes': {
                'rabbitmq_data': {},
                'postgres_data': {},
                'redis_data': {}
            },
            'networks': {
                'squadnet': {
                    'driver': 'bridge'
                }
            }
        }
    
    def _load_instances(self) -> List[Dict[str, Any]]:
        """Load agent instances from YAML file"""
        try:
            with open(self.instances_file, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('instances', [])
        except Exception as e:
            logger.error(f"Failed to load instances from {self.instances_file}: {e}")
            return []
    
    def _generate_infrastructure_services(self) -> Dict[str, Any]:
        """Generate infrastructure services (RabbitMQ, PostgreSQL, etc.)"""
        return {
            'rabbitmq': {
                'image': 'rabbitmq:3.12-management',
                'container_name': 'squadops-rabbitmq',
                'ports': ['5672:5672', '15672:15672'],
                'environment': {
                    'RABBITMQ_DEFAULT_USER': 'squadops',
                    'RABBITMQ_DEFAULT_PASS': 'squadops123'
                },
                'volumes': ['rabbitmq_data:/var/lib/rabbitmq'],
                'networks': ['squadnet'],
                'healthcheck': {
                    'test': ['CMD', 'rabbitmq-diagnostics', 'ping'],
                    'interval': '30s',
                    'timeout': '10s',
                    'retries': 5
                }
            },
            'postgres': {
                'image': 'postgres:15',
                'container_name': 'squadops-postgres',
                'ports': ['5432:5432'],
                'environment': {
                    'POSTGRES_DB': 'squadops',
                    'POSTGRES_USER': 'squadops',
                    'POSTGRES_PASSWORD': 'squadops123'
                },
                'command': ['postgres', '-c', 'max_connections=200'],
                'volumes': [
                    'postgres_data:/var/lib/postgresql/data',
                    './infra/init.sql:/docker-entrypoint-initdb.d/init.sql'
                ],
                'networks': ['squadnet'],
                'healthcheck': {
                    'test': ['CMD-SHELL', 'pg_isready -U squadops -d squadops'],
                    'interval': '30s',
                    'timeout': '10s',
                    'retries': 5
                }
            },
            'redis': {
                'image': 'redis:7-alpine',
                'container_name': 'squadops-redis',
                'ports': ['6379:6379'],
                'volumes': ['redis_data:/data'],
                'networks': ['squadnet'],
                'healthcheck': {
                    'test': ['CMD', 'redis-cli', 'ping'],
                    'interval': '30s',
                    'timeout': '10s',
                    'retries': 5
                }
            },
            'prefect-server': {
                'image': 'prefecthq/prefect:2.14-python3.11',
                'container_name': 'squadops-prefect-server',
                'ports': ['4200:4200'],
                'environment': {
                    'PREFECT_API_URL': 'http://prefect-server:4200/api',
                    'PREFECT_SERVER_API_HOST': '0.0.0.0',
                    'PREFECT_SERVER_API_PORT': '4200',
                    'PREFECT_API_DATABASE_CONNECTION_URL': 'postgresql+asyncpg://squadops:squadops123@postgres:5432/squadops'
                },
                'depends_on': {
                    'postgres': {'condition': 'service_healthy'}
                },
                'networks': ['squadnet'],
                'command': ['prefect', 'server', 'start', '--host', '0.0.0.0', '--port', '4200'],
                'healthcheck': {
                    'test': ['CMD', 'python', '-c', "import urllib.request; urllib.request.urlopen('http://localhost:4200/api/health')"],
                    'interval': '30s',
                    'timeout': '10s',
                    'retries': 5
                }
            },
            'prefect-ui': {
                'image': 'prefecthq/prefect:2.14-python3.11',
                'container_name': 'squadops-prefect-ui',
                'ports': ['4201:4201'],
                'environment': {
                    'PREFECT_API_URL': 'http://prefect-server:4200/api'
                },
                'depends_on': {
                    'prefect-server': {'condition': 'service_healthy'}
                },
                'networks': ['squadnet'],
                'command': ['prefect', 'server', 'start', '--host', '0.0.0.0', '--port', '4201']
            },
            'health-check': {
                'build': {
                    'context': '.',
                    'dockerfile': 'infra/health-check/Dockerfile'
                },
                'container_name': 'squadops-health-check',
                'ports': ['8000:8000'],
                'environment': {
                    'RABBITMQ_URL': 'amqp://squadops:squadops123@rabbitmq:5672/',
                    'POSTGRES_URL': 'postgresql://squadops:squadops123@postgres:5432/squadops',
                    'REDIS_URL': 'redis://redis:6379',
                    'PREFECT_URL': 'http://prefect-server:4200/api'
                },
                'depends_on': {
                    'rabbitmq': {'condition': 'service_healthy'},
                    'postgres': {'condition': 'service_healthy'},
                    'redis': {'condition': 'service_healthy'},
                    'prefect-server': {'condition': 'service_healthy'}
                },
                'networks': ['squadnet']
            }
        }
    
    def _generate_agent_service(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Docker service configuration for an agent instance"""
        agent_id = instance['id']
        role = instance['role']
        
        return {
            'build': {
                'context': '.',
                'dockerfile': f'agents/roles/{role}/Dockerfile',
                'args': {
                    'AGENT_ROLE': role
                }
            },
            'container_name': f'squadops-{agent_id}',
            'environment': {
                'AGENT_ID': agent_id,
                'AGENT_ROLE': role,
                'AGENT_DISPLAY_NAME': instance['display_name'],
                'AGENT_MODEL': instance['model'],
                'RABBITMQ_URL': 'amqp://squadops:squadops123@rabbitmq:5672/',
                'POSTGRES_URL': 'postgresql://squadops:squadops123@postgres:5432/squadops',
                'REDIS_URL': 'redis://redis:6379'
            },
            'depends_on': {
                'rabbitmq': {'condition': 'service_healthy'},
                'postgres': {'condition': 'service_healthy'},
                'redis': {'condition': 'service_healthy'}
            },
            'networks': ['squadnet']
        }
    
    def generate_compose(self) -> Dict[str, Any]:
        """Generate complete Docker Compose configuration"""
        instances = self._load_instances()
        
        # Start with base template
        compose_config = self.base_compose_template.copy()
        
        # Add infrastructure services
        compose_config['services'].update(self._generate_infrastructure_services())
        
        # Add agent services
        for instance in instances:
            if instance.get('enabled', False):
                agent_id = instance['id']
                compose_config['services'][agent_id] = self._generate_agent_service(instance)
        
        return compose_config
    
    def save_compose(self, output_file: str = "docker-compose.yml"):
        """Generate and save Docker Compose configuration"""
        try:
            compose_config = self.generate_compose()
            
            with open(output_file, 'w') as f:
                yaml.dump(compose_config, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Docker Compose configuration saved to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save Docker Compose configuration: {e}")
            return False
    
    def get_enabled_agents(self) -> List[str]:
        """Get list of enabled agent IDs"""
        instances = self._load_instances()
        return [instance['id'] for instance in instances if instance.get('enabled', False)]

if __name__ == "__main__":
    # Test the generator
    generator = DockerComposeGenerator()
    
    print("🔍 Enabled agents:")
    enabled_agents = generator.get_enabled_agents()
    for agent in enabled_agents:
        print(f"  - {agent}")
    
    print(f"\n📝 Generating Docker Compose configuration...")
    if generator.save_compose():
        print("✅ Docker Compose configuration generated successfully!")
    else:
        print("❌ Failed to generate Docker Compose configuration")
