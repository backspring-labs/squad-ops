-- Squad Memory Pool Migration (SIP-042)
-- Creates table for validated, squad-level memories

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

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_agent ON squad_mem_pool(agent);
CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_ns ON squad_mem_pool(ns);
CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_pid ON squad_mem_pool(pid);
CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_ecid ON squad_mem_pool(ecid);
CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_tags ON squad_mem_pool USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_status ON squad_mem_pool(status);
CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_created_at ON squad_mem_pool(created_at DESC);

-- Memory reuse tracking (optional enhancement)
CREATE TABLE IF NOT EXISTS memory_reuse_log (
    id SERIAL PRIMARY KEY,
    memory_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    accessed_at TIMESTAMPTZ DEFAULT now(),
    query_context TEXT
);

CREATE INDEX IF NOT EXISTS idx_memory_reuse_log_memory_id ON memory_reuse_log(memory_id);
CREATE INDEX IF NOT EXISTS idx_memory_reuse_log_agent ON memory_reuse_log(agent);

