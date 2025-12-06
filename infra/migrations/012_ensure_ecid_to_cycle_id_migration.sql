-- Migration: Ensure all ecid columns are renamed to cycle_id (SIP-0048)
-- Date: 2025-12-03
-- Purpose: Final migration to ensure all ecid columns are renamed to cycle_id
-- This migration is idempotent and safe to run multiple times

-- Step 1: Ensure squad_mem_pool.ecid is renamed to cycle_id (if not already done)
DO $$
BEGIN
    -- Check if ecid column exists and rename it
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'squad_mem_pool' 
        AND column_name = 'ecid'
        AND table_schema = 'public'
    ) THEN
        ALTER TABLE squad_mem_pool RENAME COLUMN ecid TO cycle_id;
        RAISE NOTICE 'Renamed squad_mem_pool.ecid to cycle_id';
    ELSE
        RAISE NOTICE 'squad_mem_pool.ecid column does not exist (already migrated or never existed)';
    END IF;
END $$;

-- Step 2: Ensure index is renamed (if not already done)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_squad_mem_pool_ecid'
        AND schemaname = 'public'
    ) THEN
        DROP INDEX IF EXISTS idx_squad_mem_pool_ecid;
        CREATE INDEX IF NOT EXISTS idx_squad_mem_pool_cycle_id ON squad_mem_pool(cycle_id);
        RAISE NOTICE 'Renamed index idx_squad_mem_pool_ecid to idx_squad_mem_pool_cycle_id';
    ELSE
        RAISE NOTICE 'Index idx_squad_mem_pool_ecid does not exist (already migrated or never existed)';
    END IF;
END $$;

-- Step 3: Verify migration completed successfully
DO $$
DECLARE
    column_exists BOOLEAN;
    index_exists BOOLEAN;
BEGIN
    -- Check if cycle_id column exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'squad_mem_pool' 
        AND column_name = 'cycle_id'
        AND table_schema = 'public'
    ) INTO column_exists;
    
    -- Check if cycle_id index exists
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_squad_mem_pool_cycle_id'
        AND schemaname = 'public'
    ) INTO index_exists;
    
    IF column_exists AND index_exists THEN
        RAISE NOTICE 'Migration completed successfully: squad_mem_pool.cycle_id column and index exist';
    ELSIF column_exists THEN
        RAISE WARNING 'Migration partially complete: cycle_id column exists but index is missing';
    ELSE
        RAISE WARNING 'Migration may have failed: cycle_id column not found';
    END IF;
END $$;

