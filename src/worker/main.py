from __future__ import annotations

import asyncio
import random
from dataclasses import asdict

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.db import get_sessionmaker
from ..core.models import Alert, ListingSnapshot, Watchlist
from ..core.profit import ProfitInputs, is_profitable
from ..core.rate_limit import build_bucket
from ..integrations.inspect import InspectClient
from ..integrations.steam import SteamClient
from ..integrations.telegram import TelegramClient

logger = structlog.get_logger(__name__)


async def evaluate_and_alert(
    session: AsyncSession,
    telegram: TelegramClient,
    watch: Watchlist,
    listing: ListingSnapshot,
    inspect_data: dict,
) -> None:
    rules = watch.rules
    float_value = inspect_data.get("float_value")
    if float_value is None:
        return
    float_min = rules.get("float_min")
    float_max = rules.get("float_max")
    if float_min is not None and float_value < float_min:
        return
    if float_max is not None and float_value > float_max:
        return
    seed_whitelist = rules.get("seed_whitelist")
    paint_seed = inspect_data.get("paint_seed")
    if seed_whitelist and paint_seed not in seed_whitelist:
        return
    sticker_any = rules.get("sticker_any") or []
    stickers_data = inspect_data.get("stickers", []) or []
    sticker_list = [s.get("name") for s in stickers_data if s.get("name")]
    sticker_names: set[str] = set()
    if sticker_any:
        sticker_names = set(sticker_list)
        if not sticker_names.intersection(sticker_any):
            return
    inputs = ProfitInputs(
        target_resale_usd=rules["target_resale_usd"],
        min_profit_usd=rules["min_profit_usd"],
        combined_fee_rate=get_settings().combined_fee_rate,
        combined_fee_min_cents=get_settings().combined_fee_min_cents,
    )
    if not is_profitable(listing.price_cents, inputs):
        return
    message = (
        f"{watch.market_hash_name} — candidate found\n"
        f"Price: ${listing.price_cents/100:.2f} | Float: {float_value:.6f} | Seed: {paint_seed}\n"
        f"Stickers: {', '.join(sticker_list) if sticker_list else 'None'}\n"
        f"[Open Steam Listing]({listing.parsed.get('listing_url') or watch.url})"
    )
    inspect_url = listing.parsed.get("inspect_url") if isinstance(listing.parsed, dict) else None
    if inspect_url:
        message += f"\n[Inspect Link]({inspect_url})"
    await telegram.send_message(message)
    listing.alerted = True
    alert = Alert(snapshot_id=listing.id, payload={"message": message, "inspect": inspect_data})
    session.add(alert)


async def process_watch(
    session: AsyncSession,
    steam: SteamClient,
    inspector: InspectClient,
    telegram: TelegramClient,
    redis: Redis,
    watch: Watchlist,
) -> None:
    listings = await steam.fetch_listings(watch.appid, watch.market_hash_name)
    inspect_bucket = await build_bucket(
        redis,
        key="inspect",
        rps=get_settings().inspect_rps_per_account * get_settings().inspect_accounts,
    )
    for parsed in listings:
        existing = await session.execute(
            select(ListingSnapshot).where(
                ListingSnapshot.watchlist_id == watch.id,
                ListingSnapshot.listing_key == parsed.listing_key,
                ListingSnapshot.price_cents == parsed.price_cents,
            )
        )
        snapshot = existing.scalar_one_or_none()
        if snapshot:
            continue
        snapshot = ListingSnapshot(
            watchlist_id=watch.id,
            listing_key=parsed.listing_key,
            price_cents=parsed.price_cents,
            parsed={"listing_url": parsed.listing_url, "inspect_url": parsed.inspect_url, "raw": parsed.raw},
        )
        session.add(snapshot)
        await session.flush()
        if not parsed.inspect_url:
            continue
        acquired = await inspect_bucket.acquire(timeout=5)
        if not acquired:
            continue
        inspect_result = await inspector.inspect(parsed.inspect_url)
        if not inspect_result:
            continue
        snapshot.inspected = asdict(inspect_result)
        await evaluate_and_alert(session, telegram, watch, snapshot, snapshot.inspected)


async def worker_loop() -> None:
    settings = get_settings()
    redis = Redis.from_url(str(settings.redis_url))
    sessionmaker = get_sessionmaker()
    steam = SteamClient()
    inspector = InspectClient()
    telegram = TelegramClient()
    try:
        while True:
            async with sessionmaker() as session:
                result = await session.execute(select(Watchlist))
                watches = result.scalars().all()
                for watch in watches:
                    try:
                        await process_watch(session, steam, inspector, telegram, redis, watch)
                        await session.commit()
                    except Exception as exc:  # pylint: disable=broad-except
                        await session.rollback()
                        logger.exception("watch processing failed", watch_id=watch.id, exc_info=exc)
                    await asyncio.sleep(random.uniform(settings.poll_interval_s * 0.2, settings.poll_interval_s * 0.4))
            await asyncio.sleep(settings.poll_interval_s + random.uniform(-2, 2))
    finally:
        await steam.close()
        await inspector.close()
        await telegram.close()
        await redis.aclose()


def main() -> None:
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()

