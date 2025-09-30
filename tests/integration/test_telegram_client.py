import pytest
import respx

from src.integrations.telegram import TelegramClient
from src.core import config as core_config


@pytest.mark.asyncio
async def test_telegram_client_sends_message(monkeypatch):
    settings_patch = {
        "TELEGRAM_BOT_TOKEN": "token",
        "TELEGRAM_CHAT_ID": "chat",
    }
    for key, value in settings_patch.items():
        monkeypatch.setenv(key, value)
    core_config.get_settings.cache_clear()
    client = TelegramClient()
    with respx.mock(base_url="https://api.telegram.org") as mock:
        request = mock.post("/bottoken/sendMessage").respond(200, json={"ok": True})
        await client.send_message("hello")
    await client.close()
    core_config.get_settings.cache_clear()
    assert request.called

