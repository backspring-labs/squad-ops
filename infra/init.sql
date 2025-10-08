-- SquadOps Database Initialization Script
-- Creates tables for task logging, metrics, and governance data

-- Task Logs Table
CREATE TABLE IF NOT EXISTS agent_task_logs (
    task_id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    task_name TEXT NOT NULL,
    pid TEXT,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration INTERVAL,
    dependencies TEXT[],
    artifacts TEXT[],
    resource_utilization JSONB,
    task_status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent Status Table
CREATE TABLE IF NOT EXISTS agent_status (
    agent_name TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    current_task_id TEXT,
    version TEXT,
    tps INTEGER DEFAULT 0,
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
CREATE INDEX IF NOT EXISTS idx_agent_task_logs_agent_name ON agent_task_logs(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_task_logs_pid ON agent_task_logs(pid);
CREATE INDEX IF NOT EXISTS idx_agent_task_logs_start_time ON agent_task_logs(start_time);
CREATE INDEX IF NOT EXISTS idx_squadcomms_messages_sender ON squadcomms_messages(sender);
CREATE INDEX IF NOT EXISTS idx_squadcomms_messages_recipient ON squadcomms_messages(recipient);
CREATE INDEX IF NOT EXISTS idx_squadcomms_messages_timestamp ON squadcomms_messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_parent_task_id ON tasks(parent_task_id);

-- Insert initial process registry entries
INSERT INTO process_registry (pid, process_name, status, last_updated_version, change_notes) VALUES
('PID-001', 'HelloSquad', 'Active', 'v1.0.0', 'First reference app - FastAPI Hello World service')
ON CONFLICT (pid) DO NOTHING;

-- Insert initial agent status entries
INSERT INTO agent_status (agent_name, status, version) VALUES
('Max', 'offline', '1.0.0'),
('Neo', 'offline', '1.0.0'),
('Nat', 'offline', '1.0.0'),
('Joi', 'offline', '1.0.0'),
('Data', 'offline', '1.0.0'),
('EVE', 'offline', '1.0.0'),
('Quark', 'offline', '1.0.0'),
('Glyph', 'offline', '1.0.0'),
('Og', 'offline', '1.0.0')
ON CONFLICT (agent_name) DO NOTHING;
