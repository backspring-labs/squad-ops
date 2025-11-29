#!/usr/bin/env python3
"""
Schema Validator for AgentRequest and AgentResponse
Validates against JSON schemas and capability catalog
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from jsonschema import validate, ValidationError

from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse
from agents.capabilities.loader import CapabilityLoader

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validator for AgentRequest and AgentResponse"""
    
    def __init__(self, base_path: Optional[Path] = None):
        """Initialize validator with base path"""
        from agents.utils.path_resolver import PathResolver
        
        if base_path is None:
            base_path = PathResolver.get_base_path()
        else:
            base_path = Path(base_path)
        self.base_path = Path(base_path)
        self.specs_path = self.base_path / "agents" / "specs"
        self.request_schema_path = self.specs_path / "request.schema.json"
        self.response_schema_path = self.specs_path / "response.schema.json"
        
        self._request_schema: Optional[Dict[str, Any]] = None
        self._response_schema: Optional[Dict[str, Any]] = None
        self._capability_loader: Optional[CapabilityLoader] = None
    
    def _load_request_schema(self) -> Dict[str, Any]:
        """Load request schema"""
        if self._request_schema is not None:
            return self._request_schema
        
        if not self.request_schema_path.exists():
            logger.warning(f"Request schema not found at {self.request_schema_path}, skipping schema validation")
            # Return a minimal schema that accepts anything
            self._request_schema = {"type": "object"}
            return self._request_schema
        
        with open(self.request_schema_path, 'r') as f:
            self._request_schema = json.load(f)
        
        return self._request_schema
    
    def _load_response_schema(self) -> Dict[str, Any]:
        """Load response schema"""
        if self._response_schema is not None:
            return self._response_schema
        
        if not self.response_schema_path.exists():
            logger.warning(f"Response schema not found at {self.response_schema_path}, skipping schema validation")
            # Return a minimal schema that accepts anything
            self._response_schema = {"type": "object"}
            return self._response_schema
        
        with open(self.response_schema_path, 'r') as f:
            self._response_schema = json.load(f)
        
        return self._response_schema
    
    def _get_capability_loader(self) -> CapabilityLoader:
        """Get capability loader instance"""
        if self._capability_loader is None:
            self._capability_loader = CapabilityLoader(self.base_path)
        return self._capability_loader
    
    def validate_request(self, request: AgentRequest) -> tuple[bool, Optional[str]]:
        """Validate AgentRequest against schema"""
        try:
            schema = self._load_request_schema()
            request_dict = request.to_dict()
            
            # Validate against JSON schema
            validate(instance=request_dict, schema=schema)
            
            # Validate action format
            if not request.validate_action_format():
                return False, f"Invalid action format: {request.action}"
            
            # Validate capability exists in catalog
            loader = self._get_capability_loader()
            if not loader.validate_capability(request.action):
                return False, f"Capability not found in catalog: {request.action}"
            
            return True, None
            
        except ValidationError as e:
            return False, f"Schema validation failed: {e.message}"
        except Exception as e:
            logger.error(f"Request validation error: {e}", exc_info=True)
            return False, f"Validation error: {str(e)}"
    
    def validate_response(self, response: AgentResponse) -> tuple[bool, Optional[str]]:
        """Validate AgentResponse against schema"""
        try:
            schema = self._load_response_schema()
            response_dict = response.to_dict()
            
            # Validate against JSON schema
            validate(instance=response_dict, schema=schema)
            
            return True, None
            
        except ValidationError as e:
            return False, f"Schema validation failed: {e.message}"
        except Exception as e:
            logger.error(f"Response validation error: {e}", exc_info=True)
            return False, f"Validation error: {str(e)}"
    
    def validate_result_keys(self, capability: str, result: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate result keys match capability catalog result schema"""
        try:
            loader = self._get_capability_loader()
            cap_def = loader.get_capability(capability)
            
            if cap_def is None:
                return False, f"Capability not found: {capability}"
            
            # Get expected result keys from catalog
            expected_keys = set(cap_def.result.get('keys', []))
            actual_keys = set(result.keys())
            
            # Check if all expected keys are present
            missing_keys = expected_keys - actual_keys
            if missing_keys:
                return False, f"Missing result keys: {missing_keys}"
            
            # Warn about extra keys (not strict, but good to know)
            extra_keys = actual_keys - expected_keys
            if extra_keys:
                logger.warning(f"Extra result keys for {capability}: {extra_keys}")
            
            return True, None
            
        except Exception as e:
            logger.error(f"Result key validation error: {e}", exc_info=True)
            return False, f"Validation error: {str(e)}"

