from textwrap import dedent

from src.core.parsing import parse_results_html


SAMPLE_HTML = dedent(
    """
    <div class="market_listing_row" id="listing-123">
      <a class="market_listing_row_link" href="https://example.com/listing">
        <div class="market_listing_item_name_block" data-paintindex="700"></div>
        <span class="market_listing_price_with_fee">$123.45</span>
      </a>
      <a class="market_action_menu_item" href="steam://inspect/123"></a>
    </div>
    """
)


def test_parse_results_html_extracts_listing():
    listings = list(parse_results_html(SAMPLE_HTML))
    assert len(listings) == 1
    listing = listings[0]
    assert listing.listing_key == "listing-123"
    assert listing.price_cents == 12345
    assert listing.inspect_url == "steam://inspect/123"
    assert listing.listing_url == "https://example.com/listing"

