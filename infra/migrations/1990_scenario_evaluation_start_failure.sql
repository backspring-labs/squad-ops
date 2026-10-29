-- 1990_scenario_evaluation_start_failure.sql
-- SIP-0113 §10ae (#2793): why an evaluation's start failed, kept on its record: the runner's detail
-- and the app's last lines, scrubbed of the evaluation's secrets and bounded. NULL on a start that
-- succeeded, one never attempted, and a record written before it.

ALTER TABLE scenario_evaluations ADD COLUMN IF NOT EXISTS start_failure JSONB;
