"""
TaskSpec contract for Max → Neo task specification.

Defines the structured input that Neo receives for build tasks.
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import yaml


@dataclass
class TaskSpec:
    """Contract: Max → Neo task specification"""
    
    app_name: str
    version: str
    run_id: str
    prd_analysis: str
    features: List[str]
    constraints: Dict[str, Any]
    success_criteria: List[str]
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TaskSpec':
        """Parse TaskSpec from dict"""
        return cls(
            app_name=data.get('app_name', 'Unknown'),
            version=data.get('version', '0.1.0'),
            run_id=data.get('run_id', 'run-001'),
            prd_analysis=data.get('prd_analysis', ''),
            features=data.get('features', []),
            constraints=data.get('constraints', {}),
            success_criteria=data.get('success_criteria', [])
        )
    
    @classmethod
    def from_yaml(cls, yaml_str: str) -> 'TaskSpec':
        """Parse TaskSpec from YAML string"""
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        return {
            'app_name': self.app_name,
            'version': self.version,
            'run_id': self.run_id,
            'prd_analysis': self.prd_analysis,
            'features': self.features,
            'constraints': self.constraints,
            'success_criteria': self.success_criteria
        }



