from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx
import structlog

from ..core.config import get_settings


logger = structlog.get_logger(__name__)


@dataclass
class InspectResult:
    float_value: float
    paint_seed: int | None
    paint_index: int | None
    stickers: list[Dict[str, Any]]
    wear_name: str | None


class InspectClient:
    def __init__(self, *, timeout: Optional[float] = None) -> None:
        self.settings = get_settings()
        self._timeout = timeout if timeout is not None else self.settings.float_api_timeout
        self.client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={
                "Accept": "application/json",
                "Origin": "https://csfloat.com",
                "Referer": "https://csfloat.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def inspect(self, inspect_url: str) -> Optional[InspectResult]:
        """Inspect an item using the CSFloat API.

        Args:
            inspect_url: Steam inspect URL (steam://rungame/730/...)

        Returns:
            InspectResult if successful, None if all retries fail
        """
        retries = 3
        delay = 2.0
        for attempt in range(retries):
            try:
                return await self._inspect_once(inspect_url)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                logger.warning(
                    "Inspect attempt failed",
                    attempt=attempt + 1,
                    retries=retries,
                    error=str(exc),
                    inspect_url=inspect_url,
                )
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    logger.error("All inspect attempts failed", inspect_url=inspect_url)
                    return None
        return None

    async def _inspect_once(self, inspect_url: str) -> InspectResult:
        """Make a single API request to CSFloat.

        Args:
            inspect_url: Steam inspect URL

        Returns:
            InspectResult with extracted data

        Raises:
            httpx.HTTPError: On HTTP request failures
            ValueError: On invalid/missing response data
            KeyError: On missing required fields in API response
        """
        # URL-encode the inspect URL for the API request
        encoded_url = quote(inspect_url, safe="")
        api_url = f"https://api.csfloat.com/?url={encoded_url}"

        logger.info("Calling CSFloat API", inspect_url=inspect_url, api_url=api_url)

        try:
            response = await self.client.get(api_url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "CSFloat API HTTP error",
                status=exc.response.status_code,
                url=api_url,
                inspect_url=inspect_url,
            )
            raise ValueError(f"CSFloat API returned status {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("CSFloat API request error", error=str(exc), url=api_url)
            raise ValueError(f"Failed to connect to CSFloat API: {exc}") from exc
        except ValueError as exc:
            # JSON decode error
            logger.error("CSFloat API JSON error", error=str(exc), url=api_url)
            raise ValueError("Failed to parse CSFloat API JSON response") from exc

        # Extract iteminfo from response
        if "iteminfo" not in data:
            logger.error("CSFloat API missing iteminfo", data_keys=list(data.keys()), inspect_url=inspect_url)
            raise ValueError("CSFloat API response missing 'iteminfo' field")

        iteminfo = data["iteminfo"]

        # Extract required float value
        if "floatvalue" not in iteminfo:
            logger.error("CSFloat API missing floatvalue", iteminfo_keys=list(iteminfo.keys()), inspect_url=inspect_url)
            raise ValueError("CSFloat API response missing 'floatvalue' field")

        float_value = float(iteminfo["floatvalue"])

        # Extract optional fields with defaults
        paint_seed = iteminfo.get("paintseed")
        paint_index = iteminfo.get("paintindex")
        wear_name = iteminfo.get("wear_name")

        # Convert stickers array to list of dicts
        stickers = []
        if "stickers" in iteminfo and isinstance(iteminfo["stickers"], list):
            for sticker in iteminfo["stickers"]:
                if isinstance(sticker, dict):
                    stickers.append(sticker)

        logger.info(
            "Successfully extracted item data",
            float_value=float_value,
            paint_seed=paint_seed,
            paint_index=paint_index,
            wear_name=wear_name,
            sticker_count=len(stickers),
        )

        return InspectResult(
            float_value=float_value,
            paint_seed=paint_seed,
            paint_index=paint_index,
            stickers=stickers,
            wear_name=wear_name,
        )
