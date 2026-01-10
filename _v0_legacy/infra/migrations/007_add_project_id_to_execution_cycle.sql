-- Migration: Add project_id to execution_cycle table (SIP-0047)
-- Date: 2025-01-29
-- Purpose: Link execution cycles to projects via foreign key

-- Add project_id column to execution_cycle table
ALTER TABLE execution_cycle 
ADD COLUMN IF NOT EXISTS project_id TEXT REFERENCES projects(project_id);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_execution_cycle_project_id ON execution_cycle(project_id);

