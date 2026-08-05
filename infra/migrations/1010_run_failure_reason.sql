-- 1010_run_failure_reason.sql
-- #427 (1.4.4 fix 1): persist the terminal failure reason on the run row.
-- A failed run's exception was recoverable nowhere — runs show gave a bare
-- `status: failed` and the report pointed at task artifacts that may not exist
-- (a pre-dispatch failure produces none). The finalize path already holds the
-- exception; this column is where it lands. Nullable: only FAILED runs carry
-- one, and only those failed after this migration.

ALTER TABLE cycle_runs ADD COLUMN IF NOT EXISTS failure_reason TEXT;
