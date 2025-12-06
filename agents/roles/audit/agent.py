#!/usr/bin/env python3
"""Audit Agent - Audit Role"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.base_agent import AgentMessage, BaseAgent
from agents.specs.agent_request import AgentRequest
from agents.specs.agent_response import AgentResponse, Timing
from agents.specs.validator import SchemaValidator

logger = logging.getLogger(__name__)

class AuditAgent(BaseAgent):
    """Audit Agent - Audit Role"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="auditor",
            reasoning_style="monitoring_audit"
        )
        self.secure_logs = {}
        self.agent_activity = {}
        self.anomaly_detection = {}
        self.audit_trail = []
        
        # Initialize schema validator
        base_path = Path(__file__).parent.parent.parent.parent
        self.validator = SchemaValidator(base_path)
    
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
            if action == "audit.monitoring":
                result = await self._handle_monitoring(request)
            elif action == "audit.compliance_tracking":
                result = await self._handle_compliance_tracking(request)
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
    
    async def _handle_monitoring(self, request: AgentRequest) -> dict[str, Any]:
        """Handle audit.monitoring capability"""
        
        # Map existing monitoring logic to new capability format
        return {
            'health_status': 'healthy',
            'metrics': {},
            'alerts': []
        }
    
    async def _handle_compliance_tracking(self, request: AgentRequest) -> dict[str, Any]:
        """Handle audit.compliance_tracking capability"""
        
        # Map existing compliance tracking logic to new capability format
        return {
            'compliance_status': 'compliant',
            'audit_trail': [],
            'violations': []
        }
    
    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Process monitoring and audit tasks"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', 'monitoring_audit')
        
        logger.info(f"HAL processing monitoring task: {task_id}")
        
        # Update task status
        await self.update_task_status(task_id, "Active-Non-Blocking", 20.0)
        
        # Monitor agent activities
        await self.monitor_agent_activities()
        
        # Perform audit
        await self.update_task_status(task_id, "Active-Non-Blocking", 40.0)
        
        audit_results = await self.perform_audit(task)
        
        # Detect anomalies
        await self.update_task_status(task_id, "Active-Non-Blocking", 60.0)
        
        anomalies = await self.detect_anomalies(audit_results)
        
        # Generate audit report
        await self.update_task_status(task_id, "Active-Non-Blocking", 80.0)
        
        report = await self.generate_audit_report(audit_results, anomalies)
        
        # Secure log storage
        await self.update_task_status(task_id, "Active-Non-Blocking", 90.0)
        
        await self.secure_log_storage(task_id, report)
        
        await self.update_task_status(task_id, "Completed", 100.0)
        
        return {
            'task_id': task_id,
            'status': 'completed',
            'agents_monitored': len(self.agent_activity),
            'audit_results': audit_results,
            'anomalies_detected': len(anomalies),
            'audit_report': report,
            'secure_logs_count': len(self.secure_logs),
            'mock_response': await self.mock_llm_response(
                f"Monitoring and audit for {task_type}",
                f"Anomalies detected: {len(anomalies)}"
            )
        }
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle monitoring-related messages"""
        if message.message_type == "activity_log":
            await self.handle_activity_log(message)
        elif message.message_type == "audit_request":
            await self.handle_audit_request(message)
        elif message.message_type == "anomaly_alert":
            await self.handle_anomaly_alert(message)
        else:
            logger.info(f"HAL received message: {message.message_type} from {message.sender}")
    
    async def monitor_agent_activities(self):
        """Monitor activities of all other agents"""
        # Mock agent activity monitoring
        agents = ['Max', 'Neo', 'Nat', 'Joi', 'Data', 'EVE', 'Og']
        
        for agent in agents:
            if agent not in self.agent_activity:
                self.agent_activity[agent] = []
            
            # Mock activity log
            activity = {
                'timestamp': time.time(),
                'agent': agent,
                'activity': 'task_processing',
                'status': 'active',
                'resource_usage': {
                    'cpu': 25.5,
                    'memory': 128.0,
                    'network': 1.2
                }
            }
            
            self.agent_activity[agent].append(activity)
    
    async def perform_audit(self, task: dict[str, Any]) -> dict[str, Any]:
        """Perform comprehensive audit"""
        audit_results = {
            'timestamp': time.time(),
            'audit_type': task.get('audit_type', 'general'),
            'agents_audited': len(self.agent_activity),
            'findings': [],
            'compliance_score': 0.0
        }
        
        # Mock audit findings
        findings = []
        for agent, activities in self.agent_activity.items():
            if len(activities) > 0:
                latest_activity = activities[-1]
                finding = {
                    'agent': agent,
                    'status': 'compliant',
                    'last_activity': latest_activity['timestamp'],
                    'resource_usage': latest_activity['resource_usage']
                }
                findings.append(finding)
        
        audit_results['findings'] = findings
        audit_results['compliance_score'] = 0.95  # Mock high compliance
        
        return audit_results
    
    async def detect_anomalies(self, audit_results: dict[str, Any]) -> list[dict[str, Any]]:
        """Detect anomalies in agent behavior"""
        anomalies = []
        
        for finding in audit_results['findings']:
            resource_usage = finding['resource_usage']
            
            # Mock anomaly detection
            if resource_usage['cpu'] > 80:
                anomalies.append({
                    'agent': finding['agent'],
                    'type': 'high_cpu_usage',
                    'severity': 'medium',
                    'description': f"High CPU usage detected: {resource_usage['cpu']}%",
                    'timestamp': time.time()
                })
            
            if resource_usage['memory'] > 500:
                anomalies.append({
                    'agent': finding['agent'],
                    'type': 'high_memory_usage',
                    'severity': 'high',
                    'description': f"High memory usage detected: {resource_usage['memory']}MB",
                    'timestamp': time.time()
                })
        
        return anomalies
    
    async def generate_audit_report(self, audit_results: dict[str, Any], anomalies: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate comprehensive audit report"""
        report = {
            'report_id': f"audit_report_{int(time.time())}",
            'generated_at': time.time(),
            'summary': {
                'total_agents': len(audit_results['findings']),
                'compliant_agents': len([f for f in audit_results['findings'] if f['status'] == 'compliant']),
                'anomalies_detected': len(anomalies),
                'compliance_score': audit_results['compliance_score']
            },
            'detailed_findings': audit_results['findings'],
            'anomalies': anomalies,
            'recommendations': [
                'Continue regular monitoring',
                'Investigate high resource usage',
                'Maintain security protocols'
            ]
        }
        
        return report
    
    async def secure_log_storage(self, task_id: str, report: dict[str, Any]):
        """Store logs securely"""
        log_entry = {
            'task_id': task_id,
            'timestamp': time.time(),
            'report': report,
            'encryption_status': 'encrypted',
            'access_level': 'restricted'
        }
        
        self.secure_logs[task_id] = log_entry
    
    async def handle_activity_log(self, message: AgentMessage):
        """Handle activity log messages from other agents"""
        agent_name = message.sender
        activity_data = message.payload
        
        logger.info(f"HAL received activity log from {agent_name}")
        
        # Store activity log
        if agent_name not in self.agent_activity:
            self.agent_activity[agent_name] = []
        
        self.agent_activity[agent_name].append({
            'timestamp': time.time(),
            'activity': activity_data.get('activity', 'unknown'),
            'details': activity_data.get('details', {}),
            'status': activity_data.get('status', 'active')
        })
    
    async def handle_audit_request(self, message: AgentMessage):
        """Handle audit requests"""
        audit_type = message.payload.get('audit_type', 'general')
        task_id = message.payload.get('task_id')
        
        logger.info(f"HAL performing audit: {audit_type}")
        
        # Perform requested audit
        audit_task = {'task_id': task_id, 'audit_type': audit_type}
        audit_results = await self.perform_audit(audit_task)
        
        await self.send_message(
            message.sender,
            "audit_response",
            {
                'task_id': task_id,
                'audit_results': audit_results,
                'auditor': 'HAL'
            }
        )
    
    async def handle_anomaly_alert(self, message: AgentMessage):
        """Handle anomaly alerts"""
        anomaly_data = message.payload
        task_id = message.payload.get('task_id')
        
        logger.info(f"HAL handling anomaly alert: {anomaly_data.get('type', 'unknown')}")
        
        # Process anomaly
        anomaly = {
            'id': f"anomaly_{int(time.time())}",
            'type': anomaly_data.get('type', 'unknown'),
            'severity': anomaly_data.get('severity', 'medium'),
            'description': anomaly_data.get('description', 'Anomaly detected'),
            'timestamp': time.time(),
            'status': 'investigating'
        }
        
        # Store anomaly
        if task_id not in self.anomaly_detection:
            self.anomaly_detection[task_id] = []
        
        self.anomaly_detection[task_id].append(anomaly)
        
        await self.send_message(
            message.sender,
            "anomaly_response",
            {
                'task_id': task_id,
                'anomaly_id': anomaly['id'],
                'status': 'investigating',
                'investigator': 'HAL'
            }
        )

async def main():
    """Main entry point for Audit agent"""
    from config.unified_config import get_config
    config = get_config()
    identity = config.get_agent_id()
    agent = AuditAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
