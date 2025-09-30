from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.db import get_session, init_models
from ..core.models import Watchlist

app = FastAPI(title="CS2 Market Watcher")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.on_event("startup")
async def _startup() -> None:
    await init_models()


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
async def list_watchlist(session: AsyncSession = Depends(get_session)) -> list[WatchResponse]:
    result = await session.execute(select(Watchlist))
    rows = result.scalars().all()
    return [WatchResponse.from_model(row) for row in rows]


@app.post("/watch", response_model=WatchResponse, status_code=status.HTTP_201_CREATED)
async def create_watch(
    payload: WatchRequest,
    session: AsyncSession = Depends(get_session),
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


@app.delete("/watch/{watch_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_watch(
    watch_id: int, session: AsyncSession = Depends(get_session)
) -> Response:
    result = await session.execute(select(Watchlist).where(Watchlist.id == watch_id))
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    await session.delete(model)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


STATUS_MESSAGES = {
    "created": "Watch added successfully.",
    "updated": "Watch updated successfully.",
    "deleted": "Watch removed successfully.",
    "not_found": "Requested watch could not be found.",
    "error": "Unable to process form submission.",
}


def parse_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return float(stripped)


def parse_int_list(value: str | None) -> list[int] | None:
    if value is None:
        return None
    items: list[int] = []
    for part in value.split(","):
        candidate = part.strip()
        if not candidate:
            continue
        items.append(int(candidate))
    return items or None


def parse_str_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    parts = [segment.strip() for segment in re.split(r"[\n,]", value) if segment.strip()]
    return parts or None


def _build_rule_config(
    *,
    float_min: str | None,
    float_max: str | None,
    seed_whitelist: str | None,
    sticker_any: str | None,
    target_resale_usd: str,
    min_profit_usd: str,
) -> RuleConfig:
    return RuleConfig(
        float_min=parse_optional_float(float_min),
        float_max=parse_optional_float(float_max),
        seed_whitelist=parse_int_list(seed_whitelist),
        sticker_any=parse_str_list(sticker_any),
        target_resale_usd=float(target_resale_usd),
        min_profit_usd=float(min_profit_usd),
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_root() -> RedirectResponse:
    return RedirectResponse(url="/admin/watches", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/watches", response_class=HTMLResponse)
async def admin_watchlist(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    result = await session.execute(select(Watchlist).order_by(Watchlist.id))
    rows = result.scalars().all()
    watches = [WatchResponse.from_model(row) for row in rows]
    status_key = request.query_params.get("status")
    message = STATUS_MESSAGES.get(status_key or "")
    settings = get_settings()
    return templates.TemplateResponse(
        "watchlist.html",
        {
            "request": request,
            "watches": watches,
            "status_message": message,
            "default_currency": settings.steam_currency_id,
        },
    )


@app.post("/admin/watches", response_class=HTMLResponse)
async def admin_create_watch(
    appid: int = Form(...),
    market_hash_name: str = Form(...),
    url: str = Form(...),
    currency_id: int = Form(1),
    float_min: str | None = Form(None),
    float_max: str | None = Form(None),
    seed_whitelist: str | None = Form(None),
    sticker_any: str | None = Form(None),
    target_resale_usd: str = Form(...),
    min_profit_usd: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    try:
        rules = _build_rule_config(
            float_min=float_min,
            float_max=float_max,
            seed_whitelist=seed_whitelist,
            sticker_any=sticker_any,
            target_resale_usd=target_resale_usd,
            min_profit_usd=min_profit_usd,
        )
    except Exception:
        return RedirectResponse(url="/admin/watches?status=error", status_code=status.HTTP_303_SEE_OTHER)

    model = Watchlist(
        appid=appid,
        market_hash_name=market_hash_name,
        url=url,
        currency_id=currency_id,
        rules=rules.model_dump(),
    )
    session.add(model)
    return RedirectResponse(url="/admin/watches?status=created", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/watches/{watch_id}", response_class=HTMLResponse)
async def admin_update_watch(
    watch_id: int,
    appid: int = Form(...),
    market_hash_name: str = Form(...),
    url: str = Form(...),
    currency_id: int = Form(1),
    float_min: str | None = Form(None),
    float_max: str | None = Form(None),
    seed_whitelist: str | None = Form(None),
    sticker_any: str | None = Form(None),
    target_resale_usd: str = Form(...),
    min_profit_usd: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    result = await session.execute(select(Watchlist).where(Watchlist.id == watch_id))
    model = result.scalar_one_or_none()
    if model is None:
        return RedirectResponse(url="/admin/watches?status=not_found", status_code=status.HTTP_303_SEE_OTHER)

    try:
        rules = _build_rule_config(
            float_min=float_min,
            float_max=float_max,
            seed_whitelist=seed_whitelist,
            sticker_any=sticker_any,
            target_resale_usd=target_resale_usd,
            min_profit_usd=min_profit_usd,
        )
    except Exception:
        return RedirectResponse(url="/admin/watches?status=error", status_code=status.HTTP_303_SEE_OTHER)

    model.appid = appid
    model.market_hash_name = market_hash_name
    model.url = url
    model.currency_id = currency_id
    model.rules = rules.model_dump()
    return RedirectResponse(url="/admin/watches?status=updated", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/watches/{watch_id}/delete", response_class=HTMLResponse)
async def admin_delete_watch(
    watch_id: int,
    session: AsyncSession = Depends(session_dependency()),
) -> RedirectResponse:
    result = await session.execute(select(Watchlist).where(Watchlist.id == watch_id))
    model = result.scalar_one_or_none()
    if model is None:
        return RedirectResponse(url="/admin/watches?status=not_found", status_code=status.HTTP_303_SEE_OTHER)
    await session.delete(model)
    return RedirectResponse(url="/admin/watches?status=deleted", status_code=status.HTTP_303_SEE_OTHER)

