-- WarmBoot run-005 Database Schema
-- Agent activity log (for demo purposes)
CREATE TABLE IF NOT EXISTS agent_activity (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Demo user preferences (theme, etc.)
CREATE TABLE IF NOT EXISTS demo_preferences (
    id SERIAL PRIMARY KEY,
    preference_key VARCHAR(50) UNIQUE NOT NULL,
    preference_value VARCHAR(200),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert sample data
INSERT INTO agent_activity (agent_name, action, details) VALUES
('Max', 'Task Assignment', 'Sent database schema task to Neo'),
('Neo', 'Task Processing', 'Creating database schema for WarmBoot run-005')
ON CONFLICT DO NOTHING;

INSERT INTO demo_preferences (preference_key, preference_value) VALUES
('theme', 'light'),
('language', 'en'),
('notifications', 'enabled')
ON CONFLICT (preference_key) DO NOTHING;
