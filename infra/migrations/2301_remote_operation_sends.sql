-- 2301_remote_operation_sends.sql
-- SIP-0117 R5.6: one operation per send of a task. An agent's request names the task and the
-- send (the dispatch id the runtime minted for it, #2932). A repeat of a send's request returns
-- the operation it already queued, and a newer send of the task stops the older sends' ones.
--
-- Both columns are read from the stored request, so the request stays the one record of them.
-- A row queued before this shape (a rehearsal row: no deploy queued one before 2.8) has no
-- task_id in its request; its columns are NULL and no send matches it.

ALTER TABLE remote_operations
    ADD COLUMN IF NOT EXISTS task_id TEXT GENERATED ALWAYS AS (request ->> 'task_id') STORED;
ALTER TABLE remote_operations
    ADD COLUMN IF NOT EXISTS dispatch_id TEXT
        GENERATED ALWAYS AS (request ->> 'dispatch_id') STORED;

-- A send asks for one operation.
CREATE UNIQUE INDEX IF NOT EXISTS uq_remote_operations_one_per_send
    ON remote_operations (task_id, dispatch_id) WHERE task_id IS NOT NULL;
-- A task's operations still without a result: what a newer send stops.
CREATE INDEX IF NOT EXISTS ix_remote_operations_unsettled_by_task
    ON remote_operations (task_id, created_at) WHERE state <> 'settled';
