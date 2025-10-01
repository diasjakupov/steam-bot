from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
import structlog

from ..core.config import get_settings


def _coerce_optional_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


@dataclass
class InspectResult:
    float_value: float
    paint_seed: Optional[int]
    paint_index: Optional[int]
    stickers: List[Dict[str, Any]] = field(default_factory=list)
    wear_name: Optional[str] = None
    custom_name: Optional[str] = None
    raw_iteminfo: Dict[str, Any] = field(default_factory=dict)


class InspectClient:
    def __init__(self, *, timeout: Optional[float] = None) -> None:
        settings = get_settings()
        self.logger = structlog.get_logger(__name__)
        self.base_url = str(settings.csfloat_api_base_url).rstrip("/")
        request_timeout = timeout if timeout is not None else settings.float_api_timeout
        self.request_delay = settings.float_api_request_delay
        self.client = httpx.AsyncClient(timeout=request_timeout)

    async def close(self) -> None:
        await self.client.aclose()

    async def inspect(self, inspect_url: str) -> Optional[InspectResult]:
        if not inspect_url or not inspect_url.startswith("steam://"):
            self.logger.error(
                "inspect.invalid_url",
                inspect_url=inspect_url,
            )
            return None

        encoded_link = quote(inspect_url, safe=":/%")
        request_url = f"{self.base_url}/?url={encoded_link}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
            ),
            "sec-ch-ua-platform": '"macOS"',
            "Referer": "https://csfloat.com/",
            "Origin": "https://csfloat.com",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "sec-ch-ua-mobile": "?0",
        }

        try:
            self.logger.debug(
                "inspect.request",
                request_url=request_url,
                headers=headers,
            )
            response = await self.client.get(request_url, headers=headers)
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - exercised in integration flows
            status = exc.response.status_code if exc.response is not None else "unknown"
            self.logger.error(
                "inspect.http_error",
                inspect_url=inspect_url,
                request_url=request_url,
                headers=headers,
                status_code=status,
                response_text=getattr(exc.response, "text", ""),
            )
            if exc.response is not None and exc.response.status_code == 429:
                self.logger.warning("inspect.rate_limited")
            return None
        except httpx.RequestError as exc:
            self.logger.error(
                "inspect.request_error",
                inspect_url=inspect_url,
                request_url=request_url,
                headers=headers,
                error=str(exc),
            )
            return None
        except ValueError as exc:
            self.logger.error(
                "inspect.json_error",
                inspect_url=inspect_url,
                request_url=request_url,
                headers=headers,
                error=str(exc),
            )
            return None
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.exception(
                "inspect.unexpected_error",
                inspect_url=inspect_url,
                request_url=request_url,
                headers=headers,
                exc_info=exc,
            )
            return None
        finally:
            if self.request_delay > 0:
                await asyncio.sleep(self.request_delay)

        item_info = data.get("iteminfo") or {}
        if not item_info:
            self.logger.warning(
                "inspect.missing_iteminfo",
                inspect_url=inspect_url,
                response=data,
            )
            return None

        float_value = item_info.get("floatvalue")
        if float_value is None:
            self.logger.warning(
                "inspect.missing_float",
                inspect_url=inspect_url,
                iteminfo=item_info,
            )
            return None

        stickers_raw = item_info.get("stickers") or []
        stickers: List[Dict[str, Any]] = []
        if isinstance(stickers_raw, list):
            stickers = [sticker for sticker in stickers_raw if isinstance(sticker, dict)]

        result = InspectResult(
            float_value=float(float_value),
            paint_seed=_coerce_optional_int(item_info.get("paintseed")),
            paint_index=_coerce_optional_int(item_info.get("paintindex")),
            stickers=stickers,
            wear_name=item_info.get("wear_name"),
            custom_name=item_info.get("full_item_name"),
            raw_iteminfo=item_info,
        )

        self.logger.info(
            "inspect.success",
            inspect_url_fragment=inspect_url[-50:],
            float_value=result.float_value,
            paint_seed=result.paint_seed,
        )
        return result
