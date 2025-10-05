# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CS2 Market Watcher is a read-only monitoring service for Counter-Strike 2 Steam Community Market listings. The system fetches Steam listings, enriches them with float/sticker data via a local inspect service, evaluates profit rules, and sends Telegram alerts for profitable opportunities.

## Architecture

The project uses a multi-service architecture orchestrated via Docker Compose:

- **FastAPI Control API** (`src/api/main.py`): HTTP API and admin web panel for managing watchlist entries, worker control, and viewing inspect history
- **Worker** (`src/worker/main.py`): Async polling loop that fetches Steam listings, inspects items via CSFloat checker website, evaluates rules, and sends alerts
- **Postgres**: Stores watchlist entries, listing snapshots, alerts, and inspect history cache
- **Redis**: Rate limiting (token buckets) and worker state management

### Data Flow

1. Worker polls Postgres for active `Watchlist` entries
2. For each watch, fetches first page of Steam listings using Playwright-based headless browser (renders JavaScript-heavy Steam pages)
3. Parses rendered HTML with `selectolax` to extract price, listing key, and inspect URL
4. Checks `InspectHistory` table for cached inspect results by URL
5. If not cached, uses token bucket rate limiter (0.25 RPS) and navigates to https://csfloat.com/checker with Playwright
6. Fills inspect URL into input field, waits 5 seconds, scrapes float value and metadata from results
7. Evaluates parsed + inspected data against user-defined rules (float range, seed whitelist, sticker requirements, profit threshold)
8. Stores `ListingSnapshot` with parsed and inspected data
9. If profitable, creates `Alert` record and sends Telegram message
10. Sleeps with jitter before processing next watch

### Key Models (src/core/models.py)

- `Watchlist`: User-defined watch with `appid`, `market_hash_name`, `url`, `rules` (JSON field with float_min/max, seed_whitelist, sticker_any, target_resale_usd, min_profit_usd)
- `ListingSnapshot`: Captures a listing at a point in time with `listing_key`, `price_cents`, `parsed` (dict with listing_url, inspect_url), `inspected` (dict with float_value, paint_seed, stickers), `alerted` flag
- `InspectHistory`: Caches inspect results by `inspect_url` to avoid redundant inspect calls
- `Alert`: Audit trail of sent Telegram messages

### Rate Limiting (src/core/rate_limit.py)

Uses Redis-based token bucket with configurable RPS. Worker uses 0.25 RPS (1 request every 4 seconds) for inspect calls to CSFloat checker to avoid rate limiting.

### Profit Calculation (src/core/profit.py)

Compares listing price against expected resale price after Steam fees (15% combined rate + minimum 1 cent fee). Only alerts if `(target_resale * (1 - fee_rate)) - fee_min - listing_price >= min_profit`.

## Common Commands

### Build and Run Services

```bash
docker compose up --build
```

Starts all services (postgres, redis, inspect, api, worker). API available at http://localhost:8000, inspect service at http://localhost:5000.

### Database Setup

Apply migrations:

```bash
psql $DATABASE_URL -f migrations/001_init.sql
```

### Local Development

Create virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running Tests

Run all tests:

```bash
pytest
```

Run specific test file:

```bash
pytest tests/unit/test_parsing.py
```

Run with verbose output:

```bash
pytest -v
```

Run integration tests (requires services):

```bash
pytest tests/integration/
```

### Admin Panel

Access web UI for managing watches:

```bash
open http://localhost:8000/admin/watches
```

### Worker Control

Worker can be paused/resumed via admin panel or by setting Redis key `worker:enabled` to "0" (pause) or "1" (resume).

## Steam Listing Parsing

The worker uses Playwright headless browser to render JavaScript-heavy Steam market pages before parsing. This is critical because Steam loads listing data dynamically.

**Parsing logic** (`src/core/parsing.py`):
- Extracts price from `span.market_listing_price_with_fee`
- Finds listing key from `id` attribute or `data-paintindex`
- Searches for inspect URL by looking for anchors with "inspect in game" text and `steam://` protocol
- Returns `ParsedListing` dataclass with listing_key, price_cents, inspect_url, listing_url

