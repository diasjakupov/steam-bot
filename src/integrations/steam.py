from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Iterable
from urllib.parse import quote

import httpx

from ..core.config import get_settings
from ..core.parsing import ParsedListing, parse_results_html


@dataclass
class PriceOverview:
    lowest_price: str | None
    median_price: str | None
    volume: str | None


class SteamClient:
    def __init__(self, *, timeout: float = 10.0) -> None:
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "cs2-market-watcher/1.0"})

    async def close(self) -> None:
        await self.client.aclose()

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

    async def fetch_listings(self, appid: int, market_hash_name: str, count: int = 100) -> Iterable[ParsedListing]:
        params = {
            "start": 0,
            "count": count,
            "currency": self.settings.steam_currency_id,
            "format": "json",
        }
        encoded_name = quote(market_hash_name, safe="")
        url = f"https://steamcommunity.com/market/listings/{appid}/{encoded_name}"
        resp = await self.client.get(url + "/render", params=params)
        resp.raise_for_status()
        payload: Dict[str, Any] = resp.json()
        results_html = payload.get("results_html", "")
        return list(parse_results_html(results_html))


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

