-- SIP-0101 Slice 2: workload-boundary checkpoints survive the max_keep prune.
-- Additive + default-false: pre-migration rows read as unretained (prunable),
-- old code ignores the column entirely (1010-pattern compatibility). Forward-only.
ALTER TABLE run_checkpoints ADD COLUMN IF NOT EXISTS retained BOOLEAN NOT NULL DEFAULT FALSE;
