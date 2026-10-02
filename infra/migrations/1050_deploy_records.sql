-- 1050_deploy_records.sql
-- #1720 (#80's follow-on; the 1.9.0 plan §7a item 1): one row per deploy, holding exactly what it
-- put in service — each service's image ID and revision label, and the digest of each model the
-- squad profiles name. Written by the deploy step (rebuild_and_deploy.sh → the runtime image's
-- squadops.api.runtime.record_deploy), never by a request. Write-once: a deploy_id is never
-- rewritten. services and models are JSON lists; a NULL revision or digest means "not reported".
-- All DDL is idempotent.

CREATE TABLE IF NOT EXISTS deploy_records (
    deploy_id TEXT PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL,
    recorded_by TEXT NOT NULL,
    source_revision TEXT,
    services JSONB NOT NULL,
    models JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deploy_records_recorded_at ON deploy_records (recorded_at DESC);
