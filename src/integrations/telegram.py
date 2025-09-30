from __future__ import annotations

import httpx

from ..core.config import get_settings


class TelegramClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        await self.client.aclose()

    async def send_message(self, text: str, parse_mode: str = "Markdown") -> None:
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.settings.telegram_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()

