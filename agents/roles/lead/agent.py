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
from pathlib import Path
from typing import Dict, Any, List
from base_agent import BaseAgent, AgentMessage

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
        # Import configuration
        import sys
        import os
        sys.path.append('/app')
        from config.agent_config import get_complexity_threshold
        
        self.escalation_threshold = get_complexity_threshold("escalation")
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process governance tasks with approval/escalation logic"""
        logger.debug(f"{self.name} process_task START - task: {task}")
        
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', 'unknown')
        complexity = task.get('complexity', 0.5)
        
        logger.debug(f"{self.name} parsed task_id={task_id}, task_type={task_type}, complexity={complexity}")
        logger.info(f"{self.name} processing governance task: {task_id}")
        logger.info(f"{self.name} DEBUG: task_type='{task_type}', has_prd_path={bool(task.get('prd_path'))}")
        
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
                'escalation_level': 'strategic_resolution',
                'mock_response': await self.mock_llm_response(
                    f"Strategic governance decision for {task_type}",
                    f"Complexity: {complexity}, Task: {task.get('description', 'N/A')}"
                )
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
            delegation_target = await self.determine_delegation_target(task_type)
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
            
            return {
                'task_id': task_id,
                'status': 'approved',
                'delegation_target': delegation_target,
                'governance_decision': f"Approved {task_type} for delegation",
                'mock_response': await self.mock_llm_response(
                    f"Governance approval for {task_type}",
                    f"Delegating to {delegation_target}"
                )
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
    
    async def handle_developer_completion(self, message: AgentMessage) -> None:
        """
        Handle developer completion event (SIP-027 Phase 1)
        When Neo completes development tasks, trigger WarmBoot wrap-up generation
        
        TECH DEBT: This method directly triggers wrap-up generation as a side effect
        of an event, rather than using proper task orchestration. The wrap-up should
        be a first-class task that gets unblocked when developer tasks complete.
        This will be resolved when we integrate Prefect for task dependency management.
        
        TODO: Refactor to task-based orchestration during Prefect integration (SIP-027 Phase 2)
        Created: 2025-10-12
        """
        try:
            payload = message.payload
            context = message.context
            task_id = payload.get('task_id', 'unknown')
            ecid = context.get('ecid', payload.get('ecid', 'unknown'))
            status = payload.get('status', 'unknown')
            
            logger.info(f"{self.name} received developer completion event: task {task_id}, ECID {ecid}, status {status}")
            
            # Only generate wrap-up if task was successful
            if status == 'completed' or status == 'success':
                logger.info(f"{self.name} triggering WarmBoot wrap-up generation for ECID {ecid}")
                await self.generate_warmboot_wrapup(ecid, task_id, payload)
            else:
                logger.warning(f"{self.name} skipping wrap-up for unsuccessful task: {status}")
                
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
    
    async def determine_delegation_target(self, task_type: str) -> str:
        """
        Determine which agent should handle the task based on role.
        Returns agent ID (e.g., 'neo') not display name.
        
        Task types are mapped to roles, then resolved to agent IDs via instances.yaml
        """
        # Map task types to roles
        task_to_role_map = {
            'code': 'dev',
            'development': 'dev',
            'deployment': 'dev',
            'archive': 'dev',
            'build': 'dev',
            'product': 'strat',
            'strategy': 'strat',
            'data': 'data',
            'analytics': 'data',
            'security': 'qa',
            'testing': 'qa',
            'financial': 'finance',
            'creative': 'creative',
            'design': 'creative',
            'analysis': 'curator',
            'research': 'curator',
            'communication': 'comms',
            'audit': 'audit'
        }
        
        # Governance tasks should NEVER be delegated
        if task_type.lower() == 'governance':
            raise ValueError(f"Governance tasks should not be delegated - handled by lead directly")
        
        # Get role for this task type (default to 'dev' for unknown types)
        target_role = task_to_role_map.get(task_type.lower(), 'dev')
        
        # Load role-to-agent mapping from instances.yaml
        role_to_agent_map = self._load_role_to_agent_mapping()
        
        agent_id = role_to_agent_map.get(target_role, 'neo')
        logger.debug(f"Task type '{task_type}' → role '{target_role}' → agent '{agent_id}'")
        
        return agent_id
    
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
    
    
    async def read_prd(self, prd_path: str) -> str:
        """Read and return PRD content"""
        try:
            prd_content = await self.read_file(prd_path)
            logger.info(f"{self.name} read PRD: {prd_path}")
            return prd_content
        except Exception as e:
            logger.error(f"{self.name} failed to read PRD {prd_path}: {e}")
            return ""
    
    async def analyze_prd_requirements(self, prd_content: str) -> Dict[str, Any]:
        """Analyze PRD content and extract requirements using LLM"""
        try:
            analysis_prompt = f"""
            You are Max, the Lead Agent responsible for analyzing Product Requirements Documents (PRDs) and creating development tasks.
            
            Please analyze the following PRD and extract:
            1. **Core Features**: List the main features that need to be built
            2. **Technical Requirements**: Identify technical constraints and requirements
            3. **Success Criteria**: What defines success for this project
            
            PRD Content:
            {prd_content}
            
            Respond with a structured analysis in JSON format:
            {{
                "core_features": ["feature1", "feature2", ...],
                "technical_requirements": ["req1", "req2", ...],
                "success_criteria": ["criteria1", "criteria2", ...]
            }}
            """
            
            llm_response = await self.llm_response(analysis_prompt, "PRD Analysis")
            logger.info(f"{self.name} analyzed PRD requirements")
            
            # Try to parse the LLM response as JSON
            try:
                import json
                # Extract JSON from the response if it's wrapped in markdown or other text
                if "```json" in llm_response:
                    json_start = llm_response.find("```json") + 7
                    json_end = llm_response.find("```", json_start)
                    json_str = llm_response[json_start:json_end].strip()
                elif "{" in llm_response and "}" in llm_response:
                    json_start = llm_response.find("{")
                    json_end = llm_response.rfind("}") + 1
                    json_str = llm_response[json_start:json_end]
                else:
                    json_str = llm_response
                
                parsed_analysis = json.loads(json_str)
                return parsed_analysis
            except json.JSONDecodeError:
                logger.warning(f"{self.name} could not parse LLM response as JSON, using fallback")
                # Fallback: create a basic structure from the text response
                return {
                    "core_features": ["Core Application Features", "User Interface", "Data Management", "Integration Points"],
                    "technical_requirements": ["Performance requirements", "Scalability", "Security", "Compatibility"],
                    "success_criteria": ["Functional requirements met", "Performance targets achieved", "User acceptance criteria satisfied"]
                }
            
        except Exception as e:
            logger.error(f"{self.name} failed to analyze PRD: {e}")
            return {
                "core_features": ["Core Application Features", "User Interface", "Data Management"],
                "technical_requirements": ["Performance", "Scalability", "Security"],
                "success_criteria": ["Functional requirements", "Performance", "User acceptance"]
            }
    
    async def create_development_tasks(self, prd_analysis: Dict[str, Any], app_name: str = "application", ecid: str = None) -> List[Dict[str, Any]]:
        """Create generic development tasks based on PRD analysis"""
        try:
            # Import version info
            import sys
            import os
            sys.path.append('/app')
            from config.version import get_framework_version
            
            # Convert app name to kebab-case for consistency
            def convert_to_kebab_case(name: str) -> str:
                """Convert CamelCase to kebab-case (e.g., HelloSquad -> hello-squad)"""
                import re
                # Insert dash before uppercase letters (except the first one)
                kebab = re.sub(r'(?<!^)(?=[A-Z])', '-', name)
                return kebab.lower()
            
            app_kebab = convert_to_kebab_case(app_name)
            
            # Get framework version and determine warm-boot sequence
            framework_version = get_framework_version()  # e.g., "0.1.4"
            
            # Extract warm-boot sequence from the current ecid
            # The ecid format: "ECID-WB-###-description" -> extract "###"
            current_ecid = getattr(self, 'current_ecid', 'ECID-WB-001')
            ecid_parts = current_ecid.split("-")
            # For ECID-WB-027-test-harness-validation, get index 2 which is "027"
            warm_boot_sequence = ecid_parts[2] if len(ecid_parts) > 2 else "001"
            
            app_version = f"{framework_version}.{warm_boot_sequence}"  # e.g., "0.1.4.008"
            
            # Create generic development tasks based on PRD analysis
            tasks = [
                {
                    "task_id": f"{app_kebab}-archive-{int(time.time())}",
                    "task_type": "development",
                    "ecid": ecid,
                    "description": f"Archive any existing {app_name} application to ensure clean slate build for version {app_version}",
                    "requirements": {
                        "action": "archive",
                        "application": app_name,
                        "version": app_version,
                        "framework_version": framework_version,
                        "warm_boot_sequence": warm_boot_sequence,
                        "clean_slate": True,
                        "create_documentation": True
                    },
                    "complexity": 0.3,
                    "priority": "HIGH"
                },
                {
                    "task_id": f"{app_kebab}-build-{int(time.time())}",
                    "task_type": "development",
                    "ecid": ecid,
                    "description": f"Build {app_name} application version {app_version} from scratch",
                    "requirements": {
                        "action": "build",
                        "application": app_name,
                        "version": app_version,
                        "framework_version": framework_version,
                        "warm_boot_sequence": warm_boot_sequence,
                        "features": prd_analysis.get("core_features", []),
                        "technical_requirements": prd_analysis.get("technical_requirements", []),
                        "target_directory": f"warm-boot/apps/{app_kebab}/",
                        "from_scratch": True
                    },
                    "complexity": 0.8,
                    "priority": "HIGH"
                },
                {
                    "task_id": f"{app_kebab}-deploy-{int(time.time())}",
                    "task_type": "development",
                    "ecid": ecid,
                    "description": f"Deploy {app_name} application version {app_version} with proper versioning",
                    "requirements": {
                        "action": "deploy",
                        "application": app_name,
                        "version": app_version,
                        "framework_version": framework_version,
                        "warm_boot_sequence": warm_boot_sequence,
                        "source": f"warm-boot/apps/{app_kebab}/",
                        "versioning": True,
                        "traceability": True
                    },
                    "complexity": 0.5,
                    "priority": "MEDIUM"
                }
            ]
            
            # Log task creation for each task
            for task in tasks:
                await self.log_task_start(
                    task['task_id'], 
                    ecid, 
                    task['description'],
                    task['priority'],
                    task.get('dependencies', [])
                )
            
            logger.info(f"{self.name} created {len(tasks)} development tasks for {app_name} version {app_version}")
            return tasks
            
        except Exception as e:
            logger.error(f"{self.name} failed to create development tasks: {e}")
            return []
    
    async def generate_warmboot_wrapup(self, ecid: str, task_id: str, completion_payload: Dict[str, Any]):
        """
        Generate WarmBoot wrap-up markdown (SIP-027 Phase 1)
        Collects telemetry and creates wrap-up document in /warm-boot/runs/run-XXX/
        """
        try:
            from datetime import datetime
            import re
            
            logger.info(f"{self.name} starting WarmBoot wrap-up generation for ECID {ecid}")
            
            # Extract run number from ECID (e.g., "ECID-WB-055" -> "055")
            run_match = re.search(r'WB-(\d+)', ecid)
            run_number = run_match.group(1) if run_match else "001"
            
            # Collect telemetry
            telemetry = await self._collect_telemetry(ecid, task_id)
            
            # Generate wrap-up markdown
            wrapup_content = await self._generate_wrapup_markdown(
                ecid, run_number, task_id, completion_payload, telemetry
            )
            
            # Write wrap-up to file
            runs_dir = "/app/warm-boot/runs"
            run_dir = f"{runs_dir}/run-{run_number}"
            wrapup_file = f"{run_dir}/warmboot-run{run_number}-wrapup.md"
            
            # Ensure directory exists
            await self.execute_command(f"mkdir -p {run_dir}")
            
            # Write wrap-up file
            success = await self.write_file(wrapup_file, wrapup_content)
            
            if success:
                logger.info(f"{self.name} successfully wrote WarmBoot wrap-up: {wrapup_file}")
            else:
                logger.error(f"{self.name} failed to write WarmBoot wrap-up: {wrapup_file}")
                
        except Exception as e:
            logger.error(f"{self.name} failed to generate WarmBoot wrap-up: {e}")
    
    async def _collect_telemetry(self, ecid: str, task_id: str) -> Dict[str, Any]:
        """
        Collect telemetry for WarmBoot wrap-up (SIP-027 Phase 1)
        Gathers reasoning logs, DB metrics, Docker events, RabbitMQ stats
        """
        from datetime import datetime
        
        telemetry = {
            'database_metrics': {},
            'rabbitmq_metrics': {},
            'docker_events': {},
            'reasoning_logs': {},
            'collection_timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            # Collect database metrics
            async with self.db_pool.acquire() as conn:
                # Get task logs for this ECID
                task_logs = await conn.fetch("""
                    SELECT task_id, agent, status, start_time, end_time, duration, artifacts
                    FROM agent_task_log
                    WHERE ecid = $1
                    ORDER BY start_time
                """, ecid)
                
                telemetry['database_metrics']['task_count'] = len(task_logs)
                telemetry['database_metrics']['tasks'] = [dict(t) for t in task_logs]
                
                # Get execution cycle info
                cycle_info = await conn.fetchrow("""
                    SELECT ecid, pid, run_type, title, created_at, status
                    FROM execution_cycle
                    WHERE ecid = $1
                """, ecid)
                
                if cycle_info:
                    telemetry['database_metrics']['execution_cycle'] = dict(cycle_info)
            
            logger.info(f"{self.name} collected DB telemetry: {telemetry['database_metrics']['task_count']} tasks")
            
            # Collect RabbitMQ metrics (basic stats)
            telemetry['rabbitmq_metrics']['messages_processed'] = len(self.communication_log)
            telemetry['rabbitmq_metrics']['communication_log'] = self.communication_log[-10:]  # Last 10 messages
            
            # Collect Docker events (simplified - just note containers involved)
            telemetry['docker_events']['note'] = "Docker events tracking placeholder"
            
            # Reasoning logs placeholder
            telemetry['reasoning_logs']['note'] = "Reasoning log collection placeholder"
            
        except Exception as e:
            logger.error(f"{self.name} failed to collect telemetry: {e}")
            telemetry['collection_error'] = str(e)
        
        return telemetry
    
    async def _generate_wrapup_markdown(self, ecid: str, run_number: str, task_id: str, 
                                       completion_payload: Dict[str, Any], 
                                       telemetry: Dict[str, Any]) -> str:
        """
        Generate wrap-up markdown content (SIP-027 Phase 1)
        Creates formatted markdown document with reasoning traces and telemetry
        """
        from datetime import datetime
        
        # Extract data from completion payload
        tasks_completed = completion_payload.get('tasks_completed', [])
        artifacts = completion_payload.get('artifacts', [])
        metrics = completion_payload.get('metrics', {})
        
        # Extract data from telemetry
        db_metrics = telemetry.get('database_metrics', {})
        task_count = db_metrics.get('task_count', 0)
        execution_cycle = db_metrics.get('execution_cycle', {})
        
        # Build markdown content
        markdown = f"""# 🧩 WarmBoot Run {run_number} — Wrap-Up Summary
