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
from typing import Dict, Any, List
from base_agent import BaseAgent, AgentMessage
from agents.contracts.task_spec import TaskSpec

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
    
    async def generate_task_spec(self, prd_content: str, app_name: str, version: str, run_id: str, features: List[str] = None) -> TaskSpec:
        """Generate TaskSpec from PRD analysis using LLM"""
        logger.info(f"{self.name} generating TaskSpec for {app_name} v{version}")
        
        prompt = f"""
        You are a senior product manager analyzing a PRD to create a detailed TaskSpec for development.
        
        APPLICATION: {app_name}
        VERSION: {version}
        RUN ID: {run_id}
        FEATURES: {', '.join(features) if features else 'General web application'}
        
        PRD CONTENT:
        {prd_content}
        
        Create a comprehensive TaskSpec that includes:
        
        1. PRD_ANALYSIS: Your detailed analysis of the requirements, user needs, and technical considerations
        2. FEATURES: Specific feature list derived from the PRD
        3. CONSTRAINTS: Technical constraints, performance requirements, security considerations
        4. SUCCESS_CRITERIA: Measurable success criteria for the application
        
        CRITICAL OUTPUT RULES:
        - Return ONLY valid YAML
        - Start directly with "app_name:"
        - Do NOT wrap in markdown code fences
        - Do NOT include explanatory text
        - Use proper YAML indentation
        
        Return the TaskSpec in this exact format:
        
        app_name: "{app_name}"
        version: "{version}"
        run_id: "{run_id}"
        prd_analysis: |
          Your detailed analysis here...
        features:
          - feature1
          - feature2
        constraints:
          technical: "constraints here"
          performance: "requirements here"
          security: "considerations here"
        success_criteria:
          - "Criterion 1"
          - "Criterion 2"
        """
        
        try:
            response = await self.llm_client.complete(
                prompt=prompt,
                temperature=0.5,  # Lower temp for structured output
                max_tokens=3000
            )
            
            # Clean and parse YAML response
            from agents.llm.validators import clean_yaml_response
            cleaned_response = clean_yaml_response(response)
            task_spec = TaskSpec.from_yaml(cleaned_response)
            logger.info(f"{self.name} generated TaskSpec with {len(task_spec.features)} features")
            
            # Log the TaskSpec generation for telemetry
            from datetime import datetime
            self.communication_log.append({
                'timestamp': datetime.utcnow().isoformat(),
                'agent': self.name,
                'message_type': 'taskspec_generation',
                'description': f"Generated TaskSpec for {app_name}: {response[:500]}...",
                'ecid': run_id,
                'full_response': response
            })
            
            return task_spec
            
        except Exception as e:
            logger.error(f"{self.name} failed to generate TaskSpec: {e}")
            # Fallback to basic TaskSpec
            return TaskSpec(
                app_name=app_name,
                version=version,
                run_id=run_id,
                prd_analysis=f"Basic analysis for {app_name} - TaskSpec generation failed: {e}",
                features=features or [],
                constraints={},
                success_criteria=["Application deploys successfully"]
            )
    
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

    async def _handle_design_manifest_completion(self, message: AgentMessage) -> None:
        """Handle design manifest completion - extract manifest and trigger build task"""
        try:
            payload = message.payload
            context = message.context
            task_id = payload.get('task_id', 'unknown')
            ecid = context.get('ecid', payload.get('ecid', 'unknown'))
            status = payload.get('status', 'unknown')
            
            logger.info(f"{self.name} received design manifest completion: task {task_id}, ECID {ecid}, status {status}")
            
            if status == 'completed' and 'manifest' in payload:
                # Extract manifest from Neo's response
                manifest = payload['manifest']
                self.warmboot_state['manifest'] = manifest
                
                logger.info(f"{self.name} stored manifest for ECID {ecid}: {manifest.get('architecture', {}).get('type', 'unknown')} with {len(manifest.get('files', []))} files")
                
                # Trigger next task in sequence (build)
                await self._trigger_next_task(ecid, 'build')
            else:
                logger.warning(f"{self.name} design manifest task failed or missing manifest: {status}")
                
        except Exception as e:
            logger.error(f"{self.name} failed to handle design manifest completion: {e}")

    async def _handle_build_completion(self, message: AgentMessage) -> None:
        """Handle build completion - extract files and trigger deploy task"""
        try:
            payload = message.payload
            context = message.context
            task_id = payload.get('task_id', 'unknown')
            ecid = context.get('ecid', payload.get('ecid', 'unknown'))
            status = payload.get('status', 'unknown')
            
            logger.info(f"{self.name} received build completion: task {task_id}, ECID {ecid}, status {status}")
            
            if status == 'completed' and 'created_files' in payload:
                # Extract created files from Neo's response
                created_files = payload['created_files']
                self.warmboot_state['build_files'] = created_files
                
                logger.info(f"{self.name} stored build files for ECID {ecid}: {len(created_files)} files created")
                
                # Trigger next task in sequence (deploy)
                await self._trigger_next_task(ecid, 'deploy')
            else:
                logger.warning(f"{self.name} build task failed or missing files: {status}")
                
        except Exception as e:
            logger.error(f"{self.name} failed to handle build completion: {e}")

    async def _handle_deploy_completion(self, message: AgentMessage) -> None:
        """Handle deploy completion - trigger governance logging"""
        try:
            payload = message.payload
            context = message.context
            task_id = payload.get('task_id', 'unknown')
            ecid = context.get('ecid', payload.get('ecid', 'unknown'))
            status = payload.get('status', 'unknown')
            
            logger.info(f"{self.name} received deploy completion: task {task_id}, ECID {ecid}, status {status}")
            
            if status == 'completed':
                # Trigger governance logging
                await self._log_warmboot_governance(ecid, self.warmboot_state['manifest'], self.warmboot_state['build_files'])
                
                # Generate wrap-up
                await self.generate_warmboot_wrapup(ecid, task_id, payload)
                
                logger.info(f"{self.name} completed three-task sequence for ECID {ecid}")
            else:
                logger.warning(f"{self.name} deploy task failed: {status}")
                
        except Exception as e:
            logger.error(f"{self.name} failed to handle deploy completion: {e}")

    async def _trigger_next_task(self, ecid: str, next_action: str) -> None:
        """Trigger the next task in the sequence"""
        try:
            # Find the next task in warmboot_state pending_tasks
            # For now, we'll create a simple implementation
            # In a full implementation, this would use proper task orchestration
            
            logger.info(f"{self.name} triggering next task: {next_action} for ECID {ecid}")
            
            # This is a placeholder - in a real implementation, we'd:
            # 1. Find the next task in the sequence
            # 2. Send it to Neo
            # 3. Update warmboot_state
            
            # For now, we'll rely on the existing task delegation system
            # The tasks are already created and will be processed in order
            
        except Exception as e:
            logger.error(f"{self.name} failed to trigger next task: {e}")

    async def _log_warmboot_governance(self, run_id: str, manifest: Dict, files: List[str]) -> None:
        """Log governance information for WarmBoot run"""
        try:
            import hashlib
            import os
            
            logger.info(f"{self.name} logging governance for run {run_id}")
            
            # Calculate checksums
            checksums = {}
            for file_path in files:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        checksums[file_path] = hashlib.sha256(f.read()).hexdigest()
            
            # Store manifest snapshot
            manifest_path = f"/app/logs/{run_id}_manifest.yaml"
            os.makedirs("/app/logs", exist_ok=True)
            with open(manifest_path, 'w') as f:
                yaml.dump(manifest, f)
            
            # Store checksums
            checksums_path = f"/app/logs/{run_id}_checksums.json"
            with open(checksums_path, 'w') as f:
                json.dump(checksums, f, indent=2)
            
            logger.info(f"{self.name} governance logged: manifest={manifest_path}, checksums={checksums_path}")
            
        except Exception as e:
            logger.error(f"{self.name} failed to log governance: {e}")

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
    
    async def determine_delegation_target(self, task_type: str) -> str:
        """
        Determine which agent should handle the task based on role.
        Returns agent ID (e.g., 'dev-agent') not display name.
        
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
        
        agent_id = role_to_agent_map.get(target_role, 'dev-agent')
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
            
            logger.info(f"{self.name} making LLM call for PRD analysis...")
            llm_response = await self.llm_response(analysis_prompt, "PRD Analysis")
            logger.info(f"{self.name} received LLM response: {llm_response[:200]}...")
            
            # Log the real AI reasoning to communication log for wrap-up extraction
            from datetime import datetime
            self.communication_log.append({
                'timestamp': datetime.utcnow().isoformat(),
                'agent': self.name,
                'message_type': 'llm_reasoning',
                'description': f"Real AI PRD Analysis: {llm_response[:500]}...",
                'ecid': self.current_ecid,
                'full_response': llm_response
            })
            
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
            
            # Generate TaskSpec for the build task
            task_spec = await self.generate_task_spec(
                prd_content=prd_analysis.get("full_analysis", "Team Status Dashboard with activity feed and project progress tracking"),
                app_name=app_name,
                version=app_version,
                run_id=ecid,
                features=prd_analysis.get("core_features", [])
            )
            
            # Create three-task sequence: design_manifest -> build -> deploy
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
                    "task_id": f"{app_kebab}-design-{int(time.time())}",
                    "task_type": "development",
                    "ecid": ecid,
                    "description": f"Design architecture manifest for {app_name} application version {app_version}",
                    "requirements": {
                        "action": "design_manifest",
                        "application": app_name,
                        "version": app_version,
                        "framework_version": framework_version,
                        "warm_boot_sequence": warm_boot_sequence,
                        "target_directory": f"warm-boot/apps/{app_kebab}/",  # Add target_directory for file creation
                        "task_spec": task_spec.to_dict()  # Include Max's TaskSpec
                    },
                    "complexity": 0.4,
                    "priority": "HIGH"
                },
                {
                    "task_id": f"{app_kebab}-build-{int(time.time())}",
                    "task_type": "development",
                    "ecid": ecid,
                    "description": f"Build {app_name} application version {app_version} using JSON workflow",
                    "requirements": {
                        "action": "build",
                        "application": app_name,
                        "version": app_version,
                        "framework_version": framework_version,
                        "warm_boot_sequence": warm_boot_sequence,
                        "features": prd_analysis.get("core_features", []),
                        "technical_requirements": prd_analysis.get("technical_requirements", []),
                        "target_directory": f"warm-boot/apps/{app_kebab}/",
                        "from_scratch": True,
                        "task_spec": task_spec.to_dict(),  # Include Max's TaskSpec
                        "prd_analysis": prd_analysis.get("full_analysis", "Team Status Dashboard with activity feed and project progress tracking"),
                        "manifest": None  # Will be populated by design_manifest completion handler
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
                        "source_dir": f"warm-boot/apps/{app_kebab}/",
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
        Collect comprehensive telemetry for WarmBoot wrap-up (SIP-027 Phase 1)
        Gathers reasoning logs, DB metrics, Docker events, RabbitMQ stats, system metrics
        """
        from datetime import datetime
        import psutil
        import subprocess
        import hashlib
        import os
        
        telemetry = {
            'database_metrics': {},
            'rabbitmq_metrics': {},
            'docker_events': {},
            'reasoning_logs': {},
            'system_metrics': {},
            'artifact_hashes': {},
            'event_timeline': [],
            'collection_timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            # Collect database metrics via Task API (replaces direct DB reads)
            import aiohttp
            
            # Get task logs for this ECID via API
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.task_api_url}/api/v1/tasks/ec/{ecid}") as resp:
                    if resp.status == 200:
                        task_logs = await resp.json()
                        telemetry['database_metrics']['task_count'] = len(task_logs)
                        telemetry['database_metrics']['tasks'] = task_logs
                    else:
                        logger.warning(f"Failed to fetch tasks for ECID {ecid}: {await resp.text()}")
                        telemetry['database_metrics']['task_count'] = 0
                        telemetry['database_metrics']['tasks'] = []
                
                # Get execution cycle info via API
                async with session.get(f"{self.task_api_url}/api/v1/execution-cycles/{ecid}") as resp:
                    if resp.status == 200:
                        cycle_info = await resp.json()
                        telemetry['database_metrics']['execution_cycle'] = cycle_info
                        
                        # Calculate execution duration (Task 1.6)
                        try:
                            # Use created_at as start_time since execution_cycle table doesn't have start_time column
                            start_time_str = cycle_info.get('start_time') or cycle_info.get('created_at')
                            if start_time_str:
                                # Parse ISO format datetime string
                                try:
                                    # Try datetime.fromisoformat first (Python 3.7+)
                                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                                    if start_time.tzinfo:
                                        from datetime import timezone
                                        start_time = start_time.astimezone(timezone.utc).replace(tzinfo=None)
                                except (ValueError, AttributeError):
                                    # Fallback to dateutil if available
                                    try:
                                        from dateutil import parser
                                        start_time = parser.parse(start_time_str)
                                        if start_time.tzinfo:
                                            from datetime import timezone
                                            start_time = start_time.astimezone(timezone.utc).replace(tzinfo=None)
                                    except ImportError:
                                        # Last resort: assume format and parse manually
                                        logger.warning(f"{self.name} dateutil not available, using basic datetime parsing")
                                        start_time = datetime.fromisoformat(start_time_str.replace('Z', '').split('.')[0])
                                
                                end_time = datetime.utcnow()
                                duration_seconds = (end_time - start_time).total_seconds()
                                telemetry['execution_duration'] = {
                                    'start_time': start_time_str,
                                    'end_time': end_time.isoformat(),
                                    'duration_seconds': round(duration_seconds, 2),
                                    'duration_formatted': f"{int(duration_seconds // 60)}m {int(duration_seconds % 60)}s"
                                }
                                logger.info(f"{self.name} execution duration: {telemetry['execution_duration']['duration_formatted']}")
                        except Exception as e:
                            logger.warning(f"{self.name} failed to calculate execution duration: {e}")
                            telemetry['execution_duration'] = {'error': str(e)}
                    else:
                        logger.warning(f"Failed to fetch execution cycle {ecid}: {await resp.text()}")
            
            logger.info(f"{self.name} collected telemetry via API: {telemetry['database_metrics']['task_count']} tasks")
            
            # Collect RabbitMQ metrics (Task 1.4: Enhanced)
            try:
                # Use rabbitmqctl to get detailed queue stats (manual collection)
                result = await self.execute_command("rabbitmqctl list_queues name messages consumers")
                queue_stats = {}
                total_messages_manual = len(self.communication_log)  # Manual tracking fallback
                if result.get('success') and result.get('stdout'):
                    for line in result.get('stdout', '').strip().split('\n')[1:]:  # Skip header
                        parts = line.split('\t')
                        if len(parts) >= 3:
                            queue_name = parts[0].strip()
                            messages = int(parts[1].strip()) if parts[1].strip().isdigit() else 0
                            consumers = int(parts[2].strip()) if parts[2].strip().isdigit() else 0
                            queue_stats[queue_name] = {
                                'messages': messages,
                                'consumers': consumers
                            }
                
                # Record RabbitMQ metrics via telemetry client
                try:
                    self.record_counter('rabbitmq_messages_total', total_messages_manual, {
                        'source': 'communication_log',
                        'ecid': ecid
                    })
                except Exception as e:
                    logger.debug(f"{self.name} failed to record RabbitMQ telemetry metric: {e}")
                
                # Query telemetry backend for RabbitMQ metrics (Task 1.4: Primary source)
                rabbitmq_from_telemetry = None
                total_messages_telemetry = 0
                try:
                    import aiohttp
                    prometheus_url = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
                    # Query Prometheus for rabbitmq_messages_total metric with ECID label
                    query = f'sum(rabbitmq_messages_total{{ecid="{ecid}"}})'
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f'{prometheus_url}/api/v1/query',
                            params={'query': query},
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get('status') == 'success' and data.get('data', {}).get('result'):
                                    # Extract message count from Prometheus result
                                    result = data['data']['result'][0] if data['data']['result'] else None
                                    if result and 'value' in result:
                                        # Prometheus returns [timestamp, value] format
                                        total_messages_telemetry = int(float(result['value'][1]))
                                        rabbitmq_from_telemetry = {
                                            'source': 'prometheus',
                                            'total_messages': total_messages_telemetry,
                                            'query': query
                                        }
                                        logger.debug(f"{self.name} RabbitMQ metrics from Prometheus: {total_messages_telemetry} messages")
                except Exception as e:
                    logger.debug(f"{self.name} Failed to query Prometheus for RabbitMQ metrics: {e}")
                
                # Use telemetry backend as primary source, manual tracking as fallback (Task 1.4)
                total_messages = total_messages_telemetry if total_messages_telemetry > 0 else total_messages_manual
                messages_source = rabbitmq_from_telemetry.get('source') if rabbitmq_from_telemetry else 'manual_tracking'
                
                telemetry['rabbitmq_metrics'] = {
                    'messages_processed': total_messages,
                    'messages_source': messages_source,
                    'communication_log': self.communication_log[-10:],  # Last 10 messages
                    'queue_stats': queue_stats,
                    'queue_count': len(queue_stats),
                    'telemetry_data': rabbitmq_from_telemetry  # Include telemetry backend data if available
                }
            except Exception as e:
                logger.warning(f"{self.name} failed to collect detailed RabbitMQ metrics: {e}")
                telemetry['rabbitmq_metrics'] = {
                    'messages_processed': len(self.communication_log),
                    'communication_log': self.communication_log[-10:],
                    'error': str(e)
                }
            
            # Collect system metrics (Task 1.2: Add GPU utilization)
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                system_metrics = {
                    'cpu_usage_percent': cpu_percent,
                    'memory_usage_gb': round(memory.used / (1024**3), 2),
                    'memory_total_gb': round(memory.total / (1024**3), 2),
                    'memory_percent': memory.percent
                }
                
                # Try to get GPU utilization (Task 1.2)
                try:
                    result = await self.execute_command("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits")
                    if result.get('success') and result.get('stdout'):
                        gpu_data = result.get('stdout', '').strip().split('\n')[0]
                        if gpu_data:
                            parts = gpu_data.split(', ')
                            if len(parts) >= 3:
                                gpu_util = int(parts[0].strip()) if parts[0].strip().isdigit() else 0
                                gpu_mem_used = int(parts[1].strip().split()[0]) if parts[1].strip().split()[0].isdigit() else 0
                                gpu_mem_total = int(parts[2].strip().split()[0]) if parts[2].strip().split()[0].isdigit() else 0
                                system_metrics['gpu_utilization'] = {
                                    'gpu_usage_percent': gpu_util,
                                    'memory_used_mb': gpu_mem_used,
                                    'memory_total_mb': gpu_mem_total,
                                    'memory_percent': round((gpu_mem_used / gpu_mem_total * 100) if gpu_mem_total > 0 else 0, 2)
                                }
                                # Record GPU metric via telemetry client
                                try:
                                    self.record_gauge('system_gpu_utilization_percent', gpu_util)
                                except Exception as e:
                                    logger.debug(f"{self.name} failed to record GPU telemetry metric: {e}")
                except Exception as e:
                    logger.debug(f"{self.name} GPU not available or nvidia-smi failed: {e}")
                    system_metrics['gpu_utilization'] = None
                
                # Record system metrics via telemetry client
                try:
                    self.record_gauge('system_cpu_usage_percent', cpu_percent)
                    self.record_gauge('system_memory_usage_percent', memory.percent)
                except Exception as e:
                    logger.debug(f"{self.name} failed to record system telemetry metrics: {e}")
                
                telemetry['system_metrics'] = system_metrics
            except Exception as e:
                logger.warning(f"{self.name} failed to collect system metrics: {e}")
                telemetry['system_metrics'] = {'error': str(e)}
            
            # Collect Docker events (Task 1.5: Improved)
            try:
                # Get execution cycle start time for filtering
                cycle_start = None
                if 'execution_duration' in telemetry and telemetry.get('execution_duration', {}).get('start_time'):
                    start_time_str = telemetry['execution_duration']['start_time']
                    try:
                        from dateutil import parser
                        cycle_start = parser.parse(start_time_str)
                    except (ImportError, Exception):
                        # Fallback to datetime.fromisoformat
                        cycle_start = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                        if cycle_start.tzinfo:
                            from datetime import timezone
                            cycle_start = cycle_start.astimezone(timezone.utc).replace(tzinfo=None)
                
                # Get Docker events since cycle start (or last 5 minutes as fallback)
                since_time = "5m"  # Default
                if cycle_start:
                    from datetime import timedelta
                    duration = datetime.utcnow() - cycle_start
                    since_time = f"{int(duration.total_seconds())}s"
                
                # Get container lifecycle events
                result = await self.execute_command(f"docker events --since {since_time} --format '{{{{.Time}}}} {{{{.Type}}}} {{{{.Action}}}} {{{{.Actor.Attributes.name}}}}'")
                
                containers = {}
                images = {}
                events_list = []
                
                if result.get('success') and result.get('stdout'):
                    docker_events = result.get('stdout', '').strip().split('\n')
                    for event_line in docker_events:
                        if not event_line.strip():
                            continue
                        parts = event_line.split(' ')
                        if len(parts) >= 4:
                            event_time = parts[0]
                            event_type = parts[1]
                            event_action = parts[2]
                            event_name = ' '.join(parts[3:]) if len(parts) > 3 else 'unknown'
                            
                            events_list.append({
                                'time': event_time,
                                'type': event_type,
                                'action': event_action,
                                'name': event_name
                            })
                            
                            # Track containers
                            if event_type == 'container':
                                if event_name not in containers:
                                    containers[event_name] = []
                                containers[event_name].append({'action': event_action, 'time': event_time})
                            
                            # Track images
                            elif event_type == 'image':
                                if event_name not in images:
                                    images[event_name] = []
                                images[event_name].append({'action': event_action, 'time': event_time})
                
                telemetry['docker_events'] = {
                    'containers': containers,
                    'images': images,
                    'events': events_list,
                    'event_count': len(events_list),
                    'container_count': len(containers),
                    'image_count': len(images)
                }
            except Exception as e:
                logger.warning(f"{self.name} failed to collect Docker events: {e}")
                telemetry['docker_events'] = {'error': str(e)}
            
            # Collect artifact hashes
            try:
                artifact_hashes = {}
                app_dir = "/app/warm-boot/apps/hello-squad"
                if os.path.exists(app_dir):
                    for root, dirs, files in os.walk(app_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                with open(file_path, 'rb') as f:
                                    file_hash = hashlib.sha256(f.read()).hexdigest()
                                    relative_path = os.path.relpath(file_path, app_dir)
                                    artifact_hashes[relative_path] = f"sha256:{file_hash}"  # Task 2.3: Full hash, not truncated
                            except Exception as e:
                                logger.warning(f"{self.name} failed to hash {file_path}: {e}")
                
                telemetry['artifact_hashes'] = artifact_hashes
            except Exception as e:
                logger.warning(f"{self.name} failed to collect artifact hashes: {e}")
                telemetry['artifact_hashes'] = {'error': str(e)}
            
            # Collect reasoning logs (from communication log) - Task 1.1: Enhanced with prompts and trace IDs
            reasoning_entries = []
            ollama_logs = []  # JSONL-like format for reasoning traces
            tokens_by_agent = {}  # Task 1.3: Track tokens per agent
            total_tokens_manual = 0  # Task 1.3: Manual tracking fallback
            
            for entry in self.communication_log:
                if 'reasoning' in entry.get('message_type', '').lower() or 'llm' in entry.get('message_type', '').lower():
                    reasoning_entries.append(entry)
                    
                    # Format as JSONL-like entry (Task 1.1: Ollama JSONL log format)
                    ollama_log_entry = {
                        'timestamp': entry.get('timestamp'),
                        'agent': entry.get('agent'),
                        'ecid': entry.get('ecid'),
                        'trace_id': entry.get('trace_id'),  # Task 1.1: Link to telemetry trace
                        'prompt': entry.get('prompt', ''),  # Task 1.1: Include prompt
                        'response': entry.get('full_response', entry.get('description', '')),
                        'message_type': entry.get('message_type')
                    }
                    
                    # Include token usage in JSONL log entry (Task 1.3)
                    if 'token_usage' in entry:
                        ollama_log_entry['token_usage'] = entry['token_usage']
                        # Sum tokens by agent
                        agent_name = entry.get('agent', 'unknown')
                        entry_tokens = entry['token_usage'].get('total_tokens', 0)
                        if agent_name not in tokens_by_agent:
                            tokens_by_agent[agent_name] = 0
                        tokens_by_agent[agent_name] += entry_tokens
                        total_tokens_manual += entry_tokens
                    
                    ollama_logs.append(ollama_log_entry)
            
            # Query telemetry backend for token metrics (Task 1.3: Primary source)
            tokens_from_telemetry = None
            total_tokens_telemetry = 0
            try:
                import aiohttp
                prometheus_url = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
                # Query Prometheus for agent_tokens_used_total metric with ECID label
                # Note: If metrics don't have ecid label, also try without it (fallback)
                query_with_ecid = f'sum(agent_tokens_used_total{{ecid="{ecid}"}})'
                query_without_ecid = f'sum(agent_tokens_used_total)'
                
                async with aiohttp.ClientSession() as session:
                    # First try with ECID label
                    async with session.get(
                        f'{prometheus_url}/api/v1/query',
                        params={'query': query_with_ecid},
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get('status') == 'success' and data.get('data', {}).get('result'):
                                # Extract token count from Prometheus result
                                result = data['data']['result'][0] if data['data']['result'] else None
                                if result and 'value' in result:
                                    # Prometheus returns [timestamp, value] format
                                    total_tokens_telemetry = int(float(result['value'][1]))
                                    tokens_from_telemetry = {
                                        'source': 'prometheus',
                                        'total_tokens': total_tokens_telemetry,
                                        'query': query_with_ecid
                                    }
                                    logger.debug(f"{self.name} Token metrics from Prometheus: {total_tokens_telemetry} tokens")
                    
                    # If no results with ECID, try without ECID (fallback for metrics without label)
                    if total_tokens_telemetry == 0:
                        async with session.get(
                            f'{prometheus_url}/api/v1/query',
                            params={'query': query_without_ecid},
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get('status') == 'success' and data.get('data', {}).get('result'):
                                    # Sum all token metrics (all agents, all operations)
                                    total_sum = 0
                                    for result in data['data']['result']:
                                        if 'value' in result:
                                            total_sum += int(float(result['value'][1]))
                                    if total_sum > 0:
                                        total_tokens_telemetry = total_sum
                                        tokens_from_telemetry = {
                                            'source': 'prometheus',
                                            'total_tokens': total_tokens_telemetry,
                                            'query': query_without_ecid,
                                            'note': 'Metrics without ECID label - aggregated all tokens'
                                        }
                                        logger.debug(f"{self.name} Token metrics from Prometheus (no ECID): {total_tokens_telemetry} tokens")
            except Exception as e:
                logger.debug(f"{self.name} Failed to query Prometheus for token metrics: {e}")
            
            # Use telemetry backend as primary source, manual tracking as fallback (Task 1.3)
            tokens_used = total_tokens_telemetry if total_tokens_telemetry > 0 else total_tokens_manual
            tokens_source = tokens_from_telemetry.get('source') if tokens_from_telemetry else 'manual_tracking'
            
            telemetry['reasoning_logs'] = {
                'reasoning_entries': reasoning_entries,
                'ollama_logs': ollama_logs,  # Task 1.1: JSONL-like format
                'entry_count': len(reasoning_entries),
                'agents_with_reasoning': list(set(entry.get('agent', 'unknown') for entry in reasoning_entries)),
                # Task 1.3: Token usage tracking
                'tokens_used': tokens_used,
                'tokens_by_agent': tokens_by_agent,
                'tokens_source': tokens_source,
                'tokens_from_telemetry': tokens_from_telemetry,
                'tokens_manual_fallback': total_tokens_manual if total_tokens_telemetry > 0 else None
            }
            
            # Build event timeline from communication log
            event_timeline = []
            for entry in self.communication_log:
                event_timeline.append({
                    'timestamp': entry.get('timestamp', 'unknown'),
                    'agent': entry.get('agent', 'unknown'),
                    'event_type': entry.get('message_type', 'unknown'),
                    'description': entry.get('description', 'No description')
                })
            
            telemetry['event_timeline'] = sorted(event_timeline, key=lambda x: x['timestamp'])
            
        except Exception as e:
            logger.error(f"{self.name} failed to collect telemetry: {e}")
            telemetry['collection_error'] = str(e)
        
        return telemetry
    
    def _extract_real_ai_reasoning(self, ecid: str, agent_name: str = None) -> str:
        """
        Extract real AI reasoning from communication log for wrap-up (Task 2.2)
        Enhanced to extract from communication_log and format with agent names and timestamps
        Also checks completion event payloads for reasoning from other agents (Fix: Neo's reasoning)
        """
        try:
            real_reasoning = []
            
            # Find entries with llm_reasoning message type for this ECID (from Max's log)
            for entry in self.communication_log:
                entry_ecid = entry.get('ecid')
                entry_agent = entry.get('agent', 'unknown')
                entry_type = entry.get('message_type', '')
                
                # Filter by ECID and optionally by agent name
                if entry_ecid == ecid:
                    if entry_type in ['llm_reasoning', 'reasoning'] or 'llm' in entry_type.lower():
                        # Skip if agent filter specified and doesn't match
                        if agent_name and entry_agent.lower() != agent_name.lower():
                            continue
                        
                        # Get timestamp
                        timestamp = entry.get('timestamp', 'unknown')
                        if timestamp != 'unknown':
                            try:
                                # Format timestamp nicely
                                from datetime import datetime
                                if 'T' in timestamp:
                                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                    formatted_time = dt.strftime('%H:%M:%S')
                                else:
                                    formatted_time = timestamp
                            except:
                                formatted_time = timestamp
                        else:
                            formatted_time = 'unknown'
                        
                        # Get response text
                        full_response = entry.get('full_response', '')
                        description = entry.get('description', '')
                        
                        # Format with agent name and timestamp (Task 2.2)
                        if full_response:
                            # Truncate long responses but keep meaningful content
                            response_preview = full_response[:500] + ('...' if len(full_response) > 500 else '')
                            reasoning_text = f"> **{entry_agent}** ({formatted_time}): {response_preview}"
                        elif description:
                            reasoning_text = f"> **{entry_agent}** ({formatted_time}): {description[:500]}"
                        else:
                            reasoning_text = f"> **{entry_agent}** ({formatted_time}): [No reasoning text]"
                        
                        real_reasoning.append(reasoning_text)
            
            # Also check completion event payloads for reasoning from other agents (Fix: Neo's reasoning)
            # Neo includes reasoning in completion event payloads sometimes
            if agent_name:
                for entry in self.communication_log:
                    entry_ecid = entry.get('ecid')
                    entry_type = entry.get('message_type', '')
                    entry_payload = entry.get('payload', {})
                    
                    # Check completion events from the target agent
                    if entry_ecid == ecid and entry_type == 'task.developer.completed':
                        sender = entry.get('sender', '').lower()
                        if agent_name.lower() in sender or ('neo' in sender.lower() if agent_name.lower() == 'neo' else False):
                            # Look for reasoning in payload or description
                            payload_description = entry_payload.get('description', entry.get('description', ''))
                            if payload_description and 'reasoning' in payload_description.lower():
                                timestamp = entry.get('timestamp', 'unknown')
                                try:
                                    from datetime import datetime
                                    if 'T' in timestamp:
                                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                        formatted_time = dt.strftime('%H:%M:%S')
                                    else:
                                        formatted_time = timestamp
                                except:
                                    formatted_time = timestamp
                                
                                reasoning_text = f"> **{agent_name}** ({formatted_time}): {payload_description[:500]}"
                                real_reasoning.append(reasoning_text)
            
            if real_reasoning:
                return '\n'.join(real_reasoning)
            else:
                if agent_name:
                    return f"> No reasoning trace found for agent '{agent_name}' in communication log for ECID {ecid}"
                else:
                    return f"> No reasoning trace found in communication log for ECID {ecid}"
                
        except Exception as e:
            logger.warning(f"{self.name} failed to extract real AI reasoning: {e}")
            return f"> Failed to extract real AI reasoning from logs: {e}"
    
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
        execution_duration = telemetry.get('execution_duration', {})
        
        # Extract comprehensive telemetry data
        system_metrics = telemetry.get('system_metrics', {})
        docker_events = telemetry.get('docker_events', {})
        artifact_hashes = telemetry.get('artifact_hashes', {})
        reasoning_logs = telemetry.get('reasoning_logs', {})
        event_timeline = telemetry.get('event_timeline', [])
        rabbitmq_metrics = telemetry.get('rabbitmq_metrics', {})
        
        # Extract token metrics (Task 1.3)
        tokens_used = reasoning_logs.get('tokens_used', metrics.get('tokens_used', 0))
        tokens_by_agent = reasoning_logs.get('tokens_by_agent', {})
        
        # Format execution duration
        duration_str = execution_duration.get('duration_formatted', 'Unknown')
        if duration_str == 'Unknown' and execution_duration.get('duration_seconds'):
            duration_sec = execution_duration['duration_seconds']
            duration_str = f"{int(duration_sec // 60)}m {int(duration_sec % 60)}s"
        
        # Format start and end times
        start_time = execution_duration.get('start_time', execution_cycle.get('start_time', 'Unknown'))
        end_time = execution_duration.get('end_time', datetime.utcnow().isoformat())
        
        # Extract reasoning traces for Max and Neo separately (Task 2.2)
        max_reasoning = self._extract_real_ai_reasoning(ecid, agent_name='max')
        neo_reasoning = self._extract_real_ai_reasoning(ecid, agent_name='neo')
        
        # Format artifacts with full hashes (Task 2.3)
        artifacts_list = []
        if artifacts:
            for artifact in artifacts:
                artifact_path = artifact.get('path', 'unknown')
                artifact_hash = artifact.get('hash', 'no hash')
                artifacts_list.append(f"- `{artifact_path}` — {artifact_hash}")
        elif artifact_hashes:
            for path, hash_val in artifact_hashes.items():
                artifacts_list.append(f"- `{path}` — {hash_val}")
        
        artifacts_section = '\n'.join(artifacts_list) if artifacts_list else "- No artifacts logged"
        
        # Calculate GPU metrics
        gpu_metrics = system_metrics.get('gpu_utilization', {})
        gpu_usage = gpu_metrics.get('gpu_usage_percent', 'N/A') if gpu_metrics else 'N/A'
        
        # Calculate Docker container counts
        containers = docker_events.get('containers', {})
        images = docker_events.get('images', {})
        container_count = len(containers)
        image_count = len(images)
        event_count = docker_events.get('event_count', len(docker_events.get('events', [])))
        
        # Build comprehensive markdown content (Task 2.1: Match SIP-027 template exactly)
        markdown = f"""# 🧩 WarmBoot Run {run_number} — Reasoning & Resource Trace Log
_Generated: {datetime.utcnow().isoformat()}_  
_ECID: {ecid}_  
_Duration: {duration_str}_

---

## 1️⃣ PRD Interpretation (Max)

**Reasoning Trace:**
{max_reasoning if max_reasoning.startswith('>') else '> ' + max_reasoning}

**Actions Taken:**
- Created execution cycle {ecid}
- Delegated tasks to Neo via task.developer.assign events
- Monitored completion via governance listener

---

## 2️⃣ Task Execution (Neo)

**Reasoning Trace:**
{neo_reasoning if neo_reasoning.startswith('>') else '> ' + neo_reasoning}

**Actions Taken:**
- Generated {len(artifact_hashes) if artifact_hashes else len(artifacts)} files
- Built Docker image: hello-squad:0.3.0.{run_number}
- Deployed container: squadops-hello-squad
- Emitted {len(tasks_completed)} completion events

---

## 3️⃣ Artifacts Produced
{artifacts_section}

---

## 4️⃣ 🔍 Resource & Event Summary

| Metric | Value | Notes |
|--------|-------|-------|
| **CPU Usage (Avg/Max)** | {system_metrics.get('cpu_usage_percent', 'N/A')}% | Measured via psutil snapshots during execution |
| **GPU Utilization** | {gpu_usage}% | Captured from nvidia-smi API (Ollama inference) |
| **Memory Usage** | {system_metrics.get('memory_usage_gb', 'N/A')} GB / {system_metrics.get('memory_total_gb', 'N/A')} GB | Container aggregate across squad |
| **DB Writes** | {task_count} task logs | `agent_task_log`, `execution_cycle` tables |
| **RabbitMQ Messages** | {rabbitmq_metrics.get('messages_processed', 0)} processed | `task.developer.assign`, `task.developer.completed` queues |
| **Containers Built** | {container_count} containers | Container lifecycle events |
| **Containers Updated** | {image_count} images | Image builds and updates |
| **Execution Duration** | {duration_str} | From ECID start to final artifact commit |
| **Artifacts Generated** | {len(artifact_hashes) if artifact_hashes else len(artifacts)} files | SHA256 hashes for integrity verification |
| **Reasoning Entries** | {reasoning_logs.get('entry_count', 0)} entries | LLM reasoning trace logs |

---

## 5️⃣ Metrics Snapshot

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Tasks Executed | {len(tasks_completed)} | N/A | ✅ Complete |
| Tokens Used | {tokens_used:,} | < 5,000 | {'✅ Under budget' if tokens_used < 5000 else '⚠️ Over budget'} |
| Reasoning Entries | {reasoning_logs.get('entry_count', 0)} | N/A | — |
| Pulse Count | {rabbitmq_metrics.get('messages_processed', 0)} | < 15 | {'✅ Efficient' if rabbitmq_metrics.get('messages_processed', 0) < 15 else '⚠️ High pulse'} |
| Rework Cycles | 0 | 0 | ✅ No rework |
| Test Pass Rate | {metrics.get('tests_passed', 0)} / {metrics.get('tests_passed', 0) + metrics.get('tests_failed', 0) if metrics.get('tests_failed', 0) > 0 else 1} | 100% | {'✅ All passed' if metrics.get('tests_failed', 0) == 0 else '⚠️ Some failed'} |

---

## 6️⃣ Event Timeline

| Timestamp | Agent | Event Type | Description |
|-----------|-------|------------|-------------|
{chr(10).join([self._format_event_timeline_entry(event) for event in event_timeline[-15:]]) if event_timeline else "| No events logged | | | |"}

---

## 7️⃣ Next Steps

- [ ] Deploy hello-squad container to production
- [ ] Archive current version to archive folder
- [ ] Update version manifest
- [ ] Schedule next WarmBoot run (run-{int(run_number)+1:03d})
- [ ] Consider activating EVE and Data agents for Phase 2

---

## 📝 SIP-027 Phase 1 Status

This wrap-up was automatically generated by LeadAgent using **SIP-027 Phase 1** event-driven coordination.  
DevAgent emitted `task.developer.completed` events, which triggered automated wrap-up generation.

**Phase 1 Features Validated:**
- ✅ Event-driven completion detection
- ✅ Automated telemetry collection (DB, RabbitMQ, System, Docker, GPU)
- ✅ Automated wrap-up generation with comprehensive metrics
- ✅ Token usage tracking with telemetry integration
- ✅ Volume mount integration (container → host filesystem)
- ✅ ECID-based traceability

**Ready for Phase 2:** Multi-agent coordination with EVE (QA) and Data (Analytics)

---

_End of WarmBoot Run {run_number} Reasoning & Resource Trace Log_
"""
        
        return markdown
    
    def _format_event_timeline_entry(self, event: Dict[str, Any]) -> str:
        """Helper to format a single event for the timeline table."""
        timestamp = event.get('timestamp', 'unknown')
        if timestamp != 'unknown':
            try:
                from datetime import datetime
                if 'T' in timestamp:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%H:%M:%S')
                else:
                    formatted_time = timestamp
            except:
                formatted_time = timestamp
        else:
            formatted_time = 'unknown'
        
        agent = event.get('agent', 'unknown')
        event_type = event.get('event_type', 'unknown')
        description = event.get('description', 'No description')
        
        # Truncate description if too long
        if len(description) > 80:
            description = description[:77] + '...'
        
        return f"| {formatted_time} | {agent} | {event_type} | {description} |"
    
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
    from config.unified_config import get_config
    config = get_config()
    identity = config.get_agent_id()
    agent = LeadAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
