from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from bs4 import BeautifulSoup, Tag

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


def _extract_price(node: Tag) -> int:
    price_node = node.select_one("span.market_listing_price_with_fee")
    if not price_node:
        raise ParseError("price node missing")
    price_text = price_node.get_text(strip=True)
    if not price_text:
        raise ParseError("empty price text")
    return price_to_cents(price_text)


def _extract_listing_key(node: Tag) -> str:
    data_listing_id = node.get("id")
    if data_listing_id:
        return data_listing_id
    asset = node.select_one("div.market_listing_item_name_block")
    if asset and asset.get("data-paintindex"):
        return asset.get("data-paintindex")
    raise ParseError("unable to determine listing key")


def _extract_urls(node: Tag) -> tuple[Optional[str], Optional[str]]:
    link = node.select_one("a.market_listing_row_link")
    listing_url = link.get("href") if link else None
    log = logger.bind(listing_url=listing_url)
    inspect_url = None
    for anchor in node.select("div.market_listing_row_action a"):
        text = anchor.get_text(strip=True)
        if text and "inspect in game" in text.lower():
            href = anchor.get("href", "")
            if href.startswith("steam://"):
                inspect_url = href
                break
    if inspect_url is None:
        for anchor in node.select("a"):
            text = anchor.get_text(strip=True)
            if not text or "inspect in game" not in text.lower():
                continue
            href = anchor.get("href", "")
            if href.startswith("steam://"):
                inspect_url = href
                break
    if inspect_url is None:
        inspect_button = node.select_one("a.market_action_menu_item")
        if inspect_button and "steam://" in inspect_button.get("href", ""):
            inspect_url = inspect_button.get("href")
    if inspect_url is None:
        sample_anchors = []
        for anchor in node.select("a"):
            sample_anchors.append(
                {
                    "text": anchor.get_text(strip=True),
                    "href": anchor.get("href", ""),
                    "class": anchor.get("class", ""),
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
    parser = BeautifulSoup(results_html, 'lxml')
    for row in parser.select("div.market_listing_row"):
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
            raw=row.attrs,
        )
