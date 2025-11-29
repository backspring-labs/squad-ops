-- Migration: Register initial projects (SIP-0047)
-- Date: 2025-01-29
-- Purpose: Register warmboot_selftest project

INSERT INTO projects (project_id, name, description) VALUES
('warmboot_selftest', 'WarmBoot Self-Test', 'Framework self-test execution cycles')
ON CONFLICT (project_id) DO NOTHING;

