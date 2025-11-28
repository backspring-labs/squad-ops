#!/usr/bin/env python3
"""
Validation script for SIP-046 capability system
Validates capability catalog, agent configs, and bindings
"""

import sys
import yaml
import json
from pathlib import Path
from typing import Dict, Any, List

def validate_capabilities():
    """Validate capability system"""
    base_path = Path(__file__).parent.parent
    errors = []
    warnings = []
    
    # Load capability catalog
    catalog_path = base_path / "agents" / "capabilities" / "catalog.yaml"
    if not catalog_path.exists():
        errors.append(f"Capability catalog not found: {catalog_path}")
        return errors, warnings
    
    with open(catalog_path, 'r') as f:
        catalog_data = yaml.safe_load(f)
    
    capabilities = {cap['name']: cap for cap in catalog_data.get('capabilities', [])}
    
    # Load capability bindings
    bindings_path = base_path / "agents" / "capability_bindings.yaml"
    if not bindings_path.exists():
        errors.append(f"Capability bindings not found: {bindings_path}")
        return errors, warnings
    
    with open(bindings_path, 'r') as f:
        bindings_data = yaml.safe_load(f)
    
    bindings = bindings_data.get('bindings', {})
    
    # Validate all bindings map to valid capabilities
    for capability, agent_id in bindings.items():
        if capability not in capabilities:
            errors.append(f"Binding references unknown capability: {capability} -> {agent_id}")
    
    # Validate all capabilities have bindings
    for capability_name in capabilities:
        if capability_name not in bindings:
            warnings.append(f"Capability has no binding: {capability_name}")
    
    # Validate agent configs
    roles_path = base_path / "agents" / "roles"
    for role_dir in roles_path.iterdir():
        if not role_dir.is_dir():
            continue
        
        config_path = role_dir / "config.yaml"
        if not config_path.exists():
            warnings.append(f"Agent config not found for role: {role_dir.name}")
            continue
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        agent_id = config_data.get('agent_id', 'unknown')
        role = config_data.get('role', 'unknown')
        implements = config_data.get('implements', [])
        
        # Validate all implemented capabilities exist in catalog
        for impl in implements:
            capability = impl.get('capability', '')
            if capability not in capabilities:
                errors.append(f"Agent {agent_id} ({role}) implements unknown capability: {capability}")
        
        # Validate agent is bound to its capabilities
        for impl in implements:
            capability = impl.get('capability', '')
            if capability in bindings:
                bound_agent = bindings[capability]
                if bound_agent != agent_id:
                    warnings.append(f"Capability {capability} bound to {bound_agent}, but {agent_id} implements it")
    
    # Validate JSON schemas
    specs_path = base_path / "agents" / "specs"
    request_schema_path = specs_path / "request.schema.json"
    response_schema_path = specs_path / "response.schema.json"
    
    if request_schema_path.exists():
        try:
            with open(request_schema_path, 'r') as f:
                json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid request schema JSON: {e}")
    else:
        errors.append(f"Request schema not found: {request_schema_path}")
    
    if response_schema_path.exists():
        try:
            with open(response_schema_path, 'r') as f:
                json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid response schema JSON: {e}")
    else:
        errors.append(f"Response schema not found: {response_schema_path}")
    
    return errors, warnings

def main():
    """Main validation function"""
    errors, warnings = validate_capabilities()
    
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    if errors:
        print("Errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    
    print("✓ All validations passed!")
    sys.exit(0)

if __name__ == "__main__":
    main()

