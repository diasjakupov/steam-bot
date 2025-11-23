from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, List
from urllib.parse import unquote, urlparse

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.db import get_session, init_models
from ..core.forex import get_usd_to_kzt_rate
from ..core.models import InspectHistory, Watchlist, WorkerSettings

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
    "worker_started": "Worker resumed.",
    "worker_stopped": "Worker paused.",
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


def extract_listing_details(url: str) -> tuple[int, str]:
    parsed = urlparse(url)
    parts = [segment for segment in parsed.path.split("/") if segment]
    if len(parts) < 4 or parts[0] != "market" or parts[1] != "listings":
        raise ValueError("Unsupported listing URL format")
    try:
        appid = int(parts[2])
    except ValueError as exc:
        raise ValueError("AppID segment must be numeric") from exc
    market_hash_name = unquote("/".join(parts[3:]))
    if not market_hash_name:
        raise ValueError("Missing market hash name segment")
    return appid, market_hash_name


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

    # Get worker status from database
    worker_result = await session.execute(select(WorkerSettings).where(WorkerSettings.id == 1))
    worker_settings = worker_result.scalar_one_or_none()
    worker_enabled = worker_settings.enabled if worker_settings else True

    # Get current USD to KZT exchange rate (pass None since Redis is removed)
    usd_to_kzt = await get_usd_to_kzt_rate(None)
    history_stmt = (
        select(InspectHistory)
        .order_by(InspectHistory.last_inspected.desc())
        .limit(100)
    )
    history_rows = await session.execute(history_stmt)
    history_models = history_rows.scalars().unique().all()
    history_payload: list[dict[str, Any]] = []
    for entry in history_models:
        result_data = entry.result or {}
        float_value = result_data.get("float_value")

        # Skip if no float value
        if float_value is None:
            continue

        # Only show items that match their watch's float range
        if entry.watchlist:
            rules = entry.watchlist.rules or {}
            float_min = rules.get("float_min")
            float_max = rules.get("float_max")

            # Check if float is within the specified range
            if float_min is not None and float_value < float_min:
                continue
            if float_max is not None and float_value > float_max:
                continue

            history_payload.append(
                {
                    "inspect_url": entry.inspect_url,
                    "float_value": float_value,
                    "paint_seed": result_data.get("paint_seed"),
                    "paint_index": result_data.get("paint_index"),
                    "wear_name": result_data.get("wear_name"),
                    "stickers": result_data.get("stickers", []),
                    "last_inspected": entry.last_inspected.isoformat() if entry.last_inspected else None,
                    "watch_name": entry.watchlist.market_hash_name,
                }
            )
    # Group by watch_name and sort by float_value
    history_payload.sort(key=lambda x: (x["watch_name"] or "", x["float_value"] or 999))
    return templates.TemplateResponse(
        "watchlist.html",
        {
            "request": request,
            "watches": watches,
            "status_message": message,
            "default_currency": settings.steam_currency_id,
            "default_min_profit": settings.admin_default_min_profit_usd,
            "worker_enabled": worker_enabled,
            "inspect_history": history_payload,
            "usd_to_kzt": usd_to_kzt,
        },
    )


@app.post("/admin/worker/start", response_class=HTMLResponse)
async def admin_start_worker(session: AsyncSession = Depends(get_session)) -> RedirectResponse:
    result = await session.execute(select(WorkerSettings).where(WorkerSettings.id == 1))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = WorkerSettings(id=1, enabled=True)
        session.add(settings)
    else:
        settings.enabled = True
        settings.updated_at = datetime.utcnow()
    await session.commit()
    return RedirectResponse(url="/admin/watches?status=worker_started", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/worker/stop", response_class=HTMLResponse)
async def admin_stop_worker(session: AsyncSession = Depends(get_session)) -> RedirectResponse:
    result = await session.execute(select(WorkerSettings).where(WorkerSettings.id == 1))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = WorkerSettings(id=1, enabled=False)
        session.add(settings)
    else:
        settings.enabled = False
        settings.updated_at = datetime.utcnow()
    await session.commit()
    return RedirectResponse(url="/admin/watches?status=worker_stopped", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/watches", response_class=HTMLResponse)
async def admin_create_watch(
    url: str = Form(...),
    float_min: str | None = Form(None),
    float_max: str | None = Form(None),
    target_resale_usd: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    settings = get_settings()
    try:
        appid, market_hash_name = extract_listing_details(url)
        # Convert KZT to USD using current exchange rate
        usd_to_kzt = await get_usd_to_kzt_rate(None)
        target_resale_kzt = float(target_resale_usd)
        target_resale_usd_converted = target_resale_kzt / usd_to_kzt

        rules = RuleConfig(
            float_min=parse_optional_float(float_min),
            float_max=parse_optional_float(float_max),
            seed_whitelist=None,
            sticker_any=None,
            target_resale_usd=target_resale_usd_converted,
            min_profit_usd=settings.admin_default_min_profit_usd,
        )
    except Exception:
        return RedirectResponse(url="/admin/watches?status=error", status_code=status.HTTP_303_SEE_OTHER)

    model = Watchlist(
        appid=appid,
        market_hash_name=market_hash_name,
        url=url,
        currency_id=settings.steam_currency_id,
        rules=rules.model_dump(),
    )
    session.add(model)
    return RedirectResponse(url="/admin/watches?status=created", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/watches/{watch_id}", response_class=HTMLResponse)
async def admin_update_watch(
    watch_id: int,
    url: str = Form(...),
    float_min: str | None = Form(None),
    float_max: str | None = Form(None),
    target_resale_usd: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    result = await session.execute(select(Watchlist).where(Watchlist.id == watch_id))
    model = result.scalar_one_or_none()
    if model is None:
        return RedirectResponse(url="/admin/watches?status=not_found", status_code=status.HTTP_303_SEE_OTHER)

    settings = get_settings()
    existing_rules = model.rules or {}
    try:
        appid, market_hash_name = extract_listing_details(url)
        min_profit_value = existing_rules.get("min_profit_usd", settings.admin_default_min_profit_usd)
        if min_profit_value is None:
            min_profit_value = settings.admin_default_min_profit_usd

        # Convert KZT to USD using current exchange rate
        usd_to_kzt = await get_usd_to_kzt_rate(None)
        target_resale_kzt = float(target_resale_usd)
        target_resale_usd_converted = target_resale_kzt / usd_to_kzt

        rules = RuleConfig(
            float_min=parse_optional_float(float_min),
            float_max=parse_optional_float(float_max),
            seed_whitelist=existing_rules.get("seed_whitelist"),
            sticker_any=existing_rules.get("sticker_any"),
            target_resale_usd=target_resale_usd_converted,
            min_profit_usd=float(min_profit_value),
        )
    except Exception:
        return RedirectResponse(url="/admin/watches?status=error", status_code=status.HTTP_303_SEE_OTHER)

    model.appid = appid
    model.market_hash_name = market_hash_name
    model.url = url
    model.rules = rules.model_dump()
    return RedirectResponse(url="/admin/watches?status=updated", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/watches/{watch_id}/delete", response_class=HTMLResponse)
async def admin_delete_watch(
    watch_id: int,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    result = await session.execute(select(Watchlist).where(Watchlist.id == watch_id))
    model = result.scalar_one_or_none()
    if model is None:
        return RedirectResponse(url="/admin/watches?status=not_found", status_code=status.HTTP_303_SEE_OTHER)
    await session.delete(model)
    return RedirectResponse(url="/admin/watches?status=deleted", status_code=status.HTTP_303_SEE_OTHER)
