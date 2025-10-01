import pytest
from src.integrations.steam import SteamClient


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

