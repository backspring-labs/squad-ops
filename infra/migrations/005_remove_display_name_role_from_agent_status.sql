-- Migration: Remove display_name and role columns from agent_status table
-- Date: 2025-01-28
-- Purpose: Clean up unused columns - health-check now uses instances.yaml for display metadata

ALTER TABLE agent_status DROP COLUMN IF EXISTS display_name;
ALTER TABLE agent_status DROP COLUMN IF EXISTS role;

