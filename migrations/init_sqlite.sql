-- SQLite Schema for CS2 Market Watcher
-- Enable foreign key support (required for ON DELETE CASCADE)
PRAGMA foreign_keys = ON;

-- Watchlist table
CREATE TABLE IF NOT EXISTS watchlist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  appid INTEGER NOT NULL,
  market_hash_name TEXT NOT NULL,
  url TEXT NOT NULL,
  currency_id INTEGER DEFAULT 1,
  rules TEXT NOT NULL,  -- JSON stored as TEXT in SQLite
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Listing snapshots
CREATE TABLE IF NOT EXISTS listing_snapshot (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  watchlist_id INTEGER NOT NULL,
  listing_key TEXT,
  price_cents INTEGER NOT NULL,
  scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  parsed TEXT,  -- JSON stored as TEXT
  inspected TEXT,  -- JSON stored as TEXT
  alerted INTEGER DEFAULT 0,  -- BOOLEAN as INTEGER (0=false, 1=true)
  FOREIGN KEY (watchlist_id) REFERENCES watchlist(id) ON DELETE CASCADE
);

-- Dedupe index for listings
CREATE UNIQUE INDEX IF NOT EXISTS ux_listing_snap_dedupe
  ON listing_snapshot(watchlist_id, listing_key, price_cents);

-- Alerts
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id INTEGER NOT NULL,
  payload TEXT NOT NULL,  -- JSON stored as TEXT
  sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (snapshot_id) REFERENCES listing_snapshot(id) ON DELETE CASCADE
);

-- Inspect history cache
CREATE TABLE IF NOT EXISTS inspect_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  inspect_url TEXT NOT NULL UNIQUE,
  result TEXT NOT NULL,  -- JSON stored as TEXT
  last_inspected TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  watchlist_id INTEGER,
  FOREIGN KEY (watchlist_id) REFERENCES watchlist(id) ON DELETE CASCADE
);

-- Worker settings
CREATE TABLE IF NOT EXISTS worker_settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),  -- Ensure only one row
  enabled INTEGER DEFAULT 1,  -- BOOLEAN as INTEGER (0=false, 1=true)
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index on updated_at for potential auditing queries
CREATE INDEX IF NOT EXISTS idx_worker_settings_updated_at ON worker_settings(updated_at);

-- Insert default worker settings
INSERT OR IGNORE INTO worker_settings (id, enabled) VALUES (1, 1);