**HTML dumping**: Worker saves rendered HTML snapshots to `STEAM_HTML_DUMP_DIR` (default: `./html-dumps`) for debugging. Each fetch creates a timestamped file like `730-AK-47_Redline_Field-Tested-1759380510.html`.

## Inspect Integration

The worker uses Playwright to automate the public CSFloat checker website (https://csfloat.com/checker) for retrieving float values and item metadata.

**How it works** (`src/integrations/inspect.py`):
1. Opens headless Chromium browser
2. Navigates to https://csfloat.com/checker
3. Waits 5 seconds for page to load
4. Fills inspect URL into input field (id="mat-input-0")
5. Waits 5 seconds for results to auto-load
6. Scrapes float value from div with class="mat-mdc-tooltip-trigger wear"
7. Attempts to extract additional data: paint_seed, paint_index, wear_name, stickers

**Rate limiting**: Fixed at 0.25 RPS (one request every 4 seconds) in worker to respect CSFloat's service.

**Retry logic**: 3 attempts with exponential backoff (2s, 4s delays) on Playwright errors or timeouts.

**Return format**: `InspectResult` dataclass with `float_value`, `paint_seed`, `paint_index`, `stickers` array, `wear_name`.

## Environment Variables

Key settings (see `.env.example`):

- `DATABASE_URL`: Postgres connection string
- `REDIS_URL`: Redis connection string
- `FLOAT_API_TIMEOUT`: Playwright timeout for inspect operations (default: 30s)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`: Telegram notification settings
- `POLL_INTERVAL_S`: Worker cycle sleep duration (default: 10)
- `COMBINED_FEE_RATE`: Steam marketplace fee rate (default: 0.15)
- `STEAM_HTML_DUMP_DIR`: Path to save rendered HTML snapshots (default: ./html-dumps)
- `ADMIN_DEFAULT_MIN_PROFIT_USD`: Default min profit when creating watches via admin panel (default: 0.0)

## Testing Strategy

**Unit tests** (`tests/unit/`): Test parsing, profit calculations, rate limiting in isolation.

**Integration tests** (`tests/integration/`): Test API endpoints and inspect client against real services (requires Docker Compose).

**Test fixtures** (`tests/conftest.py`): Provides `default_env` fixture that sets required env vars and clears settings cache.

## Important Constraints

- **Read-only**: System never places orders or buys items
- **Rate limiting**: Token bucket prevents overwhelming Steam and CSFloat (0.25 RPS for inspect calls)
- **Deduplication**: Listings are tracked by `(watchlist_id, listing_key, price_cents)` to avoid re-inspecting same item
- **Inspect caching**: `InspectHistory` table caches results by `inspect_url` indefinitely to minimize CSFloat requests
- **Playwright requirement**: Playwright browser must be installed in Docker image (see Dockerfile install steps)
- **CSFloat dependency**: System relies on public CSFloat checker website; changes to their UI may break inspection

## Common Gotchas

1. **Playwright browser dependencies**: The Dockerfile installs Chromium and its runtime dependencies. If running locally, ensure `playwright install chromium` has been run.

2. **Lazy loading in worker**: Worker captures primitives (`watch.id`, `watch.market_hash_name`, etc.) before async operations to avoid SQLAlchemy `MissingGreenlet` errors.

3. **Worker pause logic**: Worker checks `worker:enabled` Redis key at multiple points (start of cycle, before processing each watch, after cycle) to enable graceful shutdown without losing work.

4. **HTML dump directory**: Worker creates directory if it doesn't exist. In Docker, `./html-dumps` is mounted as volume so dumps persist on host.

5. **Settings cache**: `get_settings()` is cached with `@lru_cache`. Tests must call `get_settings.cache_clear()` to reset state.

6. **Inspect URL extraction**: Parsing looks for "inspect in game" text in anchor elements with `steam://` protocol. If Steam changes page structure, parsing may fail silently (logs warning with anchor samples).

7. **CSFloat website scraping**: InspectClient relies on specific CSS selectors (#mat-input-0 for input, .mat-mdc-tooltip-trigger.wear for float value). If CSFloat updates their UI, inspection will fail. Monitor logs for "inspect attempt failed" errors.

8. **Conservative rate limiting**: The 0.25 RPS rate limit for CSFloat is hardcoded in worker/main.py:129. This is intentionally conservative to avoid rate limiting on their public service.
