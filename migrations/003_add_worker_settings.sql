-- Migration: Add worker settings table
-- Replaces Redis-based worker state management with Postgres

CREATE TABLE IF NOT EXISTS worker_settings (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1), -- Ensure only one row
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Insert default row
INSERT INTO worker_settings (id, enabled) VALUES (1, TRUE)
ON CONFLICT (id) DO NOTHING;

-- Add index on updated_at for potential auditing queries
CREATE INDEX IF NOT EXISTS idx_worker_settings_updated_at ON worker_settings(updated_at);
