-- Migration: Add display_name and role columns to agent_status table
-- Date: 2025-11-28
-- Purpose: Enable service discovery - agents provide their own metadata

ALTER TABLE agent_status 
ADD COLUMN IF NOT EXISTS display_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS role VARCHAR(50);

COMMENT ON COLUMN agent_status.display_name IS 'Human-readable display name from agent_info.json';
COMMENT ON COLUMN agent_status.role IS 'Agent role (e.g., data, qa, lead) from agent_info.json';



