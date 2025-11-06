"""
SqlAdapter - PostgreSQL-based memory provider for Squad Memory Pool
Implements MemoryProvider interface for Squad layer memory (validated, shared)
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncpg
from agents.memory.base import MemoryProvider

logger = logging.getLogger(__name__)

class SqlAdapter(MemoryProvider):
    """
    Adapter for PostgreSQL Squad Memory Pool.
    Handles Squad layer memory (validated, shared memories).
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize SqlAdapter with database connection pool.
        
        Args:
            db_pool: AsyncPG connection pool
        """
        self.db_pool = db_pool
    
    async def put(self, item: dict) -> str:
        """
        Store a memory item in Squad Memory Pool.
        
        Args:
            item: Dictionary with ns, agent, tags, content, importance, pid, ecid, status, validator
        
        Returns:
            Memory ID (UUID) as string
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Extract fields
                agent = item.get('agent', 'unknown')
                ns = item.get('ns', 'squad')
                pid = item.get('pid')
                ecid = item.get('ecid')
                tags = item.get('tags', [])
                importance = item.get('importance', 0.7)
                status = item.get('status', 'validated')
                validator = item.get('validator')
                content = item.get('content', {})
                
                # Insert into squad_mem_pool
                query = """
                    INSERT INTO squad_mem_pool 
                    (agent, ns, pid, ecid, tags, importance, status, validator, content)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                    RETURNING id
                """
                
                mem_id = await conn.fetchval(
                    query,
                    agent,
                    ns,
                    pid,
                    ecid,
                    tags,
                    importance,
                    status,
                    validator,
                    json.dumps(content)
                )
                
                logger.debug(f"Stored memory {mem_id} in Squad Memory Pool for agent {agent}")
                return str(mem_id)
                
        except Exception as e:
            logger.error(f"Failed to store memory in Squad Memory Pool: {e}")
            raise
    
    async def get(self, query: str, k: int = 8, **kw) -> List[dict]:
        """
        Retrieve memories from Squad Memory Pool.
        
        Args:
            query: Search query (can be tag, agent, pid, ecid, or text search)
            k: Maximum number of results
            **kw: Additional filters (agent, pid, ecid, tags, ns, status)
        
        Returns:
            List of memory dictionaries
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Build WHERE clause
                conditions = []
                params = []
                param_idx = 1
                
                # Filter by memory IDs (for direct lookup)
                if 'mem_ids' in kw and kw['mem_ids']:
                    # Convert UUID strings to UUID objects if needed
                    import uuid
                    uuid_list = []
                    for mem_id in kw['mem_ids']:
                        try:
                            uuid_list.append(uuid.UUID(mem_id) if isinstance(mem_id, str) else mem_id)
                        except ValueError:
                            logger.warning(f"Invalid UUID format: {mem_id}")
                            continue
                    if uuid_list:
                        conditions.append(f"id = ANY(${param_idx}::uuid[])")
                        params.append(uuid_list)
                        param_idx += 1
                
                # Filter by agent
                if 'agent' in kw:
                    conditions.append(f"agent = ${param_idx}")
                    params.append(kw['agent'])
                    param_idx += 1
                
                # Filter by pid
                if 'pid' in kw:
                    conditions.append(f"pid = ${param_idx}")
                    params.append(kw['pid'])
                    param_idx += 1
                
                # Filter by ecid
                if 'ecid' in kw:
                    conditions.append(f"ecid = ${param_idx}")
                    params.append(kw['ecid'])
                    param_idx += 1
                
                # Filter by namespace
                if 'ns' in kw:
                    conditions.append(f"ns = ${param_idx}")
                    params.append(kw['ns'])
                    param_idx += 1
                
                # Filter by status
                if 'status' in kw:
                    conditions.append(f"status = ${param_idx}")
                    params.append(kw['status'])
                    param_idx += 1
                
                # Filter by tags
                if 'tags' in kw and kw['tags']:
                    conditions.append(f"tags && ${param_idx}")
                    params.append(kw['tags'])
                    param_idx += 1
                
                # Text search in content
                if query:
                    conditions.append(f"content::text ILIKE ${param_idx}")
                    params.append(f"%{query}%")
                    param_idx += 1
                
                where_clause = " AND ".join(conditions) if conditions else "TRUE"
                
                # Execute query
                sql_query = f"""
                    SELECT id, agent, ns, pid, ecid, tags, importance, status, validator, content, created_at
                    FROM squad_mem_pool
                    WHERE {where_clause}
                    ORDER BY importance DESC, created_at DESC
                    LIMIT ${param_idx}
                """
                params.append(k)
                
                rows = await conn.fetch(sql_query, *params)
                
                # Convert to list of dicts
                results = []
                for row in rows:
                    results.append({
                        'id': str(row['id']),
                        'agent': row['agent'],
                        'ns': row['ns'],
                        'pid': row['pid'],
                        'ecid': row['ecid'],
                        'tags': row['tags'] or [],
                        'importance': float(row['importance']),
                        'status': row['status'],
                        'validator': row['validator'],
                        'content': json.loads(row['content']) if isinstance(row['content'], str) else row['content'],
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None
                    })
                
                logger.debug(f"Retrieved {len(results)} memories from Squad Memory Pool")
                return results
                
        except Exception as e:
            logger.error(f"Failed to retrieve memories from Squad Memory Pool: {e}")
            return []
    
    async def promote(self, mem_id: str, validator: str, to_ns: str = "squad") -> str:
        """
        Promote a memory (already in Squad Memory Pool, update status).
        
        Args:
            mem_id: Memory ID to promote
            validator: Agent performing promotion
            to_ns: Target namespace (usually 'squad')
        
        Returns:
            Memory ID
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Update memory status to validated and update namespace
                query = """
                    UPDATE squad_mem_pool
                    SET status = 'validated', validator = $1, ns = $2
                    WHERE id = $3
                    RETURNING id
                """
                
                result = await conn.fetchval(query, validator, to_ns, mem_id)
                
                if result:
                    logger.info(f"Promoted memory {mem_id} to namespace {to_ns} by {validator}")
                    return str(result)
                else:
                    logger.warning(f"Memory {mem_id} not found for promotion")
                    return mem_id
                    
        except Exception as e:
            logger.error(f"Failed to promote memory {mem_id}: {e}")
            raise

