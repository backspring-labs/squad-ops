-- 1610_cycle_campaign_columns.sql
-- SIP-0109 §12b, §16 (#1799): which campaign launched a cycle, why, and from which launch intent.
-- All three are nullable: a cycle no campaign launched has none, and its row is otherwise
-- unchanged (§19's compatibility criterion). source_launch_id is unique, which is what makes
-- cycle creation idempotent by launch: a re-drained intent finds its cycle instead of creating a
-- second one. No foreign keys: a cycle outlives nothing it references.
-- The kind CHECK list is CycleKind's values, held equal by test_campaign_schema.py.

ALTER TABLE cycle_registry ADD COLUMN IF NOT EXISTS campaign_id TEXT;
ALTER TABLE cycle_registry ADD COLUMN IF NOT EXISTS kind TEXT
    CHECK (kind IN ('calibration', 'increment', 'repair', 'retry'));
ALTER TABLE cycle_registry ADD COLUMN IF NOT EXISTS source_launch_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_cycle_registry_source_launch_id
    ON cycle_registry (source_launch_id);

CREATE INDEX IF NOT EXISTS idx_cycle_registry_campaign
    ON cycle_registry (campaign_id) WHERE campaign_id IS NOT NULL;
