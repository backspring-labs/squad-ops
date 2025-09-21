#!/usr/bin/env python3
"""
HAL - Monitoring and Audit Agent
Reasoning Style: Monitoring and audit
Memory Structure: Secure log storage
Task Model: Continuous monitoring
Local Model: LLaMA 3 70B (mocked)
Premium Consultation: Anomaly detection
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from base_agent import BaseAgent, AgentMessage
import time

logger = logging.getLogger(__name__)

class HALAgent(BaseAgent):
    """HAL - The Monitoring and Audit Agent"""
    
    def __init__(self):
        super().__init__(
            name="HAL",
            agent_type="monitoring",
            reasoning_style="monitoring_audit"
        )
        self.secure_logs = {}
        self.agent_activity = {}
        self.anomaly_detection = {}
        self.audit_trail = []
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
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
    
    async def perform_audit(self, task: Dict[str, Any]) -> Dict[str, Any]:
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
    
    async def detect_anomalies(self, audit_results: Dict[str, Any]) -> List[Dict[str, Any]]:
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
    
    async def generate_audit_report(self, audit_results: Dict[str, Any], anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
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
    
    async def secure_log_storage(self, task_id: str, report: Dict[str, Any]):
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
    """Main entry point for HAL agent"""
    agent = HALAgent()
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
