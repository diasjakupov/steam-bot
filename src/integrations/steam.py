from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Iterable, Optional
from urllib.parse import quote

import httpx
import structlog
from playwright.async_api import (
    Browser,
    Error as PlaywrightError,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from ..core.config import get_settings
from ..core.parsing import ParsedListing, parse_results_html


@dataclass
class PriceOverview:
    lowest_price: str | None
    median_price: str | None
    volume: str | None


PageFetcher = Callable[[str], Awaitable[str]]


class BrowserLaunchError(RuntimeError):
    """Raised when Playwright fails to launch a browser instance."""


class SteamClient:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        browser: str = "chromium",
        page_fetcher: Optional[PageFetcher] = None,
    ) -> None:
        self.settings = get_settings()
        self.logger = structlog.get_logger(__name__)
        self.client = httpx.AsyncClient(
            timeout=timeout, headers={"User-Agent": "cs2-market-watcher/1.0"}
        )
        self._timeout = timeout
        self._browser_name = browser
        self._page_fetcher = page_fetcher
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._browser_lock = asyncio.Lock()

    async def close(self) -> None:
        await self.client.aclose()
        async with self._browser_lock:
            await self._cleanup_playwright()

    async def _ensure_browser(self) -> None:
        if self._page_fetcher is not None or self._browser is not None:
            return
        async with self._browser_lock:
            if self._browser is not None or self._page_fetcher is not None:
                return
            self._playwright = await async_playwright().start()
            launcher = getattr(self._playwright, self._browser_name, None)
            if launcher is None:
                await self._cleanup_playwright()
                raise ValueError(f"Unsupported browser type: {self._browser_name}")
            try:
                # In many container environments, Chromium must be launched without sandbox
                self._browser = await launcher.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
            except (PlaywrightError, OSError) as exc:  # pragma: no cover - defensive
                await self._cleanup_playwright()
                raise BrowserLaunchError("Failed to launch Playwright browser") from exc

    async def _cleanup_playwright(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def _fetch_page_content(self, url: str) -> str:
        if self._page_fetcher is not None:
            html = await self._page_fetcher(url)
            return html

        await self._ensure_browser()
        if self._browser is None:
            raise BrowserLaunchError("Browser is not initialized")

        page = await self._browser.new_page()
        timeout_ms = int(self._timeout * 1000)
        # These Playwright methods are synchronous in Python
        page.set_default_navigation_timeout(timeout_ms)
        page.set_default_timeout(timeout_ms)

        async def _navigate_once() -> None:
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            try:
                await page.wait_for_selector("div.market_listing_row", timeout=timeout_ms)
            except PlaywrightTimeoutError:
                # Capture whatever rendered; listings may still be parsable
                pass
            # Allow additional time for late-loading resources (images, pricing data, etc.).
            await page.wait_for_timeout(5000)

        try:
            try:
                await _navigate_once()
            except (PlaywrightTimeoutError, PlaywrightError):
                # Simple one-time retry to mitigate transient flakiness
                await asyncio.sleep(1.0)
                await _navigate_once()
            html = await page.content()
            return html
        except PlaywrightError as exc:  # pragma: no cover - network/runtime failures
            raise BrowserLaunchError("Failed to load listings page") from exc
        finally:
            await page.close()

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
        self, appid: int, market_hash_name: str, count: int = 100
    ) -> Iterable[ParsedListing]:
        encoded_name = quote(market_hash_name, safe="")
        url = (
            f"https://steamcommunity.com/market/listings/{appid}/{encoded_name}?count={count}"
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
