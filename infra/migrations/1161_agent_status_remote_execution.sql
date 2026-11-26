-- 1161_agent_status_remote_execution.sql
-- #3235: an agent says, in its heartbeat, which remote-execution provider its own port binds.
--
-- The agent binds that port itself when its process starts, from its own configuration. On
-- 2026-11-19 the runtime was switched to runtime_api and rebuilt while the QA agent still bound
-- none, and a cycle was created whose in-run evaluation could ask no worker. A cycle's creation
-- now reads this column for the agent that runs a worker's tool.
--
-- NULL is an agent that has not said: one built before agents reported it. It is refused by
-- name, never read as "bound".

ALTER TABLE IF EXISTS agent_status ADD COLUMN IF NOT EXISTS remote_execution TEXT;
