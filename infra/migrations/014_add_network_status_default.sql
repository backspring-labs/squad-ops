-- Migration: Add DEFAULT 'offline' to network_status column
-- SIP-Agent-Lifecycle: Network status should only be managed by reconciliation loop
-- Date: 2025-12-07

-- Add DEFAULT 'offline' to network_status column
-- This ensures that when heartbeat handler inserts a new row, network_status gets
-- a safe default value, and only the reconciliation loop updates it based on timing.
ALTER TABLE agent_status 
ALTER COLUMN network_status SET DEFAULT 'offline';

-- Add comment explaining the default
COMMENT ON COLUMN agent_status.network_status IS 
'Network reachability status (online/offline) - derived by Health Check reconciliation loop from heartbeat timing. Default is "offline" (safe default until reconciliation loop sets it to "online" based on recent heartbeats).';

