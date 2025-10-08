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
from typing import Dict, Any, List
from base_agent import BaseAgent, AgentMessage

logger = logging.getLogger(__name__)

class LeadAgent(BaseAgent):
    """Lead Agent - The Governance Role"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="governance",
            reasoning_style="governance"
        )
        self.task_state_log = []
        self.approval_queue = []
        self.communication_log = []
        # Import configuration
        import sys
        import os
        sys.path.append('/app')
        from config.agent_config import get_complexity_threshold
        
        self.escalation_threshold = get_complexity_threshold("escalation")
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process governance tasks with approval/escalation logic"""
        logger.debug(f"Max process_task START - task: {task}")
        
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', 'unknown')
        complexity = task.get('complexity', 0.5)
        
        logger.debug(f"Max parsed task_id={task_id}, task_type={task_type}, complexity={complexity}")
        logger.info(f"Max processing governance task: {task_id}")
        
        # Check if this is a governance task with PRD path
        if task_type == "governance" and task.get('prd_path'):
            logger.debug(f"Max handling governance task with PRD path")
            prd_path = task.get('prd_path', '')
            application = task.get('application', 'Application')
            
            if prd_path:
                logger.info(f"Max processing PRD from path: {prd_path}")
                # Get run_id from the task
                run_id = task.get('run_id', 'run-001')
                # Process PRD from file path
                result = await self.process_prd_request(prd_path, run_id)
                await self.update_task_status(task_id, "Completed", 100.0)
                return result
            else:
                logger.warning(f"Max received empty PRD path for application: {application}")
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
        logger.debug(f"Max about to call update_task_status with task_id={task_id}")
        await self.update_task_status(task_id, "Active-Non-Blocking", 25.0)
        logger.debug(f"Max update_task_status completed successfully")
        
        # Governance decision logic
        if complexity > self.escalation_threshold:
            logger.debug(f"Max escalating task due to high complexity: {complexity} > {self.escalation_threshold}")
            # Escalate to premium consultation
            await self.escalate_task(task_id, task)
            logger.debug(f"Max escalate_task completed")
            await self.update_task_status(task_id, "Blocked", 50.0, "Escalated to premium consultation")
            logger.debug(f"Max update_task_status (escalated) completed")
            
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
            logger.debug(f"Max approving task for delegation (complexity: {complexity} <= {self.escalation_threshold})")
            # Approve and delegate
            await self.update_task_status(task_id, "Active-Non-Blocking", 75.0)
            logger.debug(f"Max update_task_status (delegation) completed")
            
            # Determine delegation target
            delegation_target = await self.determine_delegation_target(task_type)
            logger.debug(f"Max determined delegation_target: {delegation_target}")
            
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
        else:
            logger.info(f"Max received message: {message.message_type} from {message.sender}")
    
    async def handle_prd_request(self, message: AgentMessage) -> None:
        """Handle PRD processing requests"""
        prd_path = message.payload.get('prd_path', '')
        if not prd_path:
            logger.error("Max received PRD request without prd_path")
            return
        
        logger.info(f"Max handling PRD request: {prd_path}")
        
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
        
        logger.info(f"Max received task acknowledgment: {task_id} from {message.sender}")
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
        
        logger.error(f"Max received task error: {task_id} from {message.sender}: {error}")
        
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
    
    async def determine_delegation_target(self, task_type: str) -> str:
        """Determine which agent should handle the task"""
        delegation_map = {
            'code': 'Neo',
            'product': 'Nat',
            'data': 'Data',
            'security': 'EVE',
            'financial': 'Quark',
            'creative': 'Glyph',
            'analysis': 'Og',
            'communication': 'Joi'
        }
        
        return delegation_map.get(task_type.lower(), 'Neo')
    
    async def handle_approval_request(self, message: AgentMessage):
        """Handle approval requests from other agents"""
        task_id = message.payload.get('task_id')
        logger.info(f"Max handling approval request for task: {task_id}")
        
        # Mock approval logic
        approved = True  # Simplified for stub
        
        await self.send_message(
            message.sender,
            "approval_response",
            {
                'task_id': task_id,
                'approved': approved,
                'governance_notes': 'Approved by Max governance agent'
            }
        )
    
    async def handle_escalation(self, message: AgentMessage):
        """Handle escalation requests"""
        task_id = message.payload.get('task_id')
        reason = message.payload.get('reason', 'Unknown')
        
        logger.info(f"Max handling escalation for task: {task_id}, reason: {reason}")
        
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
                'agent': 'Max',
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
            logger.info(f"Max read PRD: {prd_path}")
            return prd_content
        except Exception as e:
            logger.error(f"Max failed to read PRD {prd_path}: {e}")
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
            logger.info(f"Max analyzed PRD requirements")
            
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
                logger.warning(f"Max could not parse LLM response as JSON, using fallback")
                # Fallback: create a basic structure from the text response
                return {
                    "core_features": ["Core Application Features", "User Interface", "Data Management", "Integration Points"],
                    "technical_requirements": ["Performance requirements", "Scalability", "Security", "Compatibility"],
                    "success_criteria": ["Functional requirements met", "Performance targets achieved", "User acceptance criteria satisfied"]
                }
            
        except Exception as e:
            logger.error(f"Max failed to analyze PRD: {e}")
            return {
                "core_features": ["Core Application Features", "User Interface", "Data Management"],
                "technical_requirements": ["Performance", "Scalability", "Security"],
                "success_criteria": ["Functional requirements", "Performance", "User acceptance"]
            }
    
    async def create_development_tasks(self, prd_analysis: Dict[str, Any], app_name: str = "application") -> List[Dict[str, Any]]:
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
            
            # Extract warm-boot sequence from the current run_id
            # The run_id is passed in the task (e.g., "run-014" -> "014")
            current_run_id = getattr(self, 'current_run_id', 'run-001')
            warm_boot_sequence = current_run_id.split("-")[1] if "-" in current_run_id else "001"
            
            app_version = f"{framework_version}.{warm_boot_sequence}"  # e.g., "0.1.4.008"
            
            # Create generic development tasks based on PRD analysis
            tasks = [
                {
                    "task_id": f"{app_kebab}-archive-{int(time.time())}",
                    "task_type": "development",
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
            
            logger.info(f"Max created {len(tasks)} development tasks for {app_name} version {app_version}")
            return tasks
            
        except Exception as e:
            logger.error(f"Max failed to create development tasks: {e}")
            return []
    
    async def process_prd_request(self, prd_path: str, run_id: str = None) -> Dict[str, Any]:
        """Process a PRD request - read PRD, analyze, and create tasks"""
        try:
            logger.info(f"Max processing PRD request: {prd_path}")
            
            # Store the current run_id for use in create_development_tasks
            if run_id:
                self.current_run_id = run_id
                logger.info(f"Max stored current run_id: {run_id}")
            
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
            tasks = await self.create_development_tasks(prd_analysis, app_name)
            if not tasks:
                return {"status": "error", "message": "Failed to create tasks"}
            
            # Delegate tasks to Neo
            delegated_tasks = []
            for task in tasks:
                delegation_target = await self.determine_delegation_target(task["task_type"])
                
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
            
            logger.info(f"Max successfully processed PRD and delegated {len(delegated_tasks)} tasks")
            
            return {
                "status": "success",
                "message": f"PRD processed and {len(delegated_tasks)} tasks delegated",
                "prd_path": prd_path,
                "tasks_delegated": delegated_tasks,
                "prd_analysis": prd_analysis
            }
            
        except Exception as e:
            logger.error(f"Max failed to process PRD request: {e}")
            return {"status": "error", "message": f"PRD processing failed: {e}"}

async def main():
    """Main entry point for Lead agent"""
    import os
    identity = os.getenv('AGENT_ID', 'lead_agent')
    agent = LeadAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
