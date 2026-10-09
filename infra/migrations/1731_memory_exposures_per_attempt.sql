-- 1731_memory_exposures_per_attempt.sql
-- SIP-0110 §0.2 (#2165): an exposure is one authoring invocation's, not one task's. 1730 made
-- (run_id, task_id) unique, so when a task was dispatched again (a re-take, an emission retry) its
-- own exposure was refused and the task ran with none. Found by the rebuild 7 regression pair:
-- run_44efb1828856's qa.test was authored three times and two of its exposures were refused. The
-- primary key, exposure_id, hashes the run, the task and the attempt, so it is one row per
-- invocation already.

ALTER TABLE memory_exposures DROP CONSTRAINT IF EXISTS memory_exposures_run_id_task_id_key;
