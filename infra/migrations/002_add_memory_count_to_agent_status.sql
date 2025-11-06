-- Migration: Add memory_count column to agent_status table
-- Date: 2025-01-XX
-- Purpose: Track agent memory count from LanceDB

ALTER TABLE agent_status 
ADD COLUMN IF NOT EXISTS memory_count INTEGER DEFAULT 0;

COMMENT ON COLUMN agent_status.memory_count IS 'Number of memories stored in LanceDB for this agent';

