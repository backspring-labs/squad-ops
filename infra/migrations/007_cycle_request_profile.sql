-- 007_cycle_request_profile.sql
-- SIP-0096 run-config provenance: capture the cycle-request-profile name a cycle was
-- created from. This is a cycle-level config attribute (all runs of a cycle share it),
-- recorded so the 1.8 cycle-evaluation scorecard can attribute outcomes to config.
-- All DDL is idempotent.

ALTER TABLE cycle_registry
    ADD COLUMN IF NOT EXISTS request_profile TEXT;
