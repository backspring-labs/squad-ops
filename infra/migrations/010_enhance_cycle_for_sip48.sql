-- Migration: Enhance cycle table with SIP-0048 fields
-- Date: 2025-12-02
-- Purpose: Add name, goal, start_time, end_time, and inputs JSONB to cycle table

-- Add new columns to cycle table
ALTER TABLE cycle 
    ADD COLUMN IF NOT EXISTS name TEXT,
    ADD COLUMN IF NOT EXISTS goal TEXT,
    ADD COLUMN IF NOT EXISTS start_time TIMESTAMP,
    ADD COLUMN IF NOT EXISTS end_time TIMESTAMP,
    ADD COLUMN IF NOT EXISTS inputs JSONB;

-- Update existing rows with defaults where possible
-- Use title as name if name is null
UPDATE cycle 
SET name = COALESCE(name, title, 'Unnamed Cycle')
WHERE name IS NULL;

-- Use description as goal if goal is null
UPDATE cycle 
SET goal = COALESCE(goal, description, 'No goal specified')
WHERE goal IS NULL;

-- Set start_time to created_at if start_time is null
UPDATE cycle 
SET start_time = COALESCE(start_time, created_at)
WHERE start_time IS NULL;

-- Initialize inputs as empty JSON object if null
UPDATE cycle 
SET inputs = COALESCE(inputs, '{}'::jsonb)
WHERE inputs IS NULL;

-- Add comment to document the new fields
COMMENT ON COLUMN cycle.name IS 'Human-readable cycle name (SIP-0048)';
COMMENT ON COLUMN cycle.goal IS 'Cycle objective or goal statement (SIP-0048)';
COMMENT ON COLUMN cycle.start_time IS 'Cycle start timestamp (SIP-0048)';
COMMENT ON COLUMN cycle.end_time IS 'Cycle end timestamp (SIP-0048)';
COMMENT ON COLUMN cycle.inputs IS 'Cycle inputs as JSON: PIDs, repo, branch (SIP-0048)';


