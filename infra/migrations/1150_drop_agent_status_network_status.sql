-- 1150_drop_agent_status_network_status.sql
-- #305 Part B (SIP-0089 consolidation, #231): agent_status.network_status is retired.
--
-- network_status was a heartbeat-derived reachability flag stored beside the canonical
-- health signal, agent_runtime_state.runtime_status — two sources for one fact. Part A
-- made runtime_status always-populated and removed every read of network_status; this
-- drops the column so it cannot be read back. The heartbeat-age verdict still drives the
-- lifecycle telemetry (UNKNOWN) and the offline mirror into agent_runtime_state; it is
-- computed, never stored. Idempotent.
ALTER TABLE agent_status DROP COLUMN IF EXISTS network_status;
