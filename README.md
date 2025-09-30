# CS2 Read-only Market Watcher

This project provides a read-only monitoring service for Counter-Strike 2 Steam Community Market listings. It polls the first page of each watched item, enriches listings with float data from a self-hosted CSFloat Inspect deployment, evaluates user-defined profit rules, and sends Telegram alerts for profitable opportunities.

## Features

- FastAPI control API for managing watchlist entries and health checks.
- Async worker that fetches Steam listing page 1, parses listings, inspects skins, and applies rule filters.
- Postgres persistence for watchlist entries, listing snapshots, and alert audit trail.
- Redis-backed rate limits and deduplication to respect Steam and Inspect service constraints.
- Telegram notifications with Markdown-formatted summaries.

## Architecture Overview

```
+-------------+        +-----------+        +-----------+
|  FastAPI    |  -->   | Postgres  |  -->   | Telegram  |
|  Control    |        | & Redis   |        | Alerts    |
+-------------+        +-----------+        +-----------+
        ^                     ^                    ^
        |                     |                    |
        |               +-----------+        +-----------+
        +---------------|  Worker   |------->| Inspect   |
                        +-----------+        +-----------+
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
INSPECT_BASE_URL=http://inspect:5000
TELEGRAM_BOT_TOKEN=replace-me
TELEGRAM_CHAT_ID=replace-me
POLL_INTERVAL_S=10
INSPECT_RPS_PER_ACCOUNT=0.8
INSPECT_ACCOUNTS=5
COMBINED_FEE_RATE=0.15
COMBINED_FEE_MIN_CENTS=1
```

### Docker Compose

```
docker compose up --build
```

This command starts Postgres, Redis, the CSFloat Inspect container, the FastAPI control API, and the worker process. The API is exposed on port 8000.

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

## Development

Install dependencies and run tests locally:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## References

- CSFloat Inspect deployment guidance (Node.js requirements, Postgres caching, multi-account support). [GitHub](https://github.com/CSSFloat/Inspect)
- CSFloat API response fields. [CSFloat Docs](https://docs.csfloat.com/)
- Steam Community Market priceoverview usage. [Stack Overflow](https://stackoverflow.com/questions/18921471/steam-market-price-history-json)
- Steam Community Market render endpoint details. [Steam Community](https://steamcommunity.com/)
- Steam Community Market fees (5% Steam + game-specific fee). [Steam Support](https://support.steampowered.com/kb_article.php?ref=6088-UDXM-7214)

## Safety Notes

- The service is read-only: it never attempts to place orders or buy items.
- Rate limits and exponential backoff guard against throttling.
- Secrets (Steam accounts for Inspect, Telegram token) must be provided via environment variables or external secret stores.
- Do not commit Steam credentials or Telegram tokens to source control.

