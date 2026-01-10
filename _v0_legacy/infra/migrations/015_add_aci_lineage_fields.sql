-- Migration: Add ACI Lineage Fields to agent_task_log table
-- ACI v0.8: Add required lineage fields as canonical columns (not metrics JSON)

-- Add ACI lineage and task fields to agent_task_log
ALTER TABLE agent_task_log
    ADD COLUMN IF NOT EXISTS project_id TEXT,
    ADD COLUMN IF NOT EXISTS pulse_id TEXT,
    ADD COLUMN IF NOT EXISTS correlation_id TEXT,
    ADD COLUMN IF NOT EXISTS causation_id TEXT,
    ADD COLUMN IF NOT EXISTS trace_id TEXT,
    ADD COLUMN IF NOT EXISTS span_id TEXT,
    ADD COLUMN IF NOT EXISTS task_type TEXT,
    ADD COLUMN IF NOT EXISTS inputs JSONB DEFAULT '{}'::jsonb;

-- Make required fields NOT NULL after populating existing rows
-- First, populate existing rows with generated placeholder values
UPDATE agent_task_log
SET
    project_id = COALESCE(
        (SELECT project_id FROM cycle WHERE cycle.cycle_id = agent_task_log.cycle_id),
        'project-placeholder'
    ),
    pulse_id = COALESCE(pulse_id, 'pulse-placeholder-' || task_id),
    correlation_id = COALESCE(correlation_id, 'corr-' || cycle_id),
    causation_id = COALESCE(causation_id, 'cause-root'),
    trace_id = COALESCE(trace_id, 'trace-placeholder-' || task_id),
    span_id = COALESCE(span_id, 'span-placeholder-' || task_id),
    task_type = COALESCE(task_type, COALESCE(task_name, 'unknown')),
    inputs = COALESCE(inputs, '{}'::jsonb)
WHERE project_id IS NULL
   OR pulse_id IS NULL
   OR correlation_id IS NULL
   OR causation_id IS NULL
   OR trace_id IS NULL
   OR span_id IS NULL
   OR task_type IS NULL
   OR inputs IS NULL;

-- Now make fields NOT NULL
ALTER TABLE agent_task_log
    ALTER COLUMN project_id SET NOT NULL,
    ALTER COLUMN pulse_id SET NOT NULL,
    ALTER COLUMN correlation_id SET NOT NULL,
    ALTER COLUMN causation_id SET NOT NULL,
    ALTER COLUMN trace_id SET NOT NULL,
    ALTER COLUMN span_id SET NOT NULL,
    ALTER COLUMN task_type SET NOT NULL,
    ALTER COLUMN inputs SET NOT NULL,
    ALTER COLUMN inputs SET DEFAULT '{}'::jsonb;

-- Create indexes for lineage fields
CREATE INDEX IF NOT EXISTS idx_agent_task_log_project_id ON agent_task_log(project_id);
CREATE INDEX IF NOT EXISTS idx_agent_task_log_pulse_id ON agent_task_log(pulse_id);
CREATE INDEX IF NOT EXISTS idx_agent_task_log_correlation_id ON agent_task_log(correlation_id);
CREATE INDEX IF NOT EXISTS idx_agent_task_log_causation_id ON agent_task_log(causation_id);
CREATE INDEX IF NOT EXISTS idx_agent_task_log_task_type ON agent_task_log(task_type);

-- Add foreign key constraint for project_id
ALTER TABLE agent_task_log
    ADD CONSTRAINT fk_agent_task_log_project_id
    FOREIGN KEY (project_id) REFERENCES projects(project_id);

