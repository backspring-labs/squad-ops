#!/usr/bin/env python3
"""
AgentResponse contract for SIP-046
Defines the structured output from agent capability execution
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class Error:
    """Error details for AgentResponse"""
    code: str
    message: str
    retryable: bool = False


@dataclass
class Timing:
    """Timing information for AgentResponse"""
    started_at: str
    ended_at: str
    
    @classmethod
    def create(cls, started_at: Optional[datetime] = None, ended_at: Optional[datetime] = None) -> 'Timing':
        """Create Timing from datetime objects"""
        if started_at is None:
            started_at = datetime.utcnow()
        if ended_at is None:
            ended_at = datetime.utcnow()
        
        return cls(
            started_at=started_at.isoformat(),
            ended_at=ended_at.isoformat()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Timing to dict"""
        return {
            'started_at': self.started_at,
            'ended_at': self.ended_at
        }


@dataclass
class AgentResponse:
    """Contract: AgentResponse for capability execution results"""
    
    status: str  # "ok" or "error"
    result: Dict[str, Any]
    error: Optional[Error] = None
    idempotency_key: Optional[str] = None
    timing: Optional[Timing] = None
    
    def __post_init__(self):
        """Validate status"""
        if self.status not in ['ok', 'error']:
            raise ValueError(f"status must be 'ok' or 'error', got '{self.status}'")
        
        if self.status == 'error' and self.error is None:
            raise ValueError("error is required when status is 'error'")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        response = {
            'status': self.status,
            'result': self.result,
            'timing': self.timing.to_dict() if self.timing else None
        }
        
        if self.error:
            response['error'] = {
                'code': self.error.code,
                'message': self.error.message,
                'retryable': self.error.retryable
            }
        
        if self.idempotency_key:
            response['idempotency_key'] = self.idempotency_key
        
        return response
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentResponse':
        """Create AgentResponse from dict"""
        error = None
        if 'error' in data:
            error_data = data['error']
            error = Error(
                code=error_data['code'],
                message=error_data['message'],
                retryable=error_data.get('retryable', False)
            )
        
        timing = None
        if 'timing' in data and data['timing']:
            timing_data = data['timing']
            timing = Timing(
                started_at=timing_data['started_at'],
                ended_at=timing_data['ended_at']
            )
        
        return cls(
            status=data['status'],
            result=data.get('result', {}),
            error=error,
            idempotency_key=data.get('idempotency_key'),
            timing=timing
        )
    
    @classmethod
    def success(cls, result: Dict[str, Any], idempotency_key: Optional[str] = None, 
                timing: Optional[Timing] = None) -> 'AgentResponse':
        """Create successful response"""
        if timing is None:
            timing = Timing.create()
        
        return cls(
            status='ok',
            result=result,
            idempotency_key=idempotency_key,
            timing=timing
        )
    
    @classmethod
    def failure(cls, error_code: str, error_message: str, retryable: bool = False,
                result: Optional[Dict[str, Any]] = None,
                idempotency_key: Optional[str] = None,
                timing: Optional[Timing] = None) -> 'AgentResponse':
        """Create error response"""
        if timing is None:
            timing = Timing.create()
        
        return cls(
            status='error',
            result=result or {},
            error=Error(code=error_code, message=error_message, retryable=retryable),
            idempotency_key=idempotency_key,
            timing=timing
        )

