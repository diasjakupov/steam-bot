from __future__ import annotations

from functools import lru_cache
from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: AnyUrl = Field(alias="DATABASE_URL")
    redis_url: AnyUrl = Field(alias="REDIS_URL")
    steam_currency_id: int = Field(default=1, alias="STEAM_CURRENCY_ID")
    inspect_base_url: AnyUrl = Field(alias="INSPECT_BASE_URL")
    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(alias="TELEGRAM_CHAT_ID")
    poll_interval_s: float = Field(default=10.0, alias="POLL_INTERVAL_S")
    inspect_rps_per_account: float = Field(default=0.8, alias="INSPECT_RPS_PER_ACCOUNT")
    inspect_accounts: int = Field(default=1, alias="INSPECT_ACCOUNTS")
    combined_fee_rate: float = Field(default=0.15, alias="COMBINED_FEE_RATE")
    combined_fee_min_cents: int = Field(default=1, alias="COMBINED_FEE_MIN_CENTS")
    admin_default_min_profit_usd: float = Field(default=0.0, alias="ADMIN_DEFAULT_MIN_PROFIT_USD")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra = "ignore"
    )
        


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]

