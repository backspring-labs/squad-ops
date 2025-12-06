-- Migration: Enhance agent_task_log table with SIP-0048 fields
-- Date: 2025-12-02
-- Purpose: Add agent_id, task_name, and metrics JSONB to agent_task_log table

-- Add new columns to agent_task_log table
ALTER TABLE agent_task_log 
    ADD COLUMN IF NOT EXISTS agent_id TEXT,
    ADD COLUMN IF NOT EXISTS task_name TEXT,
    ADD COLUMN IF NOT EXISTS metrics JSONB;

-- Migrate existing data: use agent field as agent_id if agent_id is null
UPDATE agent_task_log 
SET agent_id = COALESCE(agent_id, agent)
WHERE agent_id IS NULL;

-- Use description as task_name if task_name is null and description exists
UPDATE agent_task_log 
SET task_name = COALESCE(task_name, LEFT(description, 100))
WHERE task_name IS NULL AND description IS NOT NULL;

-- Initialize metrics as empty JSON object if null
UPDATE agent_task_log 
SET metrics = COALESCE(metrics, '{}'::jsonb)
WHERE metrics IS NULL;

-- Add indexes for new fields
CREATE INDEX IF NOT EXISTS idx_agent_task_log_agent_id ON agent_task_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_task_log_task_name ON agent_task_log(task_name);

-- Add comments to document the new fields
COMMENT ON COLUMN agent_task_log.agent_id IS 'Agent identifier (SIP-0048: use agent_id, not role normalization)';
COMMENT ON COLUMN agent_task_log.task_name IS 'Task name/type identifier (SIP-0048)';
COMMENT ON COLUMN agent_task_log.metrics IS 'Task metrics as JSON (SIP-0048)';

-- Note: agent field is kept for backward compatibility but agent_id should be used going forward