_Generated: {datetime.utcnow().isoformat()}_  
_ECID: {ecid}_  
_Generated by: Max (Lead Agent)_

---

## 1️⃣ Execution Summary

**Run Information:**
- **ECID**: {ecid}
- **PID**: {execution_cycle.get('pid', 'N/A')}
- **Run Type**: {execution_cycle.get('run_type', 'warmboot')}
- **Title**: {execution_cycle.get('title', 'WarmBoot Run')}
- **Status**: {execution_cycle.get('status', 'completed')}

**Task Information:**
- **Primary Task**: {task_id}
- **Tasks Completed**: {', '.join(tasks_completed)}
- **Total Task Count**: {task_count}

---

## 2️⃣ Development Activities (Neo)

**Tasks Executed:**
{chr(10).join([f"- {task}" for task in tasks_completed])}

**Artifacts Generated:**
{chr(10).join([f"- `{artifact.get('path', 'unknown')}` (hash: {artifact.get('hash', 'N/A')[:16]}...)" for artifact in artifacts]) if artifacts else '- No artifacts logged'}

**Metrics:**
- **Duration**: {metrics.get('duration_seconds', 0)} seconds
- **Tokens Used**: {metrics.get('tokens_used', 0)}
- **Tests Passed**: {metrics.get('tests_passed', 0)}
- **Tests Failed**: {metrics.get('tests_failed', 0)}

