from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from selectolax.parser import HTMLParser

from .profit import price_to_cents

import structlog


logger = structlog.get_logger(__name__)


@dataclass
class ParsedListing:
    listing_key: str
    price_cents: int
    inspect_url: Optional[str]
    listing_url: Optional[str]
    raw: dict


class ParseError(RuntimeError):
    pass


def _extract_price(node: HTMLParser) -> int:
    price_node = node.css_first("span.market_listing_price_with_fee")
    if not price_node:
        raise ParseError("price node missing")
    price_text = price_node.text(strip=True)
    if not price_text:
        raise ParseError("empty price text")
    return price_to_cents(price_text)


def _extract_listing_key(node: HTMLParser) -> str:
    data_listing_id = node.attributes.get("id")
    if data_listing_id:
        return data_listing_id
    asset = node.css_first("div.market_listing_item_name_block")
    if asset and asset.attributes.get("data-paintindex"):
        return asset.attributes["data-paintindex"]
    raise ParseError("unable to determine listing key")


def _extract_urls(node: HTMLParser) -> tuple[Optional[str], Optional[str]]:
    link = node.css_first("a.market_listing_row_link")
    listing_url = link.attributes.get("href") if link else None
    log = logger.bind(listing_url=listing_url)
    inspect_url = None
    for anchor in node.css("div.market_listing_row_action a"):
        text = anchor.text(strip=True)
        if text and "inspect in game" in text.lower():
            href = anchor.attributes.get("href", "")
            if href.startswith("steam://"):
                inspect_url = href
                break
    if inspect_url is None:
        for anchor in node.css("a"):
            text = anchor.text(strip=True)
            if not text or "inspect in game" not in text.lower():
                continue
            href = anchor.attributes.get("href", "")
            if href.startswith("steam://"):
                inspect_url = href
                break
    if inspect_url is None:
        inspect_button = node.css_first("a.market_action_menu_item")
        if inspect_button and "steam://" in inspect_button.attributes.get("href", ""):
            inspect_url = inspect_button.attributes["href"]
    if inspect_url is None:
        sample_anchors = []
        for anchor in node.css("a"):
            sample_anchors.append(
                {
                    "text": anchor.text(strip=True),
                    "href": anchor.attributes.get("href", ""),
                    "class": anchor.attributes.get("class", ""),
                }
            )
            if len(sample_anchors) >= 5:
                break
        log.warning(
            "parsing.inspect.not_found",
            anchor_samples=sample_anchors,
        )
    return inspect_url, listing_url


def parse_results_html(results_html: str) -> Iterable[ParsedListing]:
    parser = HTMLParser(results_html)
    for row in parser.css("div.market_listing_row"):
        try:
            price_cents = _extract_price(row)
            listing_key = _extract_listing_key(row)
            inspect_url, listing_url = _extract_urls(row)
        except ParseError:
            continue
        yield ParsedListing(
            listing_key=listing_key,
            price_cents=price_cents,
            inspect_url=inspect_url,
            listing_url=listing_url,
            raw=row.attributes,
        )
