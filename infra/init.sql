-- SquadOps Database Initialization Script
-- Creates tables for task logging, metrics, and governance data

-- LangFuse database (SIP-0061) - shared Postgres instance
-- Note: CREATE DATABASE cannot run inside a transaction block,
-- so we use a DO block with exception handling.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse') THEN
        PERFORM dblink_exec('dbname=' || current_database(), 'CREATE DATABASE langfuse');
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'langfuse database may already exist or dblink not available - skipping';
END
$$;

-- Create langfuse role if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'langfuse') THEN
        CREATE USER langfuse WITH PASSWORD 'langfuse';
    END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE langfuse TO langfuse;

-- Keycloak database (SIP-0062) - shared Postgres instance
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak') THEN
        PERFORM dblink_exec('dbname=' || current_database(), 'CREATE DATABASE keycloak');
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'keycloak database may already exist or dblink not available - skipping';
END
$$;

-- Create keycloak role if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'keycloak') THEN
        CREATE USER keycloak WITH PASSWORD 'keycloak';
    END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;

-- Drop old table
DROP TABLE IF EXISTS agent_task_logs CASCADE;

-- Projects table (SIP-0047)
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);

-- Cycle table (SIP-024, SIP-0047, SIP-0048 - renamed from execution_cycle, enhanced with new fields)
CREATE TABLE IF NOT EXISTS cycle (
    cycle_id TEXT PRIMARY KEY,
    pid TEXT NOT NULL,
    project_id TEXT REFERENCES projects(project_id),
    run_type TEXT CHECK (run_type IN ('warmboot','project','experiment','tuning')),
    title TEXT,
    description TEXT,
    name TEXT,  -- SIP-0048: Human-readable cycle name
    goal TEXT,  -- SIP-0048: Cycle objective or goal statement
    start_time TIMESTAMP,  -- SIP-0048: Cycle start timestamp
    end_time TIMESTAMP,  -- SIP-0048: Cycle end timestamp
    inputs JSONB,  -- SIP-0048: Cycle inputs as JSON (PIDs, repo, branch)
    created_at TIMESTAMP DEFAULT now(),
    initiated_by TEXT,
    status TEXT DEFAULT 'active',
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_cycle_project_id ON cycle(project_id);

-- Task Log table (SIP-024/025, SIP-0048 - updated to use cycle_id, enhanced with new fields)
CREATE TABLE IF NOT EXISTS agent_task_log (
    task_id TEXT PRIMARY KEY,
    pid TEXT,
    cycle_id TEXT REFERENCES cycle(cycle_id),
    agent TEXT NOT NULL,  -- Kept for backward compatibility
    agent_id TEXT,  -- SIP-0048: Agent identifier (use agent_id, not role normalization)
    task_name TEXT,  -- SIP-0048: Task name/type identifier
    phase TEXT,
    status TEXT NOT NULL,
    priority TEXT,
    description TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration INTERVAL,
    artifacts JSONB,
    metrics JSONB,  -- SIP-0048: Task metrics as JSON
    dependencies TEXT[],
    error_log TEXT,
    delegated_by TEXT,
    delegated_to TEXT,
    created_at TIMESTAMP DEFAULT now()
);

-- Agent Status Table
-- SIP-Agent-Lifecycle: agent_id is the identifier used for all key references
-- network_status is derived by Health Check from heartbeat timing (online/offline)
-- lifecycle_state is reported by agent FSM (STARTING, READY, WORKING, BLOCKED, CRASHED, STOPPING, or UNKNOWN when offline)
CREATE TABLE IF NOT EXISTS agent_status (
    agent_id TEXT PRIMARY KEY,  -- Renamed from agent_name for consistency with task system
    network_status TEXT NOT NULL,  -- Renamed from status, derived by Health Check from heartbeat timing
    lifecycle_state TEXT,  -- Agent FSM state (nullable, set to UNKNOWN when network_status=offline)
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    current_task_id TEXT,
    version TEXT,
    tps INTEGER DEFAULT 0,
    memory_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Task Status Table
CREATE TABLE IF NOT EXISTS task_status (
    task_id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    status TEXT NOT NULL,
    progress FLOAT DEFAULT 0.0,
    eta TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks Table (Enhanced for WarmBoot)
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    assignee TEXT,
    parent_task_id TEXT,
    progress_message TEXT,
    result_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- SquadComms Messages Table
CREATE TABLE IF NOT EXISTS squadcomms_messages (
    id SERIAL PRIMARY KEY,
    message_id TEXT UNIQUE NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    message_type TEXT NOT NULL,
    payload JSONB,
    context JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE
);

-- WarmBoot Runs Table
CREATE TABLE IF NOT EXISTS warmboot_runs (
    run_id TEXT PRIMARY KEY,
    run_name TEXT NOT NULL,
    squad_config JSONB,
    benchmark_target TEXT,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status TEXT NOT NULL,
    metrics JSONB,
    scorecard JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Process Registry Table
CREATE TABLE IF NOT EXISTS process_registry (
    pid TEXT PRIMARY KEY,
    process_name TEXT NOT NULL,
    status TEXT NOT NULL,
    last_updated_version TEXT,
    change_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Optimization Log Table
CREATE TABLE IF NOT EXISTS optimization_log (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    optimization_type TEXT NOT NULL,
    before_config JSONB,
    after_config JSONB,
    performance_impact JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_agent_task_log_cycle_id ON agent_task_log(cycle_id);
CREATE INDEX IF NOT EXISTS idx_agent_task_log_agent ON agent_task_log(agent);
CREATE INDEX IF NOT EXISTS idx_agent_task_log_agent_id ON agent_task_log(agent_id);  -- SIP-0048: new index
CREATE INDEX IF NOT EXISTS idx_agent_task_log_task_name ON agent_task_log(task_name);  -- SIP-0048: new index
CREATE INDEX IF NOT EXISTS idx_agent_task_log_status ON agent_task_log(status);
CREATE INDEX IF NOT EXISTS idx_cycle_run_type ON cycle(run_type);
CREATE INDEX IF NOT EXISTS idx_cycle_project_id ON cycle(project_id);
CREATE INDEX IF NOT EXISTS idx_squadcomms_messages_sender ON squadcomms_messages(sender);
CREATE INDEX IF NOT EXISTS idx_squadcomms_messages_recipient ON squadcomms_messages(recipient);
CREATE INDEX IF NOT EXISTS idx_squadcomms_messages_timestamp ON squadcomms_messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_parent_task_id ON tasks(parent_task_id);

-- Insert initial projects (SIP-0047)
INSERT INTO projects (project_id, name, description) VALUES
('warmboot_selftest', 'WarmBoot Self-Test', 'Framework self-test execution cycles')
ON CONFLICT (project_id) DO NOTHING;

-- Insert initial process registry entries
INSERT INTO process_registry (pid, process_name, status, last_updated_version, change_notes) VALUES
('PID-001', 'HelloSquad', 'Active', 'v1.0.0', 'First reference app - FastAPI Hello World service')
ON CONFLICT (pid) DO NOTHING;

-- Insert initial agent status entries
-- SIP-Agent-Lifecycle: Use agent_id (lowercase identifier) and network_status
INSERT INTO agent_status (agent_id, network_status, lifecycle_state, version) VALUES
('max', 'offline', 'UNKNOWN', '1.0.0'),
('neo', 'offline', 'UNKNOWN', '1.0.0'),
('nat', 'offline', 'UNKNOWN', '1.0.0'),
('joi', 'offline', 'UNKNOWN', '1.0.0'),
('data', 'offline', 'UNKNOWN', '1.0.0'),
('eve', 'offline', 'UNKNOWN', '1.0.0'),
('quark', 'offline', 'UNKNOWN', '1.0.0'),
('glyph', 'offline', 'UNKNOWN', '1.0.0'),
('og', 'offline', 'UNKNOWN', '1.0.0')
ON CONFLICT (agent_id) DO NOTHING;

-- Squad Memory Pool (SIP-042)
CREATE TABLE IF NOT EXISTS squad_mem_pool (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent TEXT NOT NULL,
    ns TEXT NOT NULL DEFAULT 'squad',
    pid TEXT,
    cycle_id TEXT,
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
CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_cycle_id ON squad_mem_pool(cycle_id);
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
