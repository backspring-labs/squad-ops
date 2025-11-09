-- Migration: Clean up obsolete agent_status entries
-- Date: 2025-11-05
-- Purpose: Remove agent_status entries for agents not in instances.yaml

-- Delete agent_status entries for agents not in instances.yaml
-- Valid agents based on instances.yaml: max, neo, strat-agent, creative-agent, 
-- data-agent, qa-agent, finance-agent, comms-agent, curator-agent, audit-agent

DELETE FROM agent_status
WHERE agent_name NOT IN (
    'max', 'neo', 'strat-agent', 'creative-agent', 'data-agent', 
    'qa-agent', 'finance-agent', 'comms-agent', 'curator-agent', 'audit-agent'
);

-- Log the cleanup
DO $$
BEGIN
    RAISE NOTICE 'Cleaned up obsolete agent_status entries';
END $$;




