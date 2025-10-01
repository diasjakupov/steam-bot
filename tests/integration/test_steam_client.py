import pytest
import respx

from src.integrations.steam import SteamClient


@pytest.mark.asyncio
async def test_fetch_listings_parses_results_html():
    client = SteamClient()
    with respx.mock(base_url="https://steamcommunity.com") as mock:
        mock.get("/market/listings/730/AK-47%20%7C%20Redline%20%28Field-Tested%29/render").respond(
            200,
            json={
                "results_html": "<div class=\"market_listing_row\" id=\"listing-1\">"
                "<a class=\"market_listing_row_link\" href=\"https://example.com\"></a>"
                "<span class=\"market_listing_price_with_fee\">$1.00</span>"
                "</div>",
            },
        )
        listings = await client.fetch_listings(730, "AK-47 | Redline (Field-Tested)")
    await client.close()
    assert len(listings) == 1
    assert listings[0].price_cents == 100

