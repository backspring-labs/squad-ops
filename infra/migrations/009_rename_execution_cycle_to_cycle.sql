-- Migration: Rename execution_cycle to cycle and ecid to cycle_id (SIP-0048)
-- Date: 2025-12-02
-- Purpose: Major naming refactor - execution_cycle → cycle, ecid → cycle_id
-- CRITICAL: This is a breaking change affecting the entire codebase

-- Step 1: Rename the table
ALTER TABLE execution_cycle RENAME TO cycle;

-- Step 2: Rename the primary key column
ALTER TABLE cycle RENAME COLUMN ecid TO cycle_id;

-- Step 3: Update foreign key references in agent_task_log
ALTER TABLE agent_task_log 
    DROP CONSTRAINT IF EXISTS agent_task_log_ecid_fkey,
    RENAME COLUMN ecid TO cycle_id;

-- Recreate foreign key with new column name
ALTER TABLE agent_task_log 
    ADD CONSTRAINT agent_task_log_cycle_id_fkey 
    FOREIGN KEY (cycle_id) REFERENCES cycle(cycle_id);

-- Step 4: Update foreign key references in squad_mem_pool (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'squad_mem_pool' AND column_name = 'ecid') THEN
        ALTER TABLE squad_mem_pool RENAME COLUMN ecid TO cycle_id;
    END IF;
END $$;

-- Step 5: Rename indexes
DROP INDEX IF EXISTS idx_execution_cycle_project_id;
CREATE INDEX IF NOT EXISTS idx_cycle_project_id ON cycle(project_id);

DROP INDEX IF EXISTS idx_execution_cycle_run_type;
CREATE INDEX IF NOT EXISTS idx_cycle_run_type ON cycle(run_type);

-- Step 6: Update agent_task_log indexes
DROP INDEX IF EXISTS idx_agent_task_log_ecid;
CREATE INDEX IF NOT EXISTS idx_agent_task_log_cycle_id ON agent_task_log(cycle_id);

-- Step 7: Update squad_mem_pool indexes (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_squad_mem_pool_ecid') THEN
        DROP INDEX IF EXISTS idx_squad_mem_pool_ecid;
        CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_cycle_id ON squad_mem_pool(cycle_id);
    END IF;
END $$;


