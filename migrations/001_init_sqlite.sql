-- Enable foreign key support (required for ON DELETE CASCADE)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS watchlist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  appid INTEGER NOT NULL,
  market_hash_name TEXT NOT NULL,
  url TEXT NOT NULL,
  currency_id INTEGER DEFAULT 1,
  rules TEXT NOT NULL,  -- JSON stored as TEXT in SQLite
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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

CREATE UNIQUE INDEX IF NOT EXISTS ux_listing_snap_dedupe
  ON listing_snapshot(watchlist_id, listing_key, price_cents);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id INTEGER NOT NULL,
  payload TEXT NOT NULL,  -- JSON stored as TEXT
  sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (snapshot_id) REFERENCES listing_snapshot(id) ON DELETE CASCADE
);
