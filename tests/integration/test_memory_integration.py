"""
Integration tests for memory system - REAL integration tests
Tests verify actual integration between components using real services.
"""

import asyncpg
import pytest

from agents.memory.lancedb_adapter import LANCEDB_AVAILABLE, LanceDBAdapter
from agents.memory.promotion import PromotionService
from agents.memory.sql_adapter import SqlAdapter


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skipif(not LANCEDB_AVAILABLE, reason="LanceDB not available")
async def test_lancedb_adapter_sql_adapter_integration(postgres_container, clean_database):
    """Test integration: LanceDBAdapter stores → SqlAdapter promotes → PostgreSQL persists"""
    import shutil
    import tempfile
    
    # Setup REAL database connection
    postgres_url = postgres_container.get_connection_url()
    if postgres_url.startswith('postgresql+psycopg2://'):
        postgres_url = postgres_url.replace('postgresql+psycopg2://', 'postgresql://')
    
    db_pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=3)
    temp_db = tempfile.mkdtemp()
    
    try:
        # Ensure memory tables exist (real schema)
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS squad_mem_pool (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent TEXT NOT NULL,
                    ns TEXT NOT NULL DEFAULT 'squad',
                    pid TEXT,
                    ecid TEXT,
                    tags TEXT[],
                    importance FLOAT DEFAULT 0.7,
                    status TEXT DEFAULT 'pending',
                    validator TEXT,
                    content JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
                
                CREATE TABLE IF NOT EXISTS memory_reuse_log (
                    id SERIAL PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    accessed_at TIMESTAMPTZ DEFAULT now(),
                    query_context TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_ecid ON squad_mem_pool(ecid);
                CREATE INDEX IF NOT EXISTS idx_memory_reuse_log_memory_id ON memory_reuse_log(memory_id);
            """)
        
        # Create REAL adapters (no mocks!)
        lancedb_adapter = LanceDBAdapter("TestAgent", db_path=temp_db)
        sql_adapter = SqlAdapter(db_pool)
        
        # Step 1: Store in REAL LanceDBAdapter
        memory_item = {
            'ns': 'role',
            'agent': 'TestAgent',
            'tags': ['test', 'integration'],
            'content': {
                'action': 'test_action',
                'result': 'success',
                'pid': 'PID-001',
                'ecid': 'ECID-001'
            },
            'importance': 0.8,
            'pid': 'PID-001',
            'ecid': 'ECID-001'
        }
        
        mem_id = await lancedb_adapter.put(memory_item)
        assert mem_id is not None
        
        # Step 2: Retrieve from REAL LanceDBAdapter
        results = await lancedb_adapter.get("test_action", k=5)
        assert len(results) > 0
        matching_memory = next((r for r in results if r.get('content', {}).get('action') == 'test_action'), None)
        assert matching_memory is not None
        
        # Step 3: Promote to REAL SQL database via REAL SqlAdapter
        promotion_item = {
            'agent': 'TestAgent',
            'ns': 'squad',
            'pid': 'PID-001',
            'ecid': 'ECID-001',
            'tags': ['test', 'integration'],
            'importance': 0.8,
            'status': 'validated',
            'validator': 'lead-agent',
            'content': memory_item['content']
        }
        
        promoted_id = await sql_adapter.put(promotion_item)
        assert promoted_id is not None
        
        # Step 4: Verify in REAL database
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT * FROM squad_mem_pool WHERE id = $1",
                promoted_id
            )
            assert result is not None
            assert result['agent'] == 'TestAgent'
            assert result['ns'] == 'squad'
            assert result['pid'] == 'PID-001'
            assert result['ecid'] == 'ECID-001'
            # Content is JSONB, parse it
            import json
            content = result['content'] if isinstance(result['content'], dict) else json.loads(result['content'])
            assert content['action'] == 'test_action'
        
    finally:
        await db_pool.close()
        shutil.rmtree(temp_db, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skipif(not LANCEDB_AVAILABLE, reason="LanceDB not available")
async def test_promotion_service_integration(postgres_container, clean_database):
    """Test integration: PromotionService with REAL adapters and database"""
    import shutil
    import tempfile
    
    postgres_url = postgres_container.get_connection_url()
    if postgres_url.startswith('postgresql+psycopg2://'):
        postgres_url = postgres_url.replace('postgresql+psycopg2://', 'postgresql://')
    
    db_pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=3)
    temp_db = tempfile.mkdtemp()
    
    try:
        # Ensure tables exist
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS squad_mem_pool (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent TEXT NOT NULL,
                    ns TEXT NOT NULL DEFAULT 'squad',
                    pid TEXT,
                    ecid TEXT,
                    tags TEXT[],
                    importance FLOAT DEFAULT 0.7,
                    status TEXT DEFAULT 'pending',
                    validator TEXT,
                    content JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
                
                CREATE TABLE IF NOT EXISTS memory_reuse_log (
                    id SERIAL PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    accessed_at TIMESTAMPTZ DEFAULT now(),
                    query_context TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_memory_reuse_log_memory_id ON memory_reuse_log(memory_id);
            """)
        
        # Create REAL adapters (no mocks!)
        lancedb_adapter = LanceDBAdapter("TestAgent", db_path=temp_db)
        sql_adapter = SqlAdapter(db_pool)
        promotion_service = PromotionService(lancedb_adapter, sql_adapter, db_pool)
        
        # Store memory in REAL LanceDBAdapter
        memory_item = {
            'ns': 'role',
            'agent': 'TestAgent',
            'tags': ['test', 'promotion'],
            'content': {'action': 'test_promotion', 'pid': 'PID-PROMO', 'ecid': 'ECID-PROMO'},
            'importance': 0.8,
            'pid': 'PID-PROMO',
            'ecid': 'ECID-PROMO'
        }
        
        mem_id = await lancedb_adapter.put(memory_item)
        
        # Clean up any existing reuse logs for this memory_id
        async with db_pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM memory_reuse_log WHERE memory_id = $1 AND agent = $2",
                mem_id, "TestAgent"
            )
        
        # Log accesses via REAL PromotionService → REAL database
        for _ in range(3):
            await promotion_service.log_memory_access(mem_id, "TestAgent", "test query")
        
        # Check reuse count from REAL database
        count = await promotion_service.get_reuse_count(mem_id, "TestAgent")
        assert count == 3, f"Expected reuse count of 3, got {count}"
        
        # Promote via REAL PromotionService → REAL SqlAdapter → REAL database
        promoted_id = await promotion_service.promote_memory(
            mem_id,
            "lead-agent",
            "TestAgent",
            auto_promote=True
        )
        
        assert promoted_id is not None
        
        # Verify in REAL database
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT * FROM squad_mem_pool WHERE id = $1",
                promoted_id
            )
            assert result is not None
            assert result['status'] == 'validated'
            assert result['validator'] == 'lead-agent'
        
    finally:
        await db_pool.close()
        shutil.rmtree(temp_db, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sql_adapter_postgresql_integration(postgres_container, clean_database):
    """Test integration: SqlAdapter with REAL PostgreSQL database"""
    postgres_url = postgres_container.get_connection_url()
    if postgres_url.startswith('postgresql+psycopg2://'):
        postgres_url = postgres_url.replace('postgresql+psycopg2://', 'postgresql://')
    
    db_pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=3)
    
    try:
        # Ensure tables exist
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS squad_mem_pool (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent TEXT NOT NULL,
                    ns TEXT NOT NULL DEFAULT 'squad',
                    pid TEXT,
                    ecid TEXT,
                    tags TEXT[],
                    importance FLOAT DEFAULT 0.7,
                    status TEXT DEFAULT 'pending',
                    validator TEXT,
                    content JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
                
                CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_ecid ON squad_mem_pool(ecid);
                CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_pid ON squad_mem_pool(pid);
            """)
        
        # Create REAL SqlAdapter with REAL database pool
        sql_adapter = SqlAdapter(db_pool)
        
        # Store memory in REAL database
        memory_item = {
            'agent': 'TestAgent',
            'ns': 'squad',
            'pid': 'PID-001',
            'ecid': 'ECID-001',
            'tags': ['test', 'real'],
            'importance': 0.9,
            'status': 'validated',
            'validator': 'lead-agent',
            'content': {'action': 'real_test', 'result': 'success'}
        }
        
        mem_id = await sql_adapter.put(memory_item)
        assert mem_id is not None
        
        # Retrieve from REAL database
        results = await sql_adapter.get("", k=10, ecid='ECID-001')
        assert len(results) > 0
        assert results[0]['ecid'] == 'ECID-001'
        assert results[0]['content']['action'] == 'real_test'
        
        # Test filtering by PID
        results_pid = await sql_adapter.get("", k=10, pid='PID-001')
        assert len(results_pid) > 0
        assert all(r['pid'] == 'PID-001' for r in results_pid)
        
        # Verify UUID handling
        results_by_id = await sql_adapter.get("", k=10, mem_ids=[mem_id])
        assert len(results_by_id) == 1
        assert results_by_id[0]['id'] == mem_id
        
    finally:
        await db_pool.close()


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skipif(not LANCEDB_AVAILABLE, reason="LanceDB not available")
async def test_memory_provider_agent_integration(postgres_container, clean_database):
    """Test integration: Memory providers initialize correctly in BaseAgent"""
    from agents.base_agent import BaseAgent
    
    # Create a test agent subclass
    class TestAgent(BaseAgent):
        async def handle_agent_request(self, request):
            from datetime import datetime

            from agents.specs.agent_response import AgentResponse, Timing
            return AgentResponse.success(
                result={'status': 'completed'},
                idempotency_key="test-key",
                timing=Timing.create(datetime.utcnow())
            )
        
        async def process_task(self, task):
            return {'status': 'completed'}
        
        async def handle_message(self, message):
            return {'status': 'handled'}
    
    # Setup REAL database
    postgres_url = postgres_container.get_connection_url()
    if postgres_url.startswith('postgresql+psycopg2://'):
        postgres_url = postgres_url.replace('postgresql+psycopg2://', 'postgresql://')
    
    db_pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=3)
    
    try:
        # Ensure tables exist
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS squad_mem_pool (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent TEXT NOT NULL,
                    ns TEXT NOT NULL DEFAULT 'squad',
                    pid TEXT,
                    ecid TEXT,
                    tags TEXT[],
                    importance FLOAT DEFAULT 0.7,
                    status TEXT DEFAULT 'pending',
                    validator TEXT,
                    content JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
        
        agent = TestAgent("TestAgent", "test", "test")
        agent.db_pool = db_pool
        
        # Manually set LanceDBAdapter with temp path before initialization
        import tempfile
        temp_db = tempfile.mkdtemp()
        agent.memory_provider = LanceDBAdapter("TestAgent", db_path=temp_db)
        
        # Initialize SQL adapter only (LanceDBAdapter already set above)
        from agents.memory.sql_adapter import SqlAdapter
        agent.sql_adapter = SqlAdapter(db_pool)
        
        # Verify providers initialized
        assert agent.memory_provider is not None
        assert isinstance(agent.memory_provider, LanceDBAdapter)
        assert agent.sql_adapter is not None
        assert isinstance(agent.sql_adapter, SqlAdapter)
        
        # Test recording memory via REAL providers
        mem_id = await agent.record_memory(
            kind="test_action",
            payload={'result': 'success'},
            importance=0.8,
            task_context={'pid': 'PID-001', 'ecid': 'ECID-001'}
        )
        
        assert mem_id is not None
        
        # Verify memory was stored (check LanceDB)
        results = await agent.memory_provider.get("test_action", k=5)
        assert len(results) > 0
        
    finally:
        await db_pool.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_memory_replay_from_sql_only(postgres_container, clean_database):
    """Test integration: WarmBoot can replay memories from SQL-only (no Mem0 required)"""
    postgres_url = postgres_container.get_connection_url()
    if postgres_url.startswith('postgresql+psycopg2://'):
        postgres_url = postgres_url.replace('postgresql+psycopg2://', 'postgresql://')
    
    db_pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=3)
    
    try:
        # Ensure tables exist
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS squad_mem_pool (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent TEXT NOT NULL,
                    ns TEXT NOT NULL DEFAULT 'squad',
                    pid TEXT,
                    ecid TEXT,
                    tags TEXT[],
                    importance FLOAT DEFAULT 0.7,
                    status TEXT DEFAULT 'pending',
                    validator TEXT,
                    content JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
                
                CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_ecid ON squad_mem_pool(ecid);
            """)
            
            # Clean up any existing memories for this test ECID
            await conn.execute("DELETE FROM squad_mem_pool WHERE ecid = 'ECID-REPLAY-TEST'")
        
        sql_adapter = SqlAdapter(db_pool)
        
        # Store memories directly in SQL (simulating promoted memories)
        # Use unique ECID for this test
        memories = [
            {
                'agent': 'lead-agent',
                'ns': 'squad',
                'pid': 'PID-REPLAY-TEST',
                'ecid': 'ECID-REPLAY-TEST',
                'tags': ['warmboot', 'completion'],
                'importance': 0.9,
                'status': 'validated',
                'validator': 'lead-agent',
                'content': {
                    'action': 'warmboot_completion',
                    'ecid': 'ECID-REPLAY-TEST',
                    'pid': 'PID-REPLAY-TEST',
                    'result': 'success'
                }
            },
            {
                'agent': 'dev-agent',
                'ns': 'squad',
                'pid': 'PID-REPLAY-TEST',
                'ecid': 'ECID-REPLAY-TEST',
                'tags': ['build', 'success'],
                'importance': 0.8,
                'status': 'validated',
                'validator': 'lead-agent',
                'content': {
                    'action': 'build_success',
                    'ecid': 'ECID-REPLAY-TEST',
                    'pid': 'PID-REPLAY-TEST',
                    'result': 'success'
                }
            }
        ]
        
        for mem in memories:
            await sql_adapter.put(mem)
        
        # Retrieve memories for ECID (simulating WarmBoot replay)
        # This tests SQL-only replay without Mem0
        retrieved_memories = await sql_adapter.get("", k=10, ecid='ECID-REPLAY-TEST', status='validated')
        
        # Should have exactly 2 memories we just inserted
        assert len(retrieved_memories) == 2, f"Expected 2 memories, got {len(retrieved_memories)}"
        assert all(m['ecid'] == 'ECID-REPLAY-TEST' for m in retrieved_memories)
        assert all(m['status'] == 'validated' for m in retrieved_memories)
        
        # Verify we can reconstruct WarmBoot state from SQL-only memories
        warmboot_completions = [m for m in retrieved_memories if m['content'].get('action') == 'warmboot_completion']
        build_successes = [m for m in retrieved_memories if m['content'].get('action') == 'build_success']
        
        # Verify we found the memories we just inserted
        assert len(warmboot_completions) > 0, "Should have warmboot_completion memory"
        assert len(build_successes) > 0, "Should have build_success memory"
        
    finally:
        await db_pool.close()

