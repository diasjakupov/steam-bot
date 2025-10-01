CREATE TABLE IF NOT EXISTS watchlist (
  id BIGSERIAL PRIMARY KEY,
  appid INT NOT NULL,
  market_hash_name TEXT NOT NULL,
  url TEXT NOT NULL,
  currency_id INT DEFAULT 1,
  rules JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS listing_snapshot (
  id BIGSERIAL PRIMARY KEY,
  watchlist_id BIGINT REFERENCES watchlist(id) ON DELETE CASCADE,
  listing_key TEXT,
  price_cents INT NOT NULL,
  scraped_at TIMESTAMPTZ DEFAULT now(),
  parsed JSONB,
  inspected JSONB,
  alerted BOOLEAN DEFAULT FALSE
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_listing_snap_dedupe
  ON listing_snapshot(watchlist_id, listing_key, price_cents);

CREATE TABLE IF NOT EXISTS alerts (
  id BIGSERIAL PRIMARY KEY,
  snapshot_id BIGINT REFERENCES listing_snapshot(id) ON DELETE CASCADE,
  payload JSONB NOT NULL,
  sent_at TIMESTAMPTZ DEFAULT now()
);
