"""
Memory Promotion Service (SIP-042)
Handles promotion of memories from agent-level (LanceDB) to Squad Memory Pool (Squad layer)
"""

import logging
from typing import Any

import asyncpg

from agents.memory.base import MemoryProvider
from agents.memory.sql_adapter import SqlAdapter

logger = logging.getLogger(__name__)

class PromotionService:
    """
    Service for promoting memories from agent-level (LanceDB) to squad-level (SQL Pool).
    Tracks reuse count and manages validation workflow.
    """
    
    def __init__(self, memory_provider: MemoryProvider, sql_adapter: SqlAdapter, db_pool: asyncpg.Pool):
        """
        Initialize promotion service.
        
        Args:
            memory_provider: MemoryProvider instance (LanceDBAdapter) for retrieving agent memories
            sql_adapter: SqlAdapter instance for storing promoted memories
            db_pool: Database connection pool for reuse tracking
        """
        self.memory_provider = memory_provider
        self.sql_adapter = sql_adapter
        self.db_pool = db_pool
    
    async def get_reuse_count(self, memory_id: str, agent_name: str) -> int:
        """
        Get reuse count for a memory.
        
        Args:
            memory_id: Memory ID
            agent_name: Agent name
        
        Returns:
            Reuse count
        """
        try:
            async with self.db_pool.acquire() as conn:
                count = await conn.fetchval("""
                    SELECT COUNT(*) 
                    FROM memory_reuse_log 
                    WHERE memory_id = $1 AND agent = $2
                """, memory_id, agent_name)
                return count or 0
        except Exception as e:
            logger.error(f"Failed to get reuse count: {e}")
            return 0
    
    async def log_memory_access(self, memory_id: str, agent_name: str, query_context: str | None = None):
        """
        Log memory access for reuse tracking.
        
        Args:
            memory_id: Memory ID
            agent_name: Agent name accessing memory
            query_context: Optional query context
        """
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO memory_reuse_log (memory_id, agent, query_context)
                    VALUES ($1, $2, $3)
                """, memory_id, agent_name, query_context)
        except Exception as e:
            logger.error(f"Failed to log memory access: {e}")
    
    async def promote_memory(self, memory_id: str, validator: str, agent_name: str, 
                           auto_promote: bool = False) -> str | None:
        """
        Promote a memory from LanceDB to Squad Memory Pool.
        
        Args:
            memory_id: Memory ID in LanceDB
            validator: Agent/entity performing promotion
            agent_name: Agent that owns the memory
            auto_promote: If True, promote automatically if reuse >= 3
        
        Returns:
            Promoted memory ID in Squad Memory Pool, or None if promotion failed
        """
        try:
            # Get reuse count
            reuse_count = await self.get_reuse_count(memory_id, agent_name)
            
            # Check if auto-promotion criteria met
            if auto_promote and reuse_count < 3:
                logger.debug(f"Memory {memory_id} not promoted: reuse count {reuse_count} < 3")
                return None
            
            # Retrieve memory from LanceDB adapter using mem_ids filter
            memories = await self.memory_provider.get("", k=1, mem_ids=[memory_id])
            memory = memories[0] if memories else None
            
            if not memory:
                logger.warning(f"Memory {memory_id} not found in LanceDB")
                return None
            
            # Prepare memory for promotion
            memory_item = {
                'agent': agent_name,
                'ns': 'squad',
                'pid': memory.get('content', {}).get('pid'),
                'cycle_id': memory.get('content', {}).get('cycle_id'),
                'tags': memory.get('tags', []),
                'importance': memory.get('importance', 0.7),
                'status': 'validated',
                'validator': validator,
                'content': memory.get('content', {})
            }
            
            # Store in Squad Memory Pool
            promoted_id = await self.sql_adapter.put(memory_item)
            
            logger.info(f"Promoted memory {memory_id} to Squad Memory Pool as {promoted_id} (reuse: {reuse_count})")
            return promoted_id
            
        except Exception as e:
            logger.error(f"Failed to promote memory {memory_id}: {e}")
            return None
    
    async def get_promoted_memories(self, agent: str | None = None, 
                                   pid: str | None = None,
                                   ecid: str | None = None,
                                   limit: int = 50) -> list[dict[str, Any]]:
        """
        Get promoted memories from Squad Memory Pool.
        
        Args:
            agent: Optional agent filter
            pid: Optional PID filter
            ecid: Optional ECID filter
            limit: Maximum results
        
        Returns:
            List of promoted memories
        """
        kwargs = {'status': 'validated'}
        if agent:
            kwargs['agent'] = agent
        if pid:
            kwargs['pid'] = pid
        if ecid:
            kwargs['ecid'] = ecid
        
        return await self.sql_adapter.get("", k=limit, **kwargs)

