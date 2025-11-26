from __future__ import annotations

import asyncio
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable, Iterable, Optional
from urllib.parse import quote

import httpx
import structlog

from ..core.config import get_settings
from ..core.parsing import ParsedListing, parse_results_html


@dataclass
class PriceOverview:
    lowest_price: str | None
    median_price: str | None
    volume: str | None


PageFetcher = Callable[[str], Awaitable[str]]


class SteamAPIError(RuntimeError):
    """Raised when Steam API request fails."""


class SteamRateLimitError(SteamAPIError):
    """Raised when Steam returns 429 Too Many Requests."""


class SteamClient:
    # Circuit breaker settings
    CIRCUIT_BREAKER_THRESHOLD = 3  # consecutive 429s before entering cooldown
    CIRCUIT_BREAKER_MAX_COOLDOWN_MINUTES = 30

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        page_fetcher: Optional[PageFetcher] = None,
    ) -> None:
        self.settings = get_settings()
        self.logger = structlog.get_logger(__name__)
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/javascript, text/html, application/xml, text/xml, */*",
                "X-Requested-With": "XMLHttpRequest",
                "X-Prototype-Version": "1.7",
            }
        )
        self._timeout = timeout
        self._page_fetcher = page_fetcher

        # Circuit breaker state
        self._consecutive_429s = 0
        self._cooldown_until: datetime | None = None

    async def close(self) -> None:
        await self.client.aclose()

    async def _check_circuit_breaker(self) -> None:
        """Check if circuit breaker is active and wait if needed."""
        if self._cooldown_until is not None:
            now = datetime.utcnow()
            if now < self._cooldown_until:
                wait_seconds = (self._cooldown_until - now).total_seconds()
                self.logger.info(
                    "steam.circuit_breaker_active",
                    wait_seconds=round(wait_seconds, 1),
                    cooldown_until=self._cooldown_until.isoformat(),
                )
                await asyncio.sleep(wait_seconds)
            # Reset cooldown after waiting
            self._cooldown_until = None

    def _on_success(self) -> None:
        """Reset circuit breaker state on successful request."""
        if self._consecutive_429s > 0:
            self.logger.info(
                "steam.circuit_breaker_reset",
                previous_consecutive_429s=self._consecutive_429s,
            )
        self._consecutive_429s = 0

    def _on_rate_limit(self) -> None:
        """Update circuit breaker state on 429 response."""
        self._consecutive_429s += 1
        if self._consecutive_429s >= self.CIRCUIT_BREAKER_THRESHOLD:
            # Enter cooldown: 5 minutes * consecutive_429s, capped at max
            cooldown_minutes = min(
                5 * self._consecutive_429s,
                self.CIRCUIT_BREAKER_MAX_COOLDOWN_MINUTES,
            )
            self._cooldown_until = datetime.utcnow() + timedelta(minutes=cooldown_minutes)
            self.logger.warning(
                "steam.circuit_breaker_triggered",
                consecutive_429s=self._consecutive_429s,
                cooldown_minutes=cooldown_minutes,
                cooldown_until=self._cooldown_until.isoformat(),
            )

    async def _fetch_page_content(self, url: str) -> str:
        """Fetch page content using Steam's /render/ API endpoint or custom page_fetcher.

        Args:
            url: The Steam market listing URL (e.g., https://steamcommunity.com/market/listings/730/AK-47...)

        Returns:
            HTML content string

        Raises:
            SteamRateLimitError: If Steam returns 429 after all retries
            SteamAPIError: For other Steam API errors
        """
        if self._page_fetcher is not None:
            html = await self._page_fetcher(url)
            return html

        # Check circuit breaker before making request
        await self._check_circuit_breaker()

        # Convert regular URL to /render/ endpoint
        # Example: https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline%20%28Field-Tested%29
        # becomes: https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline%20%28Field-Tested%29/render/
        if "/render/" not in url:
            # Extract the base URL and query parameters
            if "?" in url:
                base_url, query_params = url.rsplit("?", 1)
                render_url = f"{base_url}/render/?{query_params}"
            else:
                render_url = f"{url}/render/"
        else:
            render_url = url

        # Set Referer header (base URL without /render/)
        referer_url = render_url.replace("/render/", "").split("?")[0]
        headers = {"Referer": referer_url}

        self.logger.debug("steam.fetch", url=render_url, referer=referer_url)

        # Retry logic with exponential backoff for 429 errors
        max_retries = 3
        base_delay = 30  # Steam 429s need longer cooldown

        for attempt in range(max_retries):
            try:
                response = await self.client.get(render_url, headers=headers)
                response.raise_for_status()
                data = response.json()

                # Extract results_html from JSON response
                if "results_html" not in data:
                    self.logger.error("steam.missing_results_html", data_keys=list(data.keys()))
                    raise SteamAPIError("Steam API response missing 'results_html' field")

                # Success - reset circuit breaker
                self._on_success()
                return data["results_html"]

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    self._on_rate_limit()
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                    self.logger.warning(
                        "steam.rate_limited",
                        status=429,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay_seconds=round(delay, 1),
                        url=render_url,
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)
                        continue
                    # Final attempt failed
                    raise SteamRateLimitError(
                        f"Steam API returned 429 after {max_retries} retries"
                    ) from exc
                else:
                    self.logger.error(
                        "steam.http_error",
                        status=exc.response.status_code,
                        url=render_url,
                    )
                    raise SteamAPIError(
                        f"Steam API returned status {exc.response.status_code}"
                    ) from exc

            except httpx.RequestError as exc:
                self.logger.error("steam.request_error", error=str(exc), url=render_url)
                raise SteamAPIError(f"Failed to connect to Steam API: {exc}") from exc

            except ValueError as exc:
                # JSON decode error
                self.logger.error("steam.json_error", error=str(exc), url=render_url)
                raise SteamAPIError("Failed to parse Steam API JSON response") from exc

        # Should not reach here, but just in case
        raise SteamAPIError("Unexpected error in fetch loop")

    async def price_overview(self, appid: int, market_hash_name: str) -> PriceOverview:
        params = {
            "appid": appid,
            "market_hash_name": market_hash_name,
            "currency": self.settings.steam_currency_id,
        }
        resp = await self.client.get("https://steamcommunity.com/market/priceoverview/", params=params)
        resp.raise_for_status()
        data = resp.json()
        return PriceOverview(
            lowest_price=data.get("lowest_price"),
            median_price=data.get("median_price"),
            volume=data.get("volume"),
        )

    async def fetch_listings(
        self, appid: int, market_hash_name: str, count: int = 10
    ) -> Iterable[ParsedListing]:
        encoded_name = quote(market_hash_name, safe="")
        url = (
            f"https://steamcommunity.com/market/listings/{appid}/{encoded_name}?start=0&count={count}"
            f"&currency={self.settings.steam_currency_id}"
        )
        page_html = await self._fetch_page_content(url)
        return list(parse_results_html(page_html))


async def main() -> None:
    client = SteamClient()
    try:
        listings = await client.fetch_listings(730, "AK-47 | Redline (Field-Tested)")
        for listing in listings:
            print(listing)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