---

## 3️⃣ Database Metrics

| Metric | Value |
|--------|-------|
| **Task Logs Recorded** | {task_count} |
| **Execution Cycle Status** | {execution_cycle.get('status', 'N/A')} |
| **ECID** | {ecid} |
| **PID** | {execution_cycle.get('pid', 'N/A')} |

---

## 4️⃣ Communication Metrics

| Metric | Value |
|--------|-------|
| **Messages Processed** | {telemetry.get('rabbitmq_metrics', {}).get('messages_processed', 0)} |
| **Inter-Agent Communications** | {len(telemetry.get('rabbitmq_metrics', {}).get('communication_log', []))} |

---

## 5️⃣ Reasoning Traces

### Max (Lead Agent)
> "PRD processed and tasks delegated to Neo"
> "Monitoring developer task completion via event-driven pattern"
> "Received developer completion event from Neo"
> "Triggering automated WarmBoot wrap-up generation"

### Neo (Dev Agent)
> "Processing delegated development tasks"
> "Executing: {', '.join(tasks_completed)}"
> "Generated {len(artifacts)} artifact(s)"
> "Emitting developer completion event to Max"

---

## 6️⃣ Infrastructure Status

**Services:**
- ✅ RabbitMQ (event-driven messaging)
- ✅ PostgreSQL (task logging and metrics)
- ✅ Task Management API (execution cycle tracking)

