PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS collections (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  parent_id TEXT,
  position INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (parent_id) REFERENCES collections(id) ON DELETE CASCADE,
  CHECK (parent_id IS NULL OR parent_id != id)
);

CREATE TABLE IF NOT EXISTS requests (
  id TEXT PRIMARY KEY,
  collection_id TEXT,
  name TEXT NOT NULL,
  method TEXT NOT NULL DEFAULT 'GET' CHECK (
    method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS')
  ),
  url TEXT NOT NULL DEFAULT '',
  params_json TEXT NOT NULL DEFAULT '[]',
  headers_json TEXT NOT NULL DEFAULT '[]',
  body_json TEXT NOT NULL DEFAULT '{"kind":"none","text":"","form":[]}',
  allowed_secret_ids_json TEXT NOT NULL DEFAULT '[]',
  timeout_ms INTEGER,
  follow_redirects INTEGER NOT NULL DEFAULT 1,
  position INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS environments (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS environment_variables (
  id TEXT PRIMARY KEY,
  environment_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1,
  UNIQUE (environment_id, key),
  FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS secret_metadata (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS request_history (
  id TEXT PRIMARY KEY,
  request_id TEXT,
  environment_id TEXT,
  request_snapshot_json TEXT NOT NULL,
  status INTEGER,
  latency_ms INTEGER,
  size_bytes INTEGER,
  response_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);

INSERT INTO settings (key, value)
VALUES ('active_environment_id', NULL)
ON CONFLICT(key) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_requests_collection_id
  ON requests(collection_id);

CREATE INDEX IF NOT EXISTS idx_environment_variables_environment_id
  ON environment_variables(environment_id);

CREATE INDEX IF NOT EXISTS idx_request_history_request_id
  ON request_history(request_id);

CREATE INDEX IF NOT EXISTS idx_collections_parent_id
  ON collections(parent_id);
