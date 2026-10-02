-- 1051_cycle_deploy_id.sql
-- #1720: the deploy a cycle was created on. 1040 records the runtime API's own commit; this
-- references the deploy record (1050) current at create, which names every service's image and
-- the models' weights. Nullable on purpose, as 1040's columns are: a cycle created before any
-- deploy was recorded has no deploy, and NULL says "unknown" where a backfill would invent one.
-- No foreign key: a deploy record is evidence about a cycle, not a parent it cannot outlive.

ALTER TABLE cycle_registry
    ADD COLUMN IF NOT EXISTS deploy_id TEXT;
