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
import json
import logging
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from base_agent import BaseAgent, AgentMessage
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse, Error, Timing
from agents.specs.validator import SchemaValidator
from agents.capabilities.telemetry_collector import TelemetryCollector
from agents.capabilities.prd_processor import PRDReader, PRDAnalyzer
from agents.capabilities.task_delegator import TaskDelegator
from agents.capabilities.wrapup_generator import WrapupGenerator
from agents.capabilities.build_requirements_generator import BuildRequirementsGenerator
from agents.capabilities.task_creator import TaskCreator
from agents.capabilities.task_completion_handler import TaskCompletionHandler
from agents.capabilities.warmboot_memory_handler import WarmBootMemoryHandler

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
        import os
        sys.path.append('/app')
        from config.agent_config import get_complexity_threshold
        
        self.escalation_threshold = get_complexity_threshold("escalation")
        
        # Initialize schema validator
        from pathlib import Path
        # In container, agent.py is at /app/agent.py, so base_path should be /app
        # In development, __file__ is at agents/roles/lead/agent.py, so go up 3 levels
        if Path('/app').exists():
            base_path = Path('/app')
        else:
            base_path = Path(__file__).parent.parent.parent.parent
        self.validator = SchemaValidator(base_path)
        
        # Initialize capability handlers
        self.telemetry_collector = TelemetryCollector(self)
        self.prd_reader = PRDReader(self)
        self.prd_analyzer = PRDAnalyzer(self)
        self.task_delegator = TaskDelegator(self)
        self.wrapup_generator = WrapupGenerator(self)
        self.build_requirements_generator = BuildRequirementsGenerator(self)
        self.task_creator = TaskCreator(self)
        # Link task creator to build requirements generator
        self.task_creator.set_build_requirements_generator(self.build_requirements_generator)
        self.task_completion_handler = TaskCompletionHandler(self)
        self.warmboot_memory_handler = WarmBootMemoryHandler(self)
    
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
            
            # Route to capability handler
            action = request.action
            if action == "validate.warmboot":
                result = await self._handle_validate_warmboot(request)
            elif action == "governance.task_coordination":
                result = await self._handle_task_coordination(request)
            elif action == "governance.approval":
                result = await self._handle_approval(request)
            elif action == "governance.escalation":
                result = await self._handle_escalation(request)
            else:
                return AgentResponse.failure(
                    error_code="UNKNOWN_CAPABILITY",
                    error_message=f"Unknown capability: {action}",
                    retryable=False,
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
    
    async def _handle_validate_warmboot(self, request: AgentRequest) -> Dict[str, Any]:
        """Handle validate.warmboot capability - processes WarmBoot requests"""
        payload = request.payload
        ecid = request.metadata.get('ecid', 'unknown')
        pid = request.metadata.get('pid', 'unknown')
        
        # Convert AgentRequest to old task format for compatibility with existing process_task logic
        # This allows us to reuse the existing WarmBoot processing code
        task = {
            'task_id': payload.get('task_id', f"{ecid}-main"),
            'type': 'governance',
            'ecid': ecid,
            'pid': pid,
            'application': payload.get('application'),
            'request_type': payload.get('request_type'),
            'agents': payload.get('agents', []),
            'priority': payload.get('priority', 'MEDIUM'),
            'description': payload.get('description'),
            'requirements': payload.get('requirements'),
            'prd_path': payload.get('prd_path')
        }
        
        # Process the WarmBoot request using existing logic
        result = await self.process_task(task)
        
        # Convert result to validate.warmboot capability format
        # The process_task result will have task completion info
        # We need to extract the wrap-up info if available
        return {
            'match': result.get('status') == 'completed',
            'diffs': result.get('diffs', []),
            'wrap_up_uri': result.get('wrap_up_uri', f'/warm-boot/runs/{ecid}/wrap-up.md'),
            'metrics': result.get('metrics', {})
        }
    
    async def _handle_task_coordination(self, request: AgentRequest) -> Dict[str, Any]:
        """Handle governance.task_coordination capability"""
        payload = request.payload
        task_type = payload.get('type', 'unknown')
        
        # Determine delegation target
        delegation_result = await self.task_delegator.determine_target(task_type)
        delegation_target = delegation_result.get('target_agent', 'dev-agent')
        
        # Delegate task
        await self.send_message(
            recipient=delegation_target,
            message_type="task_delegation",
            payload=payload,
            context=request.metadata
        )
        
        return {
            'tasks_created': 1,
            'tasks_delegated': 1,
            'coordination_log': f"Delegated {task_type} to {delegation_target}"
        }
    
    async def _handle_approval(self, request: AgentRequest) -> Dict[str, Any]:
        """Handle governance.approval capability"""
        payload = request.payload
        complexity = payload.get('complexity', 0.5)
        
        if complexity > self.escalation_threshold:
            return {
                'approved': False,
                'decision': 'escalated',
                'approval_time': 0.0
            }
        
        return {
            'approved': True,
            'decision': 'approved',
            'approval_time': 0.5
        }
    
    async def _handle_escalation(self, request: AgentRequest) -> Dict[str, Any]:
        """Handle governance.escalation capability"""
        payload = request.payload
        task_id = payload.get('task_id', 'unknown')
        
        await self.escalate_task(task_id, payload)
        
        return {
            'escalated': True,
            'resolution': 'escalated_to_premium',
            'escalation_time': 1.0
        }
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process governance tasks with approval/escalation logic"""
        logger.debug(f"{self.name} process_task START - task: {task}")
        
        # Check if this is a new SIP-046 AgentRequest format
        if 'action' in task:
            # Let BaseAgent handle the conversion to AgentRequest
            return await super().process_task(task)
        
        # Old format handling
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', 'unknown')
        complexity = task.get('complexity', 0.5)
        
        logger.debug(f"{self.name} parsed task_id={task_id}, task_type={task_type}, complexity={complexity}")
        logger.info(f"{self.name} processing governance task: {task_id}")
        logger.info(f"{self.name} DEBUG: task_type='{task_type}', has_prd_path={bool(task.get('prd_path'))}")
        
        # Load relevant memories for WarmBoot context (SIP-042)
        ecid = task.get('ecid') or task.get('context', {}).get('ecid')
        pid = task.get('pid') or task.get('context', {}).get('pid')
        if ecid or pid:
            await self.warmboot_memory_handler.load_memories(ecid, pid)
        
        # Check if this is a governance task with PRD path
        if task_type == "governance" and task.get('prd_path'):
            logger.debug(f"{self.name} handling governance task with PRD path")
            prd_path = task.get('prd_path', '')
            application = task.get('application', 'Application')
            
            if prd_path:
                logger.info(f"{self.name} processing PRD from path: {prd_path}")
                # Get ecid from the task
                ecid = task.get('ecid', 'ECID-WB-001')
                # Process PRD from file path
                result = await self.process_prd_request(prd_path, ecid)
                await self.update_task_status(task_id, "Completed", 100.0)
                return result
            else:
                logger.warning(f"{self.name} received empty PRD path for application: {application}")
                # Continue with normal governance processing
        
        # Log task state
        self.task_state_log.append({
            'task_id': task_id,
            'timestamp': task.get('timestamp'),
            'type': task_type,
            'complexity': complexity,
            'status': 'processing'
        })
        
        # Update task status
        logger.debug(f"{self.name} about to call update_task_status with task_id={task_id}")
        await self.update_task_status(task_id, "Active-Non-Blocking", 25.0)
        logger.debug(f"{self.name} update_task_status completed successfully")
        
        # Governance decision logic
        if complexity > self.escalation_threshold:
            logger.debug(f"{self.name} escalating task due to high complexity: {complexity} > {self.escalation_threshold}")
            # Escalate to premium consultation
            await self.escalate_task(task_id, task)
            logger.debug(f"{self.name} escalate_task completed")
            await self.update_task_status(task_id, "Blocked", 50.0, "Escalated to premium consultation")
            logger.debug(f"{self.name} update_task_status (escalated) completed")
            
            return {
                'task_id': task_id,
                'status': 'escalated',
                'reason': 'High complexity requires premium consultation',
                'escalation_level': 'strategic_resolution'
            }
        else:
            logger.debug(f"{self.name} approving task for delegation (complexity: {complexity} <= {self.escalation_threshold})")
            logger.info(f"{self.name} DEBUG: task_type='{task_type}', task_type.lower()='{task_type.lower()}'")
            
            # Governance tasks should be handled directly by Max, not delegated
            if task_type.lower() == 'governance':
                logger.info(f"{self.name} handling governance task directly: {task_id}")
                await self.update_task_status(task_id, "Completed", 100.0)
                return {
                    'task_id': task_id,
                    'status': 'completed',
                    'governance_decision': f"Governance task {task_id} handled directly by {self.name}",
                    'message': 'Governance tasks are handled directly by the Lead Agent'
                }
            
            logger.info(f"{self.name} DEBUG: Not a governance task, proceeding with delegation for task_type='{task_type}'")
            
            # Approve and delegate non-governance tasks
            await self.update_task_status(task_id, "Active-Non-Blocking", 75.0)
            logger.debug(f"{self.name} update_task_status (delegation) completed")
            
            # Determine delegation target
            delegation_result = await self.task_delegator.determine_target(task_type)
            delegation_target = delegation_result.get('target_agent', 'dev-agent')
            logger.debug(f"{self.name} determined delegation_target: {delegation_target}")
            
            # Send message to delegation target
            await self.send_message(
                recipient=delegation_target,
                message_type="task_delegation",
                payload={
                    'task_id': task_id,
                    'task_type': task_type,
                    'description': task.get('description', ''),
                    'requirements': task.get('requirements', {}),
                    'complexity': complexity,
                    'priority': task.get('priority', 'MEDIUM')
                },
                context={
                    'delegated_by': self.name,
                    'delegation_reason': f"Approved {task_type} for delegation",
                    'original_task': task
                }
            )
            
            await self.update_task_status(task_id, "Completed", 100.0)
            
            # Record memory for task delegation
            await self.record_memory(
                kind="task_delegation",
                payload={
                    'task_id': task_id,
                    'task_type': task_type,
                    'delegated_to': delegation_target,
                    'decision': 'approved',
                    'complexity': complexity
                },
                importance=0.7,
                task_context=task
            )
            
            return {
                'task_id': task_id,
                'status': 'approved',
                'delegation_target': delegation_target,
                'governance_decision': f"Approved {task_type} for delegation"
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
        else:
            logger.info(f"{self.name} received message: {message.message_type} from {message.sender}")
    
    async def handle_prd_request(self, message: AgentMessage) -> None:
        """Handle PRD processing requests"""
        prd_path = message.payload.get('prd_path', '')
        if not prd_path:
            logger.error("Max received PRD request without prd_path")
            return
        
        logger.info(f"{self.name} handling PRD request: {prd_path}")
        
        # Process the PRD
        result = await self.process_prd_request(prd_path)
        
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
        status = payload.get('status', 'unknown')
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
    
    async def handle_developer_completion(self, message: AgentMessage) -> None:
        """
        Handle developer completion event (SIP-027 Phase 1)
        When Neo completes development tasks, trigger WarmBoot wrap-up generation
        
        Delegates to task.completion.handle capability.
        """
        try:
            payload = message.payload
            context = message.context
            await self.task_completion_handler.handle_completion(payload, context)
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
    
    
    
    async def process_prd_request(self, prd_path: str, ecid: str = None) -> Dict[str, Any]:
        """Process a PRD request - read PRD, analyze, and create tasks"""
        try:
            logger.info(f"{self.name} processing PRD request: {prd_path}")
            
            # Use provided ecid or create default
            if not ecid:
                ecid = "ECID-WB-001"
            
            # Create execution cycle (Max owns the execution cycle lifecycle)
            try:
                await self.create_execution_cycle(ecid, "PID-001", "warmboot", 
                                                 f"WarmBoot {ecid}", prd_path)
                logger.info(f"{self.name} created execution cycle {ecid}")
            except Exception as e:
                # Execution cycle may already exist in edge cases - continue anyway
                logger.warning(f"Execution cycle {ecid} creation failed (may already exist): {e}")
            
            # Store the current ecid for use in create_development_tasks
            self.current_ecid = ecid
            logger.info(f"{self.name} stored current ecid: {ecid}")
            
            # Read PRD via capability
            prd_result = await self.prd_reader.read(prd_path)
            prd_content = prd_result.get('prd_content', '')
            if not prd_content:
                return {"status": "error", "message": "Failed to read PRD"}
            
            # Analyze PRD requirements via capability
            prd_analysis = await self.prd_analyzer.analyze(prd_content, agent_role="Max, the Lead Agent")
            if not prd_analysis:
                return {"status": "error", "message": "Failed to analyze PRD"}
            
            # Extract app name from PRD path or content
            app_name = "Application"  # Default fallback
            if "prd-" in prd_path.lower():
                # Extract app name from PRD filename (e.g., "PRD-001-HelloSquad.md" -> "HelloSquad")
                import re
                match = re.search(r'PRD-\d+-(.+)\.md', prd_path)
                if match:
                    app_name = match.group(1)
            
            # Create development tasks via capability
            task_result = await self.task_creator.create(prd_analysis, app_name, ecid)
            tasks = task_result.get('tasks', [])
            if not tasks:
                return {"status": "error", "message": "Failed to create tasks"}
            
            # Delegate tasks to Neo
            delegated_tasks = []
            for task in tasks:
                # For build tasks, inject manifest from warmboot_state if available
                if task.get('requirements', {}).get('action') == 'build':
                    if task['requirements'].get('manifest') is None and self.warmboot_state.get('manifest'):
                        task['requirements']['manifest'] = self.warmboot_state['manifest']
                        logger.info(f"{self.name} injected manifest into build task {task['task_id']}")
                    elif task['requirements'].get('manifest') is None:
                        # Build task without manifest - skip for now, will be delegated after design manifest completes
                        logger.info(f"{self.name} skipping build task {task['task_id']} - manifest not yet available")
                        continue
                
                delegation_result = await self.task_delegator.determine_target(task["task_type"])
                delegation_target = delegation_result.get('target_agent', 'dev-agent')
                
                # Log task delegation
                await self.log_task_delegation(
                    task['task_id'],
                    ecid,
                    delegation_target,
                    task['description']
                )
                
                await self.send_message(
                    recipient=delegation_target,
                    message_type="task_delegation",
                    payload=task,
                    context={
                        'delegated_by': self.name,
                        'delegation_reason': f"PRD-based task: {task['description']}",
                        'prd_path': prd_path,
                        'prd_analysis': prd_analysis
                    }
                )
                
                # Record memory for task delegation (SIP-042)
                await self.record_memory(
                    kind="task_delegation",
                    payload={
                        'task_id': task['task_id'],
                        'task_type': task.get('task_type', 'unknown'),
                        'delegated_to': delegation_target,
                        'decision': 'approved',
                        'ecid': ecid
                    },
                    importance=0.7,
                    task_context={'ecid': ecid, 'pid': task.get('pid', 'unknown')}
                )
                
                delegated_tasks.append({
                    'task_id': task['task_id'],
                    'delegated_to': delegation_target,
                    'status': 'delegated'
                })
            
            logger.info(f"{self.name} successfully processed PRD and delegated {len(delegated_tasks)} tasks")
            
            return {
                "status": "success",
                "message": f"PRD processed and {len(delegated_tasks)} tasks delegated",
                "prd_path": prd_path,
                "tasks_delegated": delegated_tasks,
                "prd_analysis": prd_analysis
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to process PRD request: {e}")
            return {"status": "error", "message": f"PRD processing failed: {e}"}

async def main():
    """Main entry point for Lead agent"""
    import os
    from config.unified_config import get_config
    config = get_config()
    identity = config.get_agent_id()
    agent = LeadAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
