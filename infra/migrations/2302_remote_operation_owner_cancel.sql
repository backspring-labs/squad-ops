-- 2302_remote_operation_owner_cancel.sql
-- SIP-0117 R5.30 (#3236): an abort governs its remote operations.
--
-- An operation's origin names whose it is: the cycle it verifies for, and the Campaign when the
-- cycle is one's and the asker knows it. A cycle's cancel and a Campaign's abort ask every operation they own
-- that has no result yet to stop. The origin stays the one record of the owner: the two indexes
-- read it, and nothing copies it.
--
-- A row queued before this shape names no owner in its origin. No cancel finds it by owner, and
-- it ends as it always did: by its result, its requester's cancel, or its lease.

-- A worker's result that arrived after its operation was asked to stop: kept for the record, and
-- no evidence. The operation's own result then reads interrupted.
ALTER TABLE remote_operations ADD COLUMN IF NOT EXISTS late_result JSONB;

-- An owner's operations still without a result: what its cancel stops.
CREATE INDEX IF NOT EXISTS ix_remote_operations_unsettled_by_cycle
    ON remote_operations ((origin ->> 'cycle_id'), created_at) WHERE state <> 'settled';
CREATE INDEX IF NOT EXISTS ix_remote_operations_unsettled_by_campaign
    ON remote_operations ((origin ->> 'campaign_id'), created_at) WHERE state <> 'settled';

-- Each owner that was cancelled, and when. Nothing new is queued for one: a play asked for after
-- a cycle's cancel would run for nobody. The first cancel is kept, and a repeat changes nothing.
CREATE TABLE IF NOT EXISTS remote_operation_cancelled_owners (
    owner_key     TEXT        NOT NULL CHECK (owner_key IN ('cycle_id', 'campaign_id')),
    owner_value   TEXT        NOT NULL,
    cancelled_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (owner_key, owner_value)
);

-- An attempt whose result arrived after its operation was asked to stop. The list is the
-- AttemptOutcome vocabulary (tests/unit/remote_execution/test_migration_vocabularies.py).
ALTER TABLE remote_operation_attempts
    DROP CONSTRAINT IF EXISTS remote_operation_attempts_outcome_check;
ALTER TABLE remote_operation_attempts ADD CONSTRAINT remote_operation_attempts_outcome_check
    CHECK (outcome IN ('accepted', 'expired', 'cancelled'));
