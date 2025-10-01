# CS2 Read-only Market Watcher

This project provides a read-only monitoring service for Counter-Strike 2 Steam Community Market listings. It polls the first page of each watched item, enriches listings with float data from the public CSFloat API, evaluates user-defined profit rules, and sends Telegram alerts for profitable opportunities.

## Features

- FastAPI control API for managing watchlist entries and health checks.
- Async worker that fetches Steam listing page 1, parses listings, inspects skins, and applies rule filters.
- Postgres persistence for watchlist entries, listing snapshots, and alert audit trail.
- Redis-backed rate limits and deduplication to respect Steam and CSFloat API constraints.
- Telegram notifications with Markdown-formatted summaries.

## Architecture Overview

```
+-------------+        +-----------+        +-----------+
|  FastAPI    |  -->   | Postgres  |  -->   | Telegram  |
|  Control    |        | & Redis   |        | Alerts    |
+-------------+        +-----------+        +-----------+
        ^                     ^                    ^
        |                     |                    |
        |               +-----------+        +-------------+
        +---------------|  Worker   |------->| CSFloat API |
                        +-----------+        +-------------+
                                 \
                                  \-> Steam Community Market
```

The worker uses configurable jitter and Redis token buckets to avoid overloading external services. Listing parsing is performed with `selectolax`. The inspect stage retrieves float, seed, and sticker metadata before evaluating user rules.

## Quick Start

### Requirements

- Docker and Docker Compose v2
- Optional: Python 3.11 for local development (see `requirements.txt`)

### Environment Variables

Copy `.env.example` to `.env` and fill in required secrets.

```
DATABASE_URL=postgresql+psycopg://steam:steam@postgres/steam
REDIS_URL=redis://redis:6379/0
STEAM_CURRENCY_ID=1
CSFLOAT_API_BASE_URL=https://api.csgofloat.com
FLOAT_API_TIMEOUT=10
FLOAT_API_REQUEST_DELAY=2
STEAM_HTML_DUMP_DIR=./html-dumps
TELEGRAM_BOT_TOKEN=replace-me
TELEGRAM_CHAT_ID=replace-me
POLL_INTERVAL_S=10
INSPECT_RPS_PER_ACCOUNT=0.8
INSPECT_ACCOUNTS=5
COMBINED_FEE_RATE=0.15
COMBINED_FEE_MIN_CENTS=1
ADMIN_DEFAULT_MIN_PROFIT_USD=0.0
```

`ADMIN_DEFAULT_MIN_PROFIT_USD` controls the minimum profit automatically applied when you create watches through the web admin.

Set `STEAM_HTML_DUMP_DIR` to a writable path if you want the worker to persist the fully rendered Steam listing HTML for debugging. Each fetch writes a timestamped snapshot in that directory.
The default Docker Compose setup mounts `./html-dumps` into the worker container and wires the environment variable so you can inspect saved pages on the host while tailing `docker compose logs`.

### Docker Compose

```
docker compose up --build
```

This command starts Postgres, Redis, the FastAPI control API, and the worker process. The API is exposed on port 8000.

### Database Migrations

```
psql $DATABASE_URL -f migrations/001_init.sql
```

### API Usage

- `POST /watch` – create a new watchlist entry.
- `GET /watch` – list watchlist entries.
- `DELETE /watch/{id}` – remove a watchlist entry.
- `GET /health` – readiness probe.

See `src/api/main.py` for request/response schemas.

### Admin Panel

Visit `http://localhost:8000/admin/watches` for a lightweight HTML dashboard backed by the same FastAPI service. The page lists
all watchlist entries, provides an inline form for creating new entries, and offers update/delete controls for existing watches
without needing to craft raw JSON requests.

## Development

Install dependencies and run tests locally:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## References

- CSFloat API response fields. [CSFloat Docs](https://docs.csfloat.com/)
- Steam Community Market priceoverview usage. [Stack Overflow](https://stackoverflow.com/questions/18921471/steam-market-price-history-json)
- Steam Community Market render endpoint details. [Steam Community](https://steamcommunity.com/)
- Steam Community Market fees (5% Steam + game-specific fee). [Steam Support](https://support.steampowered.com/kb_article.php?ref=6088-UDXM-7214)

## Safety Notes

- The service is read-only: it never attempts to place orders or buy items.
- Rate limits and exponential backoff guard against throttling.
- Secrets (Telegram token and any optional overrides) must be provided via environment variables or external secret stores.
- Do not commit Steam credentials or Telegram tokens to source control.
