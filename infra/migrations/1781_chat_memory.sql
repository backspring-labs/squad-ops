-- SIP-0110 Appendix A §3.5–§3.6 and §A.8 Q29 (#2180 stage A): chat on the memory substrate.

-- Q29: a person deletes their own sessions. The session's row stays, marked, so a record confirmed
-- from one can say it came from a deleted session; its messages are removed.
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- §3.6 Disclosure: one exposure per chat turn, keyed by session and message, with no cycle, run or
-- task: what each section of the turn's context supplied, omitted (and by which limit) or failed.
CREATE TABLE IF NOT EXISTS chat_exposures (
    session_id   TEXT NOT NULL,
    message_id   TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    agent_id     TEXT NOT NULL,
    project_id   TEXT,
    assembled_at TIMESTAMPTZ NOT NULL,
    sections     JSONB NOT NULL,
    PRIMARY KEY (session_id, message_id)
);
CREATE INDEX IF NOT EXISTS idx_chat_exposures_user ON chat_exposures(user_id, assembled_at);
