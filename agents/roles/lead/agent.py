#!/usr/bin/env python3
"""
Lead Agent - Governance Role
Reasoning Style: Governance
Memory Structure: Task state log
Task Model: Approval/escalation
Local Model: LLaMA 3 13B (mocked)
Premium Consultation: Strategic resolution
"""

import asyncio
import logging
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from agents.base_agent import BaseAgent, AgentMessage
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse, Timing
from agents.specs.validator import SchemaValidator
# Capabilities are now loaded via CapabilityLoader - no direct imports needed

logger = logging.getLogger(__name__)

class LeadAgent(BaseAgent):
    """Lead Agent - The Governance Role"""
    
    def __init__(self, identity: str, instances_file: str = "agents/instances/instances.yaml"):
        super().__init__(
            name=identity,
            agent_type="governance",
            reasoning_style="governance"
        )
        self.task_state_log = []
        self.approval_queue = []
        self.instances_file = instances_file
        self._role_to_agent_cache = None
        self.communication_log = []
        
        # WarmBoot state tracking for three-task sequence
        self.warmboot_state = {
            'manifest': None,
            'build_files': [],
            'pending_tasks': []
        }
        # Import configuration
        import sys
        sys.path.append('/app')
        from config.agent_config import get_complexity_threshold
        
        self.escalation_threshold = get_complexity_threshold("escalation")
        
        # Initialize schema validator using unified path resolver
        from agents.utils.path_resolver import PathResolver
        base_path = PathResolver.get_base_path()
        self.validator = SchemaValidator(base_path)
        
        # Capability loader is initialized in BaseAgent._load_capability_config()
        # Use self.capability_loader to resolve and execute capabilities
    
    async def handle_agent_request(self, request: AgentRequest) -> AgentResponse:
        """Handle agent request using capability-based routing"""
        started_at = datetime.utcnow()
        
        try:
            # Validate request
            is_valid, error_msg = self.validator.validate_request(request)
            if not is_valid:
                return AgentResponse.failure(
                    error_code="VALIDATION_ERROR",
                    error_message=error_msg or "Request validation failed",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            
            # Validate constraints
            is_valid, error_msg = self._validate_constraints(request)
            if not is_valid:
                return AgentResponse.failure(
                    error_code="POLICY_VIOLATION",
                    error_message=error_msg or "Constraint validation failed",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            
            # Generate idempotency key
            idempotency_key = request.generate_idempotency_key(self.name)
            
            # Route to capability via Loader
            action = request.action
            if not self.capability_loader:
                return AgentResponse.failure(
                    error_code="LOADER_NOT_INITIALIZED",
                    error_message="Capability loader not initialized",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            
            try:
                # Execute capability via Loader - fully generic routing
                # Use calling convention metadata to determine how to call the capability
                args = self.capability_loader.prepare_capability_args(action, request.payload, request.metadata)
                result = await self.capability_loader.execute(action, self, *args)
            except ValueError:
                # Capability not found in Loader
                return AgentResponse.failure(
                    error_code="UNKNOWN_CAPABILITY",
                    error_message=f"Unknown capability: {action}",
                    retryable=False,
                    timing=Timing.create(started_at)
                )
            except Exception as e:
                logger.error(f"{self.name}: Capability execution error: {e}", exc_info=True)
                return AgentResponse.failure(
                    error_code="CAPABILITY_EXECUTION_ERROR",
                    error_message=str(e),
                    retryable=True,
                    timing=Timing.create(started_at)
                )
            
            # Validate result keys
            is_valid, error_msg = self.validator.validate_result_keys(action, result)
            if not is_valid:
                logger.warning(f"{self.name}: Result validation warning: {error_msg}")
            
            # Create success response
            ended_at = datetime.utcnow()
            return AgentResponse.success(
                result=result,
                idempotency_key=idempotency_key,
                timing=Timing.create(started_at, ended_at)
            )
            
        except Exception as e:
            logger.error(f"{self.name}: Error handling request: {e}", exc_info=True)
            return AgentResponse.failure(
                error_code="INTERNAL_ERROR",
                error_message=str(e),
                retryable=True,
                timing=Timing.create(started_at)
            )
    
    # Handler methods removed - capabilities are now executed via Loader
    # Duplicate logic has been moved to capability classes
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process tasks using generic capability routing.
        
        Uses CapabilityLoader.get_capability_for_task() to determine capability
        based on task_type or requirements.action, then executes it generically.
        """
        logger.debug(f"{self.name} process_task START - task: {task}")
        
        # Check if this is a new SIP-046 AgentRequest format
        if 'action' in task:
            # Let BaseAgent handle the conversion to AgentRequest
            return await super().process_task(task)
        
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('task_type') or task.get('type', 'unknown')
        
        logger.info(f"{self.name} processing {task_type} task: {task_id}")
        
        # Load relevant memories for WarmBoot context (SIP-042) via Loader
        ecid = task.get('ecid') or task.get('context', {}).get('ecid')
        pid = task.get('pid') or task.get('context', {}).get('pid')
        if (ecid or pid) and self.capability_loader:
            try:
                await self.capability_loader.execute('warmboot.memory', self, ecid, pid)
            except Exception as e:
                logger.warning(f"{self.name}: Failed to load WarmBoot memories: {e}")
        
        # Generic capability routing via loader
        if not self.capability_loader:
            logger.error(f"{self.name}: Capability loader not initialized")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': 'Capability loader not initialized'
            }
        
        # Determine capability from task structure
        capability_name = self.capability_loader.get_capability_for_task(task)
        if not capability_name:
            logger.warning(f"{self.name} received task with no capability mapping: {task_type}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': f'No capability mapping found for task type: {task_type}'
            }
        
        logger.info(f"{self.name} routing task {task_id} to capability: {capability_name}")
        
        # Update task status to in_progress
        await self.update_task_status(task_id, "Active-Non-Blocking", 25.0)
        
        try:
            # Generic capability execution - use calling convention metadata
            # This handles all calling conventions: task_dict, requirements_only, task_id_requirements, payload_as_is
            args = self.capability_loader.prepare_capability_args(capability_name, task)
            result = await self.capability_loader.execute(capability_name, self, *args)
            
            # Update task status to completed
            await self.update_task_status(task_id, "Completed", 100.0)
            
            # Return result (capabilities return their own result format)
            return result
                
        except ValueError as e:
            # Capability not found
            logger.error(f"{self.name}: Capability not found: {e}")
            await self.update_task_status(task_id, "Failed", 0.0, str(e))
            return {
                'task_id': task_id,
                'status': 'error',
                'error': f'Capability not found: {e}'
            }
        except Exception as e:
            logger.error(f"{self.name}: Capability execution error: {e}", exc_info=True)
            await self.update_task_status(task_id, "Failed", 0.0, str(e))
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e)
            }
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle governance-related messages"""
        if message.message_type == "approval_request":
            await self.handle_approval_request(message)
        elif message.message_type == "escalation":
            await self.handle_escalation(message)
        elif message.message_type == "status_query":
            await self.handle_status_query(message)
        elif message.message_type == "task_acknowledgment":
            await self.handle_task_acknowledgment(message)
        elif message.message_type == "task_error":
            await self.handle_task_error(message)
        elif message.message_type == "prd_request":
            await self.handle_prd_request(message)
        elif message.message_type == "task.developer.completed":
            await self.handle_developer_completion(message)
        elif message.message_type == "agent_reasoning":
            await self.handle_reasoning_event(message)
        elif message.message_type == "task_delegation":
            await self.handle_task_delegation(message)
        else:
            logger.info(f"{self.name} received message: {message.message_type} from {message.sender}")
    
    async def handle_prd_request(self, message: AgentMessage) -> None:
        """Handle PRD processing requests - routes to prd.process capability via process_task"""
        # Convert message payload to task (payload should already contain required fields)
        # If payload doesn't have task_id, generate one
        task = message.payload.copy()
        if 'task_id' not in task:
            ecid = task.get('ecid') or message.context.get('ecid', 'ECID-WB-001')
            task['task_id'] = f"{ecid}-prd-{int(__import__('time').time())}"
        
        # Merge context fields into task if needed
        if 'ecid' not in task:
            task['ecid'] = message.context.get('ecid', 'ECID-WB-001')
        
        logger.info(f"{self.name} handling PRD request: task_id={task.get('task_id', 'unknown')}")
        
        # Process via generic routing (capability loader will determine capability from task structure)
        result = await self.process_task(task)
        
        # Send response back to requester
        await self.send_message(
            recipient=message.sender,
            message_type="prd_response",
            payload=result,
            context={
                'original_request': message.payload,
                'processed_by': self.name
            }
        )
    
    async def handle_task_acknowledgment(self, message: AgentMessage) -> None:
        """Handle task acknowledgment from delegated agents"""
        payload = message.payload
        task_id = payload.get('task_id', 'unknown')
        understanding = payload.get('understanding', '')
        
        logger.info(f"{self.name} received task acknowledgment: {task_id} from {message.sender}")
        logger.info(f"Agent understanding: {understanding[:200]}...")
        
        # Log the successful communication
        self.communication_log.append({
            'task_id': task_id,
            'from_agent': message.sender,
            'to_agent': self.name,
            'message_type': 'task_acknowledgment',
            'timestamp': message.timestamp,
            'status': 'success',
            'understanding': understanding
        })

    async def handle_task_error(self, message: AgentMessage) -> None:
        """Handle task error from delegated agents"""
        payload = message.payload
        task_id = payload.get('task_id', 'unknown')
        error = payload.get('error', 'Unknown error')
        
        logger.error(f"{self.name} received task error: {task_id} from {message.sender}: {error}")
        
        # Log the error
        self.communication_log.append({
            'task_id': task_id,
            'from_agent': message.sender,
            'to_agent': self.name,
            'message_type': 'task_error',
            'timestamp': message.timestamp,
            'status': 'error',
            'error': error
        })
    
    async def handle_reasoning_event(self, message: AgentMessage) -> None:
        """
        Handle reasoning event from other agents (DevAgent, etc.)
        Stores reasoning events in communication log for wrap-up generation
        """
        try:
            payload = message.payload
            context = message.context
            sender = message.sender
            
            # Extract reasoning event data
            reasoning_data = {
                'timestamp': message.timestamp,
                'sender': sender,
                'agent': context.get('sender_agent', sender),
                'message_type': 'agent_reasoning',
                'ecid': payload.get('ecid', context.get('ecid', 'unknown')),
                'task_id': payload.get('task_id', 'unknown'),
                'reason_step': payload.get('reason_step', 'unknown'),
                'summary': payload.get('summary', ''),
                'context': payload.get('context', 'unknown'),
                'key_points': payload.get('key_points', []),
                'confidence': payload.get('confidence'),
                'schema': payload.get('schema', 'reasoning.v1'),
                'raw_reasoning_included': payload.get('raw_reasoning_included', False)
            }
            
            # Store in communication log for wrap-up extraction
            self.communication_log.append(reasoning_data)
            
            logger.info(f"{self.name} received reasoning event from {sender}: {payload.get('reason_step', 'unknown')} for {payload.get('context', 'unknown')} (ECID: {payload.get('ecid', 'unknown')})")
            
        except Exception as e:
            logger.warning(f"{self.name} failed to handle reasoning event: {e}")
    
    async def handle_task_delegation(self, message: AgentMessage) -> None:
        """Handle task delegation messages - routes to generic process_task"""
        try:
            task_payload = message.payload
            task_id = task_payload.get('task_id', 'unknown')
            task_type = task_payload.get('task_type', 'unknown')
            
            logger.info(f"{self.name} received task delegation: {task_id} (type: {task_type}) from {message.sender}")
            
            # Update task status to in_progress
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.put(
                        f"{self.task_api_url}/api/v1/tasks/{task_id}",
                        json={"status": "in_progress"}
                    ) as resp:
                        if resp.status == 200:
                            logger.info(f"{self.name} marked task {task_id} as in_progress")
                        elif resp.status == 404:
                            # Task doesn't exist, log it
                            ecid = task_payload.get('ecid', 'unknown')
                            await self.log_task_start(task_id, ecid, 
                                task_payload.get('description', 'Unknown task'),
                                task_payload.get('priority', 'MEDIUM'))
                        else:
                            logger.warning(f"Failed to update task status: {await resp.text()}")
            except Exception as e:
                logger.warning(f"Failed to update task {task_id}: {e}, continuing anyway")
            
            # Process the delegated task via generic capability routing
            result = await self.process_task(task_payload)
            
            logger.info(f"{self.name} completed delegated task {task_id}: {result.get('status', 'unknown')}")
            
        except Exception as e:
            logger.error(f"{self.name} failed to handle task delegation: {e}", exc_info=True)
    
    async def handle_developer_completion(self, message: AgentMessage) -> None:
        """
        Handle developer completion event (SIP-027 Phase 1)
        When Neo completes development tasks, trigger WarmBoot wrap-up generation
        
        Delegates to task.completion.handle capability via Loader.
        """
        try:
            payload = message.payload
            context = message.context
            if not self.capability_loader:
                logger.error(f"{self.name}: Capability loader not initialized")
                return
            await self.capability_loader.execute('task.completion.handle', self, payload, context)
        except Exception as e:
            logger.error(f"{self.name} failed to handle developer completion: {e}")

    async def escalate_task(self, task_id: str, task: Dict[str, Any]):
        """Escalate task to premium consultation"""
        self.approval_queue.append({
            'task_id': task_id,
            'task': task,
            'escalation_time': task.get('timestamp'),
            'reason': 'High complexity'
        })
        
        # Log to communication log (deprecated log_activity may fail in integration tests)
        self.communication_log.append({
            'event': 'task_escalated',
            'task_id': task_id,
            'complexity': task.get('complexity'),
            'reason': 'Premium consultation required',
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Record memory for governance decision (escalation)
        await self.record_memory(
            kind="governance_decision",
            payload={
                'task_id': task_id,
                'decision_type': 'escalation',
                'complexity': task.get('complexity'),
                'reason': 'Premium consultation required'
            },
            importance=0.8,
            task_context=task
        )
        
        # Try deprecated log_activity (gracefully handles missing table)
        await self.log_activity("task_escalated", {
            'task_id': task_id,
            'complexity': task.get('complexity'),
            'reason': 'Premium consultation required'
        })
    
    def _load_role_to_agent_mapping(self) -> Dict[str, str]:
        """
        Load role-to-agent mapping from instances.yaml.
        Returns dict mapping role -> agent_id for enabled agents.
        Caches result for performance.
        """
        if self._role_to_agent_cache is not None:
            return self._role_to_agent_cache
        
        try:
            instances_path = Path(self.instances_file)
            if not instances_path.exists():
                logger.warning(f"Instances file not found: {self.instances_file}, using defaults")
                return self._get_default_role_mapping()
            
            with open(instances_path, 'r') as f:
                data = yaml.safe_load(f)
            
            # Build role -> agent_id mapping from enabled instances
            role_to_agent = {}
            for instance in data.get('instances', []):
                if instance.get('enabled', False):
                    role = instance.get('role')
                    agent_id = instance.get('id')
                    if role and agent_id:
                        # If multiple agents have same role, keep first (TODO: add load balancing)
                        if role not in role_to_agent:
                            role_to_agent[role] = agent_id
            
            self._role_to_agent_cache = role_to_agent
            logger.info(f"Loaded role-to-agent mapping: {role_to_agent}")
            return role_to_agent
            
        except Exception as e:
            logger.error(f"Failed to load instances.yaml: {e}, using defaults")
            return self._get_default_role_mapping()
    
    def _get_default_role_mapping(self) -> Dict[str, str]:
        """Fallback role-to-agent mapping if instances.yaml can't be loaded"""
        return {
            'lead': 'max',
            'dev': 'neo',
            'strat': 'nat',
            'qa': 'eve',
            'data': 'data',
            'finance': 'quark',
            'creative': 'glyph',
            'comms': 'joi',
            'curator': 'og',
            'audit': 'hal'
        }
    
    
    async def handle_approval_request(self, message: AgentMessage):
        """Handle approval requests from other agents"""
        task_id = message.payload.get('task_id')
        logger.info(f"{self.name} handling approval request for task: {task_id}")
        
        # Mock approval logic
        approved = True  # Simplified for stub
        
        await self.send_message(
            message.sender,
            "approval_response",
            {
                'task_id': task_id,
                'approved': approved,
                'governance_notes': f'Approved by {self.name} governance agent'
            }
        )
    
    async def handle_escalation(self, message: AgentMessage):
        """Handle escalation requests"""
        task_id = message.payload.get('task_id')
        reason = message.payload.get('reason', 'Unknown')
        
        logger.info(f"{self.name} handling escalation for task: {task_id}, reason: {reason}")
        
        # Log to communication log (deprecated log_activity may fail in integration tests)
        self.communication_log.append({
            'event': 'escalation_received',
            'task_id': task_id,
            'from_agent': message.sender,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Try deprecated log_activity (gracefully handles missing table)
        await self.log_activity("escalation_received", {
            'task_id': task_id,
            'from_agent': message.sender,
            'reason': reason
        })
    
    async def handle_status_query(self, message: AgentMessage):
        """Handle status queries"""
        await self.send_message(
            message.sender,
            "status_response",
            {
                'agent': self.name,
                'status': self.status,
                'current_task': self.current_task,
                'task_state_log_count': len(self.task_state_log),
                'approval_queue_count': len(self.approval_queue)
            }
        )
    

async def main():
    """Main entry point for Lead agent"""
    from config.unified_config import get_config
    config = get_config()
    identity = config.get_agent_id()
    agent = LeadAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
