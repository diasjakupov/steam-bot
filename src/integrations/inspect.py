from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import structlog
from playwright.async_api import (
    Browser,
    Error as PlaywrightError,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

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
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._browser_lock = asyncio.Lock()

    async def close(self) -> None:
        async with self._browser_lock:
            await self._cleanup_playwright()

    async def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        async with self._browser_lock:
            if self._browser is not None:
                return
            self._playwright = await async_playwright().start()
            try:
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
            except (PlaywrightError, OSError) as exc:
                await self._cleanup_playwright()
                raise RuntimeError("Failed to launch Playwright browser") from exc

    async def _cleanup_playwright(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def inspect(self, inspect_url: str) -> Optional[InspectResult]:
        retries = 3
        delay = 2.0
        for attempt in range(retries):
            try:
                return await self._inspect_once(inspect_url)
            except (PlaywrightError, PlaywrightTimeoutError, ValueError) as exc:
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
        await self._ensure_browser()
        if self._browser is None:
            raise RuntimeError("Browser is not initialized")

        page = await self._browser.new_page()
        timeout_ms = int(self._timeout * 1000)
        page.set_default_navigation_timeout(timeout_ms)
        page.set_default_timeout(timeout_ms)

        try:
            logger.info("Navigating to CSFloat checker", inspect_url=inspect_url)
            await page.goto("https://csfloat.com/checker")
            await page.wait_for_timeout(5000)
            await page.fill("#mat-input-0", inspect_url)
            await page.wait_for_timeout(5000)

            # Check if float div appeared (correct class: mat-mdc-tooltip-trigger wear)
            float_element = await page.query_selector(".mat-mdc-tooltip-trigger.wear")
            if not float_element:
                logger.warning("Float value element not found after 5 seconds, skipping", inspect_url=inspect_url)
                return None

            float_text = await float_element.inner_text()
            float_value = self._parse_float(float_text)

            logger.info("Successfully extracted float value", float_value=float_value)

            # Try to extract additional data if available
            paint_seed = await self._extract_paint_seed(page)
            paint_index = await self._extract_paint_index(page)
            wear_name = await self._extract_wear_name(page)
            stickers = await self._extract_stickers(page)

            return InspectResult(
                float_value=float_value,
                paint_seed=paint_seed,
                paint_index=paint_index,
                stickers=stickers,
                wear_name=wear_name,
            )
        finally:
            await page.close()

    @staticmethod
    def _parse_float(text: str) -> float:
        """Extract float value from text like '0.123456' or 'Float: 0.123456'"""
        match = re.search(r"(\d+\.\d+)", text)
        if not match:
            raise ValueError(f"Could not parse float value from: {text}")
        return float(match.group(1))

    async def _extract_paint_seed(self, page) -> Optional[int]:
        """Try to extract paint seed from the page"""
        try:
            # Look for text containing "Paint Seed" or "Seed"
            seed_element = await page.query_selector("text=/paint seed|seed/i")
            if seed_element:
                seed_text = await seed_element.inner_text()
                match = re.search(r"(\d+)", seed_text)
                if match:
                    return int(match.group(1))
        except Exception:
            pass
        return None

    async def _extract_paint_index(self, page) -> Optional[int]:
        """Try to extract paint index from the page"""
        try:
            # Look for text containing "Paint Index"
            index_element = await page.query_selector("text=/paint index/i")
            if index_element:
                index_text = await index_element.inner_text()
                match = re.search(r"(\d+)", index_text)
                if match:
                    return int(match.group(1))
        except Exception:
            pass
        return None

    async def _extract_wear_name(self, page) -> Optional[str]:
        """Try to extract wear name (Factory New, Minimal Wear, etc.)"""
        try:
            # Look for common wear tier names
            wear_patterns = [
                "Factory New",
                "Minimal Wear",
                "Field-Tested",
                "Well-Worn",
                "Battle-Scarred",
            ]
            for wear in wear_patterns:
                element = await page.query_selector(f"text=/{wear}/i")
                if element:
                    return wear
        except Exception:
            pass
        return None

    async def _extract_stickers(self, page) -> list[Dict[str, Any]]:
        """Try to extract sticker information from the page"""
        try:
            stickers = []
            # CSFloat usually shows stickers with specific classes or patterns
            # This is a best-effort extraction
            sticker_elements = await page.query_selector_all(".sticker, [class*='sticker']")
            for element in sticker_elements:
                text = await element.inner_text()
                if text:
                    stickers.append({"name": text.strip()})
            return stickers
        except Exception:
            pass
        return []
