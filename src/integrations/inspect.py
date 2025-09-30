from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from ..core.config import get_settings


@dataclass
class InspectResult:
    float_value: float
    paint_seed: int | None
    paint_index: int | None
    stickers: list[Dict[str, Any]]
    wear_name: str | None


class InspectClient:
    def __init__(self, *, timeout: float = 10.0) -> None:
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self.client.aclose()

    async def inspect(self, inspect_url: str) -> InspectResult | None:
        params = {"url": inspect_url}
        retries = 3
        delay = 1.0
        for attempt in range(retries):
            try:
                resp = await self.client.get(str(self.settings.inspect_base_url), params=params)
                resp.raise_for_status()
                payload: Dict[str, Any] = resp.json()
                return InspectResult(
                    float_value=payload.get("float_value"),
                    paint_seed=payload.get("paint_seed"),
                    paint_index=payload.get("paint_index"),
                    stickers=payload.get("stickers", []),
                    wear_name=payload.get("wear_name"),
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {429, 500, 502, 503, 504} and attempt < retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise
            except httpx.RequestError:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
        return None

