from __future__ import annotations

import asyncio
import random
from datetime import datetime
from dataclasses import asdict

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.db import get_sessionmaker, init_models
from ..core.models import Alert, InspectHistory, ListingSnapshot, Watchlist
from ..core.profit import ProfitInputs, is_profitable
from ..core.rate_limit import build_bucket
from ..integrations.inspect import InspectClient
from ..integrations.steam import SteamClient
from ..integrations.telegram import TelegramClient

logger = structlog.get_logger(__name__)
WORKER_STATE_KEY = "worker:enabled"


async def is_worker_enabled(redis: Redis) -> bool:
    value = await redis.get(WORKER_STATE_KEY)
    return value is None or value != b"0"


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
        logger.debug("Skipping item without float value", price_cents=listing.price_cents)
        return
        
    logger.info("Evaluating item for alerts", 
               price_cents=listing.price_cents,
               float_value=float_value,
               market_hash_name=watch.market_hash_name)
    
    float_min = rules.get("float_min")
    float_max = rules.get("float_max")
    if float_min is not None and float_value < float_min:
        logger.debug("Item below float minimum", float_value=float_value, float_min=float_min)
        return
    if float_max is not None and float_value > float_max:
        logger.debug("Item above float maximum", float_value=float_value, float_max=float_max)
        return
        
    seed_whitelist = rules.get("seed_whitelist")
    paint_seed = inspect_data.get("paint_seed")
    if seed_whitelist and paint_seed not in seed_whitelist:
        logger.debug("Item seed not in whitelist", paint_seed=paint_seed, seed_whitelist=seed_whitelist)
        return
        
    sticker_any = rules.get("sticker_any") or []
    stickers_data = inspect_data.get("stickers", []) or []
    sticker_list = [s.get("name") for s in stickers_data if s.get("name")]
    sticker_names: set[str] = set()
    if sticker_any:
        sticker_names = set(sticker_list)
        if not sticker_names.intersection(sticker_any):
            logger.debug("Item stickers don't match requirements", 
                        stickers=sticker_list, 
                        required_stickers=sticker_any)
            return
            
    inputs = ProfitInputs(
        target_resale_usd=rules["target_resale_usd"],
        min_profit_usd=rules["min_profit_usd"],
        combined_fee_rate=get_settings().combined_fee_rate,
        combined_fee_min_cents=get_settings().combined_fee_min_cents,
    )
    if not is_profitable(listing.price_cents, inputs):
        logger.debug("Item not profitable", 
                    price_cents=listing.price_cents,
                    target_resale=rules["target_resale_usd"],
                    min_profit=rules["min_profit_usd"])
        return
        
    logger.info("🚨 PROFITABLE ITEM FOUND! Sending alert", 
               price_cents=listing.price_cents,
               float_value=float_value,
               market_hash_name=watch.market_hash_name)
    
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
    logger.info("Fetching Steam listings", 
               market_hash_name=watch.market_hash_name, 
               appid=watch.appid)
    listings = await steam.fetch_listings(watch.appid, watch.market_hash_name)
    logger.info("Fetched listings from Steam", 
               count=len(listings), 
               market_hash_name=watch.market_hash_name)
    
    inspect_bucket = await build_bucket(
        redis,
        key="inspect",
        rps=get_settings().inspect_rps_per_account * get_settings().inspect_accounts,
    )
    
    new_listings = 0
    inspected_listings = 0
    
    for parsed in listings:
        if not await is_worker_enabled(redis):
            logger.info("Worker stop requested, ending current cycle early")
            break
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
            
        new_listings += 1
        logger.info("Found new listing", 
                   price_cents=parsed.price_cents,
                   price_usd=parsed.price_cents/100,
                   market_hash_name=watch.market_hash_name)
        
        snapshot = ListingSnapshot(
            watchlist_id=watch.id,
            listing_key=parsed.listing_key,
            price_cents=parsed.price_cents,
            parsed={"listing_url": parsed.listing_url, "inspect_url": parsed.inspect_url, "raw": parsed.raw},
        )
        session.add(snapshot)
        await session.flush()
        
        if not parsed.inspect_url:
            logger.debug("Skipping listing without inspect URL", price_cents=parsed.price_cents)
            continue
        
        cached_history = None
        if parsed.inspect_url:
            history_result = await session.execute(
                select(InspectHistory).where(InspectHistory.inspect_url == parsed.inspect_url)
            )
            cached_history = history_result.scalar_one_or_none()
        
        if cached_history and cached_history.result:
            logger.info(
                "Using cached inspect result",
                price_cents=parsed.price_cents,
                inspect_url=parsed.inspect_url,
            )
            cached_history.last_inspected = datetime.utcnow()
            cached_history.watchlist_id = watch.id
            snapshot.inspected = cached_history.result
            inspected_listings += 1
            await evaluate_and_alert(session, telegram, watch, snapshot, snapshot.inspected)
            continue

        logger.info("Attempting to inspect item", 
                   price_cents=parsed.price_cents,
                   inspect_url=parsed.inspect_url)

        acquired = await inspect_bucket.acquire(timeout=5)
        if not acquired:
            logger.warning("Rate limit reached, skipping inspection", price_cents=parsed.price_cents)
            continue
            
        inspect_result = await inspector.inspect(parsed.inspect_url)
        if not inspect_result:
            logger.warning("Inspection failed", price_cents=parsed.price_cents)
            continue

        inspected_listings += 1
        logger.info("Successfully inspected item", 
                   price_cents=parsed.price_cents,
                   float_value=inspect_result.get("float_value"),
                   paint_seed=inspect_result.get("paint_seed"))
        
        result_payload = asdict(inspect_result)
        snapshot.inspected = result_payload
        if cached_history is None:
            cached_history = InspectHistory(
                inspect_url=parsed.inspect_url,
                result=result_payload,
                watchlist_id=watch.id,
            )
            session.add(cached_history)
        else:
            cached_history.result = result_payload
            cached_history.watchlist_id = watch.id
        cached_history.last_inspected = datetime.utcnow()
        await evaluate_and_alert(session, telegram, watch, snapshot, snapshot.inspected)
    
    logger.info("Completed processing watch", 
               market_hash_name=watch.market_hash_name,
               total_listings=len(listings),
               new_listings=new_listings,
               inspected_listings=inspected_listings)


