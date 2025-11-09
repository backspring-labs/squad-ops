#!/usr/bin/env python3
"""
WarmBoot Memory Handler Capability
Implements warmboot.memory capability for loading WarmBoot memories and governance logging.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class WarmBootMemoryHandler:
    """
    WarmBoot Memory Handler - Implements warmboot.memory capability
    
    Loads relevant memories for WarmBoot context and handles governance logging.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize WarmBootMemoryHandler with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        self.sql_adapter = getattr(agent_instance, 'sql_adapter', None)
        self.record_memory = agent_instance.record_memory if hasattr(agent_instance, 'record_memory') else None
    
    async def load_memories(self, ecid: Optional[str] = None, pid: Optional[str] = None) -> Dict[str, Any]:
        """
        Load relevant memories for WarmBoot context (SIP-042).
        Pre-loads agent memories from Squad Memory Pool.
        
        Implements the warmboot.memory capability.
        
        Args:
            ecid: Optional execution cycle ID
            pid: Optional process ID
            
        Returns:
            Dictionary containing memories_loaded, memory_count, and memories
        """
        try:
            if not self.sql_adapter:
                return {
                    'memories_loaded': False,
                    'memory_count': 0,
                    'memories': [],
                    'error': 'SQL adapter not available'
                }
            
            # Load from Squad Memory Pool
            kwargs = {'status': 'validated'}
            if ecid:
                kwargs['ecid'] = ecid
            if pid:
                kwargs['pid'] = pid
            
            memories = await self.sql_adapter.get("", k=20, **kwargs)
            
            if memories:
                logger.info(f"{self.name}: Loaded {len(memories)} memories for WarmBoot context (ECID: {ecid}, PID: {pid})")
                # Store in agent context for use during task processing
                if not hasattr(self.agent, 'warmboot_memories'):
                    self.agent.warmboot_memories = []
                self.agent.warmboot_memories = memories
                
                return {
                    'memories_loaded': True,
                    'memory_count': len(memories),
                    'memories': memories
                }
            else:
                logger.debug(f"{self.name}: No memories found for ECID: {ecid}, PID: {pid}")
                return {
                    'memories_loaded': False,
                    'memory_count': 0,
                    'memories': []
                }
                
        except Exception as e:
            logger.warning(f"{self.name}: Failed to load WarmBoot memories: {e}")
            return {
                'memories_loaded': False,
                'memory_count': 0,
                'memories': [],
                'error': str(e)
            }
    
    async def log_governance(self, run_id: str, manifest: Dict[str, Any], files: List[str]) -> Dict[str, Any]:
        """
        Log WarmBoot governance information (SIP-042).
        
        Implements the warmboot.memory capability for governance logging.
        
        Args:
            run_id: Run ID (e.g., "001" from ECID-WB-001)
            manifest: Architecture manifest dictionary
            files: List of created files
            
        Returns:
            Dictionary containing governance_logged status
        """
        try:
            # Extract run number from run_id if it's a full ECID
            if isinstance(run_id, str) and 'WB-' in run_id:
                import re
                match = re.search(r'WB-(\d+)', run_id)
                if match:
                    run_id = match.group(1)
            
            logger.info(f"{self.name} logging WarmBoot governance for run {run_id}")
            
            # Record governance memory
            if self.record_memory:
                await self.record_memory(
                    kind="warmboot_governance",
                    payload={
                        'run_id': run_id,
                        'manifest': manifest,
                        'files': files,
                        'file_count': len(files)
                    },
                    importance=0.8,
                    task_context={'run_id': run_id}
                )
            
            logger.info(f"{self.name} logged WarmBoot governance: run {run_id}, {len(files)} files")
            
            return {
                'governance_logged': True,
                'run_id': run_id,
                'file_count': len(files)
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to log WarmBoot governance: {e}")
            return {
                'governance_logged': False,
                'error': str(e)
            }

