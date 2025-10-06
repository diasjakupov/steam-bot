#!/usr/bin/env python3
"""
Local test script for InspectClient using CSFloat checker website.
No database or Redis required - just tests the Playwright scraping.
"""
import asyncio
import os
import sys

# Set minimal dummy env vars before importing
os.environ.setdefault("DATABASE_URL", "postgresql://dummy:dummy@localhost/dummy")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "dummy-id")

from src.integrations.inspect import InspectClient


async def test_inspect():
    inspect_url = "steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20M664967544611895696A43429104909D12594460147621735933"

    print(f"Testing InspectClient with URL:\n{inspect_url}\n")
    print("=" * 80)

    # Create a custom client with visible browser for debugging
    from src.integrations.inspect import InspectClient as BaseClient

    class VisibleInspectClient(BaseClient):
        async def _ensure_browser(self):
            if self._browser is not None:
                return
            async with self._browser_lock:
                if self._browser is not None:
                    return
                self._playwright = await async_playwright().start()
                try:
                    self._browser = await self._playwright.chromium.launch(
                        headless=False,  # Make browser visible
                        args=["--no-sandbox", "--disable-dev-shm-usage"],
                    )
                except Exception as exc:
                    await self._cleanup_playwright()
                    raise RuntimeError("Failed to launch Playwright browser") from exc

    from playwright.async_api import async_playwright
    client = VisibleInspectClient(timeout=60.0)  # Increased timeout for local testing

    try:
        print("Starting inspection (this will open CSFloat checker in VISIBLE browser)...\n")
        result = await client.inspect(inspect_url)

        if result:
            print("✅ SUCCESS! Inspection completed.\n")
            print("Results:")
            print("-" * 80)
            print(f"Float Value:  {result.float_value}")
            print(f"Paint Seed:   {result.paint_seed}")
            print(f"Paint Index:  {result.paint_index}")
            print(f"Wear Name:    {result.wear_name}")
            print(f"Stickers:     {result.stickers}")
            print("-" * 80)
        else:
            print("❌ FAILED: No result returned from inspection")
            sys.exit(1)

    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\nClosing browser...")
        await client.close()
        print("Done!")


if __name__ == "__main__":
    print("CS2 Market Watcher - InspectClient Local Test")
    print("=" * 80)
    asyncio.run(test_inspect())