async def worker_loop() -> None:
    settings = get_settings()
    logger.info("Starting worker loop", poll_interval=settings.poll_interval_s)
    redis = Redis.from_url(str(settings.redis_url))
    await redis.setnx(WORKER_STATE_KEY, "1")
    sessionmaker = get_sessionmaker()
    steam = SteamClient()
    inspector = InspectClient()
    telegram = TelegramClient()
    try:
        paused_logged = False
        while True:
            if not await is_worker_enabled(redis):
                if not paused_logged:
                    logger.info("Worker paused by admin")
                    paused_logged = True
                await asyncio.sleep(5)
                continue
            if paused_logged:
                logger.info("Worker resumed by admin")
                paused_logged = False

            logger.info("Starting new polling cycle")
            async with sessionmaker() as session:
                result = await session.execute(select(Watchlist))
                watches = result.scalars().all()
                logger.info("Found watches to process", count=len(watches))

                for watch in watches:
                    if not await is_worker_enabled(redis):
                        logger.info("Worker stop requested before processing remaining watches")
                        break
                    # Capture primitives before potential lazy loads to avoid MissingGreenlet
                    watch_id = watch.id
                    watch_name = watch.market_hash_name
                    watch_appid = watch.appid
                    try:
                        logger.info(
                            "Processing watch",
                            watch_id=watch_id,
                            market_hash_name=watch_name,
                            appid=watch_appid,
                        )
                        await process_watch(session, steam, inspector, telegram, redis, watch)
                        await session.commit()
                        logger.info("Successfully processed watch", watch_id=watch_id)
                    except Exception as exc:  # pylint: disable=broad-except
                        await session.rollback()
                        logger.exception("watch processing failed", watch_id=watch_id, exc_info=exc)
                    await asyncio.sleep(
                        random.uniform(
                            settings.poll_interval_s * 0.2, settings.poll_interval_s * 0.4
                        )
                    )

            if not await is_worker_enabled(redis):
                logger.info("Worker stop request detected after cycle completion")
                continue

            logger.info("Completed polling cycle, sleeping", sleep_duration=settings.poll_interval_s)
            await asyncio.sleep(settings.poll_interval_s + random.uniform(-2, 2))
    finally:
        logger.info("🛑 Shutting down worker, closing connections")
        await steam.close()
        await inspector.close()
        await telegram.close()
        await redis.aclose()
        logger.info("Worker shutdown complete")


async def _bootstrap() -> None:
    logger.info("🚀 Starting CS2 Market Watcher Worker")
    await init_models()
    logger.info("Database models initialized, starting worker loop")
    await worker_loop()


def main() -> None:
    asyncio.run(_bootstrap())


if __name__ == "__main__":
    main()
