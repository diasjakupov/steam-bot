# CS2 Read-only Market Watcher

This project provides a read-only monitoring service for Counter-Strike 2 Steam Community Market listings. It polls the first page of each watched item, enriches listings with float data using a local inspect service powered by the csfloat/inspect project, evaluates user-defined profit rules, and sends Telegram alerts for profitable opportunities.

## Features

- FastAPI control API for managing watchlist entries and health checks.
- Async worker that fetches Steam listing page 1, parses listings, inspects skins, and applies rule filters.
- SQLite database for watchlist entries, listing snapshots, alert audit trail, and worker state.
- In-memory rate limiting to respect Steam and inspect service constraints.
- Telegram notifications with Markdown-formatted summaries.

## Architecture Overview

```
+-------------+        +-----------+        +-----------+
|  FastAPI    |  -->   |  SQLite   |  -->   | Telegram  |
|  Control    |        |  Database |        | Alerts    |
+-------------+        +-----------+        +-----------+
        ^                     ^                    ^
        |                     |                    |
        |               +-----------+              |
        +---------------|  Worker   |--------------+
                        +-----------+
                                 |
                                 v
                     Steam Community Market
                        CSFloat Checker
```

The worker uses configurable jitter and in-memory token bucket rate limiting to avoid overloading external services. All data is stored in a single SQLite file, making deployment simple and portable. Listing parsing is performed with `selectolax`. The inspect stage uses Playwright to automate the CSFloat checker website (https://csfloat.com/checker) to retrieve float, seed, and sticker metadata before evaluating user rules.

## Quick Start

### Requirements

- Docker and Docker Compose v2
- Optional: Python 3.11 for local development (see `requirements.txt`)

### Environment Variables

Copy `.env.example` to `.env` and fill in required secrets.

```
DATABASE_URL=sqlite+aiosqlite:////data/cs2bot.db
STEAM_CURRENCY_ID=1
FLOAT_API_TIMEOUT=30
TELEGRAM_BOT_TOKEN=replace-me
TELEGRAM_CHAT_ID=replace-me
POLL_INTERVAL_S=10
COMBINED_FEE_RATE=0.15
COMBINED_FEE_MIN_CENTS=1
ADMIN_DEFAULT_MIN_PROFIT_USD=0.0
```

`ADMIN_DEFAULT_MIN_PROFIT_USD` controls the minimum profit automatically applied when you create watches through the web admin.

The worker uses Playwright to automate the public CSFloat checker website (https://csfloat.com/checker) for retrieving item float values and metadata. Inspect requests are rate-limited to 0.25 RPS (one request every 4 seconds) to respect CSFloat's service.

### Docker Compose

```
docker compose up --build
```

This command starts the FastAPI control API and the worker process. The API is exposed on port 8000. The SQLite database is automatically initialized on first run.

### Database Initialization

The database is automatically created when services start. To manually initialize:

```bash
docker compose exec api python -c "
import asyncio
from src.core.db import init_models
asyncio.run(init_models())
"
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
