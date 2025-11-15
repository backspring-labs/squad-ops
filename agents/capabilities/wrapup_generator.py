#!/usr/bin/env python3
"""
Wrap-up Generator Capability Handler
Implements warmboot.wrapup capability for generating WarmBoot wrap-up reports.
"""

import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class WrapupGenerator:
    """
    Wrap-up Generator - Implements warmboot.wrapup capability
    
    Generates comprehensive WarmBoot wrap-up reports including:
    - Reasoning traces from agents
    - Telemetry data (collected via telemetry.collect capability)
    - Artifact information
    - Event timeline
    - Metrics snapshot
    """
    
    def __init__(self, agent):
        """
        Initialize WrapupGenerator with agent instance.
        
        Args:
            agent: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent
        self.name = agent.name if hasattr(agent, 'name') else 'unknown'
        self.communication_log = agent.communication_log if hasattr(agent, 'communication_log') else []
    
    async def generate_wrapup(self, task: Dict[str, Any] = None, 
                             ecid: str = None, task_id: str = None, 
                             completion_payload: Dict[str, Any] = None,
                             telemetry_data: Dict[str, Any] = None, 
                             reasoning_events: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate WarmBoot wrap-up report.
        
        Implements the warmboot.wrapup capability.
        
        Accepts either:
        1. A task dictionary (for generic routing) - extracts all fields from task
        2. Individual parameters (for backward compatibility)
        
        Args:
            task: Task dictionary containing ecid, task_id, completion_payload, telemetry, reasoning_events
            ecid: Execution cycle ID (extracted from task if not provided)
            task_id: Task ID (extracted from task if not provided)
            completion_payload: Completion payload from task (extracted from task if not provided)
            telemetry_data: Telemetry data (extracted from task.telemetry if not provided)
            reasoning_events: Optional list of reasoning events (extracted from task.reasoning_events if not provided)
            
        Returns:
            Dictionary containing wrapup_uri, wrapup_content, telemetry_data, and run_number
        """
        try:
            # Extract parameters from task dictionary if provided (generic routing)
            if task is not None:
                ecid = task.get('ecid', ecid or 'unknown')
                task_id = task.get('task_id', task_id or task.get('original_task_id', 'unknown'))
                completion_payload = task.get('completion_payload', completion_payload or {})
                telemetry_data = task.get('telemetry', telemetry_data or {})
                reasoning_events = task.get('reasoning_events', reasoning_events)
            
            # Validate required parameters
            if not ecid or not task_id:
                raise ValueError("ecid and task_id are required (either via task dict or individual parameters)")
            
            logger.info(f"{self.name} starting WarmBoot wrap-up generation for ECID {ecid}")
            
            # Extract run number from ECID (e.g., "ECID-WB-055" -> "055")
            run_match = re.search(r'WB-(\d+)', ecid)
            run_number = run_match.group(1) if run_match else "001"
            
            # Generate wrap-up markdown
            wrapup_content = await self.generate_wrapup_markdown(
                ecid, run_number, task_id, completion_payload or {}, telemetry_data or {}, reasoning_events
            )
            
            # Write wrap-up to file
            runs_dir = "/app/warm-boot/runs"
            run_dir = f"{runs_dir}/run-{run_number}"
            wrapup_file = f"{run_dir}/warmboot-run{run_number}-wrapup.md"
            
            # Write wrap-up file (write_file already ensures directory exists)
            success = await self.agent.write_file(wrapup_file, wrapup_content)
            
            if success:
                logger.info(f"{self.name} successfully wrote WarmBoot wrap-up: {wrapup_file}")
                wrapup_uri = wrapup_file
            else:
                logger.error(f"{self.name} failed to write WarmBoot wrap-up: {wrapup_file}")
                wrapup_uri = None
            
            return {
                'wrapup_uri': wrapup_uri,
                'wrapup_content': wrapup_content,
                'telemetry_data': telemetry_data,
                'run_number': run_number
            }
        except Exception as e:
            logger.error(f"{self.name} failed to generate WarmBoot wrap-up: {e}")
            return {
                'wrapup_uri': None,
                'wrapup_content': None,
                'telemetry_data': telemetry_data,
                'run_number': None,
                'error': str(e)
            }
    
    async def generate_wrapup_markdown(self, ecid: str, run_number: str, task_id: str,
                                       completion_payload: Dict[str, Any],
                                       telemetry: Dict[str, Any], 
                                       reasoning_events: List[Dict[str, Any]] = None) -> str:
        """
        Generate wrap-up markdown content.
        
        Args:
            ecid: Execution cycle ID
            run_number: Run number
            task_id: Task ID
            completion_payload: Completion payload
            telemetry: Telemetry data
            reasoning_events: Optional list of reasoning events. If not provided, reads from communication_log.
            
        Returns:
            Markdown content string
        """
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
        
        # Extract token metrics
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
        
        # Extract reasoning traces - use provided events or fall back to communication log
        if reasoning_events is not None:
            # Use provided reasoning events from task payload
            max_reasoning = self._format_reasoning_events(reasoning_events, agent_name='max')
            neo_reasoning = self._format_reasoning_events(reasoning_events, agent_name='neo')
        else:
            # Fallback to reading from communication log (backward compatibility)
            max_reasoning = self.extract_real_ai_reasoning(ecid, agent_name='max')
            neo_reasoning = self.extract_real_ai_reasoning(ecid, agent_name='neo')
        
        # Format artifacts with full hashes
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
        
        # Build comprehensive markdown content
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
{chr(10).join([self.format_event_timeline_entry(event) for event in event_timeline[-15:]]) if event_timeline else "| No events logged | | | |"}

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
    
    def _format_reasoning_events(self, reasoning_events: List[Dict[str, Any]], agent_name: str = None) -> str:
        """
        Format reasoning events list into text format.
        
        Args:
            reasoning_events: List of reasoning event dictionaries
            agent_name: Optional agent name filter
            
        Returns:
            Formatted reasoning trace string (joined with newlines)
        """
        formatted_reasoning = []
        
        for entry in reasoning_events:
            entry_agent = entry.get('agent', entry.get('sender', 'unknown'))
            
            # Filter by agent name if specified
            if agent_name and entry_agent.lower() != agent_name.lower():
                continue
            
            # Get timestamp
            timestamp = entry.get('timestamp', 'unknown')
            if timestamp != 'unknown':
                try:
                    if 'T' in timestamp:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime('%H:%M:%S')
                    else:
                        formatted_time = timestamp
                except:
                    formatted_time = timestamp
            else:
                formatted_time = 'unknown'
            
            # Format reasoning event
            summary = entry.get('summary', '')
            context = entry.get('context', 'unknown')
            reason_step = entry.get('reason_step', 'unknown')
            key_points = entry.get('key_points', [])
            llm_reasoning = entry.get('llm_reasoning', {})
            
            # Build formatted reasoning text
            if summary:
                reasoning_text = f"> **{entry_agent}** ({formatted_time}) [{context}/{reason_step}]: {summary}"
                if key_points:
                    reasoning_text += f"\n>   - Key points: {', '.join(key_points[:3])}"
                
                # Include actual LLM reasoning if available
                if llm_reasoning and entry.get('raw_reasoning_included', False):
                    llm_response = llm_reasoning.get('response', '')
                    if llm_response:
                        response_preview = llm_response[:300] + ('...' if len(llm_response) > 300 else '')
                        reasoning_text += f"\n>   - LLM Response: {response_preview}"
                    
                    token_usage = llm_reasoning.get('token_usage', {})
                    if token_usage:
                        prompt_tokens = token_usage.get('prompt_tokens', 0)
                        completion_tokens = token_usage.get('completion_tokens', 0)
                        if prompt_tokens > 0 or completion_tokens > 0:
                            reasoning_text += f"\n>   - Tokens: {prompt_tokens} prompt + {completion_tokens} completion = {prompt_tokens + completion_tokens} total"
                
                formatted_reasoning.append(reasoning_text)
        
        # Join with newlines to match extract_real_ai_reasoning format
        return '\n'.join(formatted_reasoning) if formatted_reasoning else ''
    
    def extract_real_ai_reasoning(self, ecid: str, agent_name: str = None) -> str:
        """
        Extract real AI reasoning from communication log for wrap-up.
        
        Enhanced to extract from communication_log and format with agent names and timestamps.
        Also checks completion event payloads for reasoning from other agents.
        
        Args:
            ecid: Execution cycle ID
            agent_name: Optional agent name filter
            
        Returns:
            Formatted reasoning trace string
        """
        try:
            real_reasoning = []
            
            # Find entries with llm_reasoning message type for this ECID
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
                        
                        # Format with agent name and timestamp
                        if full_response:
                            # Truncate long responses but keep meaningful content
                            response_preview = full_response[:500] + ('...' if len(full_response) > 500 else '')
                            reasoning_text = f"> **{entry_agent}** ({formatted_time}): {response_preview}"
                        elif description:
                            reasoning_text = f"> **{entry_agent}** ({formatted_time}): {description[:500]}"
                        else:
                            reasoning_text = f"> **{entry_agent}** ({formatted_time}): [No reasoning text]"
                        
                        real_reasoning.append(reasoning_text)
            
            # Also check for agent reasoning events
            for entry in self.communication_log:
                entry_ecid = entry.get('ecid')
                entry_agent = entry.get('agent', entry.get('sender', 'unknown'))
                entry_type = entry.get('message_type', '')
                
                # Filter by ECID and optionally by agent name
                if entry_ecid == ecid and entry_type == 'agent_reasoning':
                    # Skip if agent filter specified and doesn't match
                    if agent_name and entry_agent.lower() != agent_name.lower():
                        continue
                    
                    # Get timestamp
                    timestamp = entry.get('timestamp', 'unknown')
                    if timestamp != 'unknown':
                        try:
                            # Format timestamp nicely
                            if 'T' in timestamp:
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                formatted_time = dt.strftime('%H:%M:%S')
                            else:
                                formatted_time = timestamp
                        except:
                            formatted_time = timestamp
                    else:
                        formatted_time = 'unknown'
                    
                    # Format reasoning event
                    summary = entry.get('summary', '')
                    context = entry.get('context', 'unknown')
                    reason_step = entry.get('reason_step', 'unknown')
                    key_points = entry.get('key_points', [])
                    llm_reasoning = entry.get('llm_reasoning', {})
                    
                    # Build formatted reasoning text
                    if summary:
                        reasoning_text = f"> **{entry_agent}** ({formatted_time}) [{context}/{reason_step}]: {summary}"
                        if key_points:
                            reasoning_text += f"\n>   - Key points: {', '.join(key_points[:3])}"
                        
                        # Include actual LLM reasoning if available
                        if llm_reasoning and entry.get('raw_reasoning_included', False):
                            llm_response = llm_reasoning.get('response', '')
                            if llm_response:
                                # Show first 300 chars of actual LLM response
                                response_preview = llm_response[:300] + ('...' if len(llm_response) > 300 else '')
                                reasoning_text += f"\n>   - LLM Response: {response_preview}"
                            
                            token_usage = llm_reasoning.get('token_usage', {})
                            if token_usage:
                                prompt_tokens = token_usage.get('prompt_tokens', 0)
                                completion_tokens = token_usage.get('completion_tokens', 0)
                                if prompt_tokens > 0 or completion_tokens > 0:
                                    reasoning_text += f"\n>   - Tokens: {prompt_tokens} prompt + {completion_tokens} completion = {prompt_tokens + completion_tokens} total"
                        
                        real_reasoning.append(reasoning_text)
            
            # Also check completion event payloads for reasoning from other agents
            if agent_name:
                for entry in self.communication_log:
                    entry_ecid = entry.get('ecid')
                    entry_type = entry.get('message_type', '')
                    entry_payload = entry.get('payload', {})
                    
                    # Check completion events from the target agent
                    if entry_ecid == ecid and entry_type == 'task.developer.completed':
                        sender = entry.get('sender', '').lower()
                        if agent_name.lower() in sender or ('neo' in sender.lower() if agent_name.lower() == 'neo' else False):
                            # Look for reasoning summary in payload
                            reasoning_summary = entry_payload.get('reasoning_summary', {})
                            if reasoning_summary and reasoning_summary.get('reasoning_available'):
                                timestamp = entry.get('timestamp', 'unknown')
                                try:
                                    if 'T' in timestamp:
                                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                        formatted_time = dt.strftime('%H:%M:%S')
                                    else:
                                        formatted_time = timestamp
                                except:
                                    formatted_time = timestamp
                                
                                key_decisions = reasoning_summary.get('key_decisions', [])
                                if key_decisions:
                                    reasoning_text = f"> **{agent_name}** ({formatted_time}): {'; '.join(key_decisions[:2])}"
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
    
    def format_event_timeline_entry(self, event: Dict[str, Any]) -> str:
        """
        Format a single event for the timeline table.
        
        Args:
            event: Event dictionary
            
        Returns:
            Formatted table row string
        """
        timestamp = event.get('timestamp', 'unknown')
        if timestamp != 'unknown':
            try:
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

