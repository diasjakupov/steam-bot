import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.core import config as core_config


@pytest.fixture(autouse=True)
def default_env(monkeypatch):
    env = {
        "DATABASE_URL": "postgresql+psycopg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "STEAM_CURRENCY_ID": "1",
        "FLOAT_API_TIMEOUT": "30",
        "TELEGRAM_BOT_TOKEN": "token",
        "TELEGRAM_CHAT_ID": "chat",
        "POLL_INTERVAL_S": "10",
        "COMBINED_FEE_RATE": "0.15",
        "COMBINED_FEE_MIN_CENTS": "1",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    core_config.get_settings.cache_clear()
    yield
    core_config.get_settings.cache_clear()
