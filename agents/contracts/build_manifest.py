"""
BuildManifest contract for Neo's build architecture plan.

Defines the structured output that Neo generates before building files.
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import yaml


@dataclass
class FileSpec:
    """Specification for a single file in the build"""
    path: str
    purpose: str
    dependencies: List[str]


@dataclass
class BuildManifest:
    """Contract: Neo's build architecture plan"""
    
    architecture_type: str  # "spa_web_app", "api_service", etc.
    framework: str
    files: List[FileSpec]
    deployment: Dict[str, Any]
    
    @classmethod
    def from_yaml(cls, yaml_str: str) -> 'BuildManifest':
        """Parse BuildManifest from YAML string"""
        data = yaml.safe_load(yaml_str)
        
        files = [
            FileSpec(
                path=f['path'],
                purpose=f['purpose'],
                dependencies=f.get('dependencies', [])
            )
            for f in data.get('files', [])
        ]
        
        return cls(
            architecture_type=data.get('architecture', {}).get('type', 'unknown'),
            framework=data.get('architecture', {}).get('framework', 'vanilla'),
            files=files,
            deployment=data.get('deployment', {})
        )
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BuildManifest':
        """Create BuildManifest from dict"""
        files = [
            FileSpec(
                path=f['path'],
                purpose=f['purpose'],
                dependencies=f.get('dependencies', [])
            )
            for f in data.get('files', [])
        ]
        
        architecture = data.get('architecture', {})
        
        return cls(
            architecture_type=architecture.get('type', 'unknown'),
            framework=architecture.get('framework', 'vanilla'),
            files=files,
            deployment=data.get('deployment', {})
        )
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        return {
            'architecture': {
                'type': self.architecture_type,
                'framework': self.framework
            },
            'files': [
                {
                    'path': f.path,
                    'purpose': f.purpose,
                    'dependencies': f.dependencies
                }
                for f in self.files
            ],
            'deployment': self.deployment
        }
    
    def validate_against_task_spec(self, task_spec: 'TaskSpec') -> bool:
        """Validate manifest satisfies TaskSpec requirements"""
        # Basic validation: ensure we have files
        if not self.files:
            raise ValueError("BuildManifest has no files")
        
        # Future: validate against success_criteria, constraints, etc.
        return True
