-- Migration: Rename agent_name to agent_id, rename status to network_status, add lifecycle_state
-- SIP-Agent-Lifecycle: Agent Lifecycle FSM Implementation
-- Date: 2025-12-06

-- Step 1: Add new columns
ALTER TABLE agent_status 
ADD COLUMN IF NOT EXISTS agent_id TEXT,
ADD COLUMN IF NOT EXISTS network_status TEXT,
ADD COLUMN IF NOT EXISTS lifecycle_state TEXT;

-- Step 2: Copy data from old columns to new columns
UPDATE agent_status 
SET 
    agent_id = LOWER(agent_name),  -- Convert to lowercase identifier
    network_status = CASE 
        WHEN status IN ('online', 'available', 'active-non-blocking') THEN 'online'
        ELSE 'offline'
    END,
    lifecycle_state = CASE 
        WHEN status IN ('online', 'available', 'active-non-blocking') THEN NULL  -- Will be set by agent FSM
        ELSE 'UNKNOWN'  -- Offline agents have UNKNOWN lifecycle state
    END
WHERE agent_id IS NULL;

-- Step 3: Set lifecycle_state to UNKNOWN for agents with old offline status
UPDATE agent_status 
SET lifecycle_state = 'UNKNOWN'
WHERE network_status = 'offline' AND lifecycle_state IS NULL;

-- Step 4: Drop old columns (after ensuring data is migrated)
-- First, ensure we have data in new columns
DO $$
BEGIN
    -- Check if any rows have NULL agent_id (migration incomplete)
    IF EXISTS (SELECT 1 FROM agent_status WHERE agent_id IS NULL) THEN
        RAISE EXCEPTION 'Migration incomplete: Some rows have NULL agent_id';
    END IF;
    
    -- Drop old columns
    ALTER TABLE agent_status DROP COLUMN IF EXISTS agent_name;
    ALTER TABLE agent_status DROP COLUMN IF EXISTS status;
END $$;

-- Step 5: Add constraints
ALTER TABLE agent_status 
ALTER COLUMN agent_id SET NOT NULL,
ALTER COLUMN network_status SET NOT NULL;

-- Step 6: Recreate primary key constraint on agent_id
ALTER TABLE agent_status DROP CONSTRAINT IF EXISTS agent_status_pkey;
ALTER TABLE agent_status ADD PRIMARY KEY (agent_id);

-- Step 7: Add check constraint for network_status
ALTER TABLE agent_status 
ADD CONSTRAINT check_network_status 
CHECK (network_status IN ('online', 'offline'));

-- Step 8: Add check constraint for lifecycle_state
ALTER TABLE agent_status 
ADD CONSTRAINT check_lifecycle_state 
CHECK (lifecycle_state IS NULL OR lifecycle_state IN ('STARTING', 'READY', 'WORKING', 'BLOCKED', 'CRASHED', 'STOPPING', 'UNKNOWN'));

-- Step 9: Add comment explaining the columns
COMMENT ON COLUMN agent_status.agent_id IS 'Agent identifier (lowercase, e.g., "neo") - used for all key references';
COMMENT ON COLUMN agent_status.network_status IS 'Network reachability status (online/offline) - derived by Health Check from heartbeat timing';
COMMENT ON COLUMN agent_status.lifecycle_state IS 'Agent FSM lifecycle state - reported by agent, set to UNKNOWN when network_status=offline';

