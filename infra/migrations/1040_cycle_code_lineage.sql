-- 1040_cycle_code_lineage.sql
-- #80 (1.8.0 plan §3.2): the code a cycle was created on. request_profile (007) already
-- records which profile; these record which framework version and which commit, so the
-- scorecard's benchmark registry (SIP-0108) can slice cycles by code lineage.
-- Nullable on purpose: a cycle created before this migration has no lineage, and NULL says
-- "unknown" where a backfilled value would invent one. All DDL is idempotent.

ALTER TABLE cycle_registry
    ADD COLUMN IF NOT EXISTS framework_version TEXT;

ALTER TABLE cycle_registry
    ADD COLUMN IF NOT EXISTS framework_git_sha TEXT;
