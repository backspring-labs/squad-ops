-- 1699_cycle_increment_id.sql
-- #2578 part 2 (SIP-0109 §24cf): the increment a campaign cycle belongs to, its proposal's id, set
-- by the launcher from the launch's own binding. Null for a calibration and a cycle no campaign
-- launched, so every earlier row is unchanged. A projection of the control log, which stays the
-- campaign's source of truth; indexed so an increment's cycles are one lookup.

ALTER TABLE cycle_registry ADD COLUMN IF NOT EXISTS increment_id TEXT;

CREATE INDEX IF NOT EXISTS idx_cycle_registry_increment
    ON cycle_registry (increment_id) WHERE increment_id IS NOT NULL;
