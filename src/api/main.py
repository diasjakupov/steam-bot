from __future__ import annotations

from typing import Any, List

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.db import session_dependency
from ..core.models import Watchlist

app = FastAPI(title="CS2 Market Watcher")


class RuleConfig(BaseModel):
    float_min: float | None = Field(default=None, ge=0, le=1)
    float_max: float | None = Field(default=None, ge=0, le=1)
    seed_whitelist: List[int] | None = None
    sticker_any: List[str] | None = None
    target_resale_usd: float = Field(..., gt=0)
    min_profit_usd: float = Field(..., ge=0)


class WatchRequest(BaseModel):
    appid: int
    market_hash_name: str
    url: str
    currency_id: int = 1
    rules: RuleConfig


class WatchResponse(BaseModel):
    id: int
    appid: int
    market_hash_name: str
    url: str
    currency_id: int
    rules: RuleConfig

    @classmethod
    def from_model(cls, model: Watchlist) -> "WatchResponse":
        return cls(
            id=model.id,
            appid=model.appid,
            market_hash_name=model.market_hash_name,
            url=model.url,
            currency_id=model.currency_id,
            rules=RuleConfig(**model.rules),
        )


@app.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "currency_id": str(settings.steam_currency_id)}


@app.get("/watch", response_model=list[WatchResponse])
async def list_watchlist(session: AsyncSession = Depends(session_dependency())) -> list[WatchResponse]:
    result = await session.execute(select(Watchlist))
    rows = result.scalars().all()
    return [WatchResponse.from_model(row) for row in rows]


@app.post("/watch", response_model=WatchResponse, status_code=status.HTTP_201_CREATED)
async def create_watch(
    payload: WatchRequest,
    session: AsyncSession = Depends(session_dependency()),
) -> WatchResponse:
    model = Watchlist(
        appid=payload.appid,
        market_hash_name=payload.market_hash_name,
        url=payload.url,
        currency_id=payload.currency_id,
        rules=payload.rules.model_dump(),
    )
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return WatchResponse.from_model(model)


@app.delete("/watch/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watch(watch_id: int, session: AsyncSession = Depends(session_dependency())) -> None:
    result = await session.execute(select(Watchlist).where(Watchlist.id == watch_id))
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    await session.delete(model)