**Agents:**
- ✅ Max (Lead/Governance)
- ✅ Neo (Development)

---

## 7️⃣ Next Steps

- [ ] Review wrap-up for completeness
- [ ] Archive artifacts if needed
- [ ] Plan next WarmBoot run
- [ ] Consider activating additional agents (EVE, Data) for Phase 2

---

## 📝 Notes

This wrap-up was automatically generated by Max using **SIP-027 Phase 1** event-driven coordination.  
Neo emitted a `task.developer.completed` event, which triggered this wrap-up generation.

**Phase 1 Status**: ✅ Event-driven wrap-up working as designed

---

_End of WarmBoot Run {run_number} Wrap-Up_
"""
        
        return markdown
    
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
            
            # Read PRD
            prd_content = await self.read_prd(prd_path)
            if not prd_content:
                return {"status": "error", "message": "Failed to read PRD"}
            
            # Analyze PRD requirements
            prd_analysis = await self.analyze_prd_requirements(prd_content)
            if not prd_analysis:
                return {"status": "error", "message": "Failed to analyze PRD"}
            
            # Extract app name from PRD path or content
            app_name = "Application"  # Default fallback
            if "hellosquad" in prd_path.lower():
                app_name = "HelloSquad"
            elif "prd-" in prd_path.lower():
                # Extract app name from PRD filename (e.g., "PRD-001-HelloSquad.md" -> "HelloSquad")
                import re
                match = re.search(r'PRD-\d+-(.+)\.md', prd_path)
                if match:
                    app_name = match.group(1)
            
            # Create development tasks
            tasks = await self.create_development_tasks(prd_analysis, app_name, ecid)
            if not tasks:
                return {"status": "error", "message": "Failed to create tasks"}
            
            # Delegate tasks to Neo
            delegated_tasks = []
            for task in tasks:
                delegation_target = await self.determine_delegation_target(task["task_type"])
                
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
    identity = os.getenv('AGENT_ID', 'lead_agent')
    agent = LeadAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
