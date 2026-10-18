CREATE TABLE IF NOT EXISTS workflow_runs (
 workflow_id text PRIMARY KEY, definition jsonb NOT NULL, definition_version integer NOT NULL,
 definition_digest text NOT NULL, payload jsonb NOT NULL, terminal_status text NOT NULL DEFAULT 'running',
 event_seq integer NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS history_events (
 workflow_id text REFERENCES workflow_runs, event_seq integer, kind text NOT NULL, step text NOT NULL,
 data jsonb NOT NULL, command_ids jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(workflow_id,event_seq)
);
CREATE TABLE IF NOT EXISTS ingress_requests (
 kind text, idempotency_key text, canonical_request_hash text NOT NULL, workflow_id text NOT NULL,
 PRIMARY KEY(kind,idempotency_key)
);
CREATE TABLE IF NOT EXISTS activity_tasks (
 workflow_id text REFERENCES workflow_runs, command_id text, step text NOT NULL, activity text NOT NULL,
 compensation boolean NOT NULL DEFAULT false, status text NOT NULL DEFAULT 'pending',
 attempt_number integer NOT NULL DEFAULT 0, lease_epoch integer NOT NULL DEFAULT 0,
 lease_expiry timestamptz, available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 max_attempts integer NOT NULL, retry_delay double precision NOT NULL,
 PRIMARY KEY(workflow_id,command_id)
);
CREATE INDEX IF NOT EXISTS ready_tasks ON activity_tasks(status,available_at,lease_expiry);
CREATE TABLE IF NOT EXISTS activity_attempts (
 workflow_id text, command_id text, attempt_number integer, lease_epoch integer NOT NULL,
 status text NOT NULL, started_at timestamptz NOT NULL DEFAULT clock_timestamp(), finished_at timestamptz,
 PRIMARY KEY(workflow_id,command_id,attempt_number)
);
CREATE TABLE IF NOT EXISTS timers (
 workflow_id text REFERENCES workflow_runs, command_id text, step text NOT NULL,
 due_at timestamptz NOT NULL, fired boolean NOT NULL DEFAULT false, PRIMARY KEY(workflow_id,command_id)
);
CREATE INDEX IF NOT EXISTS due_timers ON timers(due_at) WHERE NOT fired;
CREATE TABLE IF NOT EXISTS signals (
 workflow_id text REFERENCES workflow_runs, name text, payload jsonb NOT NULL, PRIMARY KEY(workflow_id,name)
);
CREATE TABLE IF NOT EXISTS provider_effects (
 business_key text PRIMARY KEY, payload jsonb NOT NULL, fenced boolean NOT NULL DEFAULT false,
 publications integer NOT NULL DEFAULT 0, cleanup_attempts integer NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS schema_migrations (
 version integer PRIMARY KEY, installed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO schema_migrations(version) VALUES(1) ON CONFLICT DO NOTHING;
ALTER TABLE history_events ADD COLUMN IF NOT EXISTS schema_version integer NOT NULL DEFAULT 1;
ALTER TABLE activity_attempts ADD COLUMN IF NOT EXISTS ready_delay double precision NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS active_runs ON workflow_runs(created_at) WHERE terminal_status IN ('running','compensating');
CREATE INDEX IF NOT EXISTS run_ready_tasks ON activity_tasks(workflow_id,status,available_at,lease_expiry);
