"""
Forex exchange rate utilities with optional Redis caching.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from forex_python.converter import CurrencyRates

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = structlog.get_logger(__name__)

FOREX_CACHE_KEY = "forex:usd_to_kzt"
FOREX_CACHE_TTL = 3600  # Cache for 1 hour
FALLBACK_RATE = 470.0  # Fallback rate if API fails


async def get_usd_to_kzt_rate(redis: "Redis | None" = None) -> float:
    """
    Get USD to KZT exchange rate with optional Redis caching.

    Args:
        redis: Optional Redis client for caching. If None, caching is skipped.

    Returns:
        Exchange rate (how many KZT for 1 USD)
    """
    # Try to get from cache if Redis is available
    if redis is not None:
        try:
            cached_rate = await redis.get(FOREX_CACHE_KEY)
            if cached_rate:
                rate = float(cached_rate)
                logger.info("Using cached forex rate", rate=rate)
                return rate
        except Exception as exc:
            logger.warning("Failed to read forex rate from cache", error=str(exc))

    # Fetch fresh rate from forex API
    try:
        logger.info("Fetching fresh forex rate from API")
        c = CurrencyRates()
        rate = c.get_rate("USD", "KZT")
        logger.info("Fetched forex rate successfully", rate=rate)

        # Cache the rate if Redis is available
        if redis is not None:
            try:
                await redis.set(FOREX_CACHE_KEY, str(rate), ex=FOREX_CACHE_TTL)
                logger.info("Cached forex rate", ttl=FOREX_CACHE_TTL)
            except Exception as exc:
                logger.warning("Failed to cache forex rate", error=str(exc))

        return rate

    except Exception as exc:
        logger.error(
            "Failed to fetch forex rate, using fallback",
            error=str(exc),
            fallback_rate=FALLBACK_RATE,
        )
        return FALLBACK_RATE
