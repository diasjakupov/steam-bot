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


class SteamClient:
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

    async def close(self) -> None:
        await self.client.aclose()

    async def _fetch_page_content(self, url: str) -> str:
        """Fetch page content using Steam's /render/ API endpoint or custom page_fetcher.

        Args:
            url: The Steam market listing URL (e.g., https://steamcommunity.com/market/listings/730/AK-47...)

        Returns:
            HTML content string
        """
        if self._page_fetcher is not None:
            html = await self._page_fetcher(url)
            return html

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

        try:
            response = await self.client.get(render_url, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Extract results_html from JSON response
            if "results_html" not in data:
                self.logger.error("steam.missing_results_html", data_keys=list(data.keys()))
                raise SteamAPIError("Steam API response missing 'results_html' field")

            return data["results_html"]
        except httpx.HTTPStatusError as exc:
            self.logger.error("steam.http_error", status=exc.response.status_code, url=render_url)
            raise SteamAPIError(f"Steam API returned status {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            self.logger.error("steam.request_error", error=str(exc), url=render_url)
            raise SteamAPIError(f"Failed to connect to Steam API: {exc}") from exc
        except ValueError as exc:
            # JSON decode error
            self.logger.error("steam.json_error", error=str(exc), url=render_url)
            raise SteamAPIError("Failed to parse Steam API JSON response") from exc

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
