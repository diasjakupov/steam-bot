import types

import httpx
import pytest
import respx

from urllib.parse import quote

from src.integrations.steam import BrowserLaunchError, SteamClient


@pytest.mark.asyncio
async def test_fetch_listings_parses_results_html():
    async def fake_fetcher(url: str) -> str:
        return (
            "<html><body>"
            '<div class="market_listing_row" id="listing-1">'
            '<a class="market_listing_row_link" href="https://example.com"></a>'
            '<span class="market_listing_price_with_fee">$1.00</span>'
            "</div>"
            "</body></html>"
        )

    client = SteamClient(page_fetcher=fake_fetcher)
    listings = await client.fetch_listings(730, "AK-47 | Redline (Field-Tested)")
    await client.close()
    assert len(listings) == 1
    assert listings[0].price_cents == 100


@pytest.mark.asyncio
async def test_fetch_listings_falls_back_to_render_endpoint():
    market_hash_name = "AK-47 | Redline (Field-Tested)"
    encoded_name = quote(market_hash_name, safe="")

    client = SteamClient()

    async def failing_ensure_browser(self) -> None:
        raise BrowserLaunchError("browser missing")

    client._ensure_browser = types.MethodType(  # type: ignore[method-assign]
        failing_ensure_browser, client
    )

    html = (
        "<div class=\"market_listing_row\" id=\"listing-1\">"
        "<a class=\"market_listing_row_link\" href=\"https://example.com\"></a>"
        "<span class=\"market_listing_price_with_fee\">$2.50</span>"
        "</div>"
    )

    with respx.mock(base_url="https://steamcommunity.com") as mock:
        mock.get(
            f"/market/listings/730/{encoded_name}/render",
            params={
                "start": 0,
                "count": 100,
                "currency": client.settings.steam_currency_id,
                "format": "json",
            },
        ).mock(return_value=httpx.Response(200, json={"results_html": html}))

        listings = await client.fetch_listings(730, market_hash_name)

    await client.close()
    assert len(listings) == 1
    assert listings[0].price_cents == 250

