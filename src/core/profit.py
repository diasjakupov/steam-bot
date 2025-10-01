from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class ProfitInputs:
    target_resale_usd: float
    min_profit_usd: float
    combined_fee_rate: float = 0.15
    combined_fee_min_cents: int = 1


def price_to_cents(price_str: str) -> int:
    # Normalize and extract a numeric value from strings like
    # "$45.50", "45.50 USD", "USD 45.50", "1,234.56", etc.
    if not price_str:
        return 0
    # Remove currency symbols/letters while preserving digits, dots, commas
    numeric_part = re.sub(r"[^0-9.,]", "", price_str)
    # Remove thousands separators
    numeric_part = numeric_part.replace(",", "")
    # Handle inputs like ".50"
    if numeric_part.startswith("."):
        numeric_part = "0" + numeric_part
    if not numeric_part or numeric_part == ".":
        return 0
    dollars = float(numeric_part)
    return int(round(dollars * 100))


def cents_to_dollars(cents: int) -> float:
    return cents / 100.0


def buyer_to_proceeds(buyer_price_cents: int, combined_fee_rate: float, fee_min_cents: int) -> int:
    gross = buyer_price_cents
    proceeds = int(round(gross / (1 + combined_fee_rate)))
    proceeds = max(0, proceeds - fee_min_cents)
    return proceeds


def max_buy_price_cents(inputs: ProfitInputs) -> int:
    resale_cents = int(round(inputs.target_resale_usd * 100))
    proceeds = buyer_to_proceeds(resale_cents, inputs.combined_fee_rate, inputs.combined_fee_min_cents)
    min_profit_cents = int(round(inputs.min_profit_usd * 100))
    return max(0, proceeds - min_profit_cents)


def is_profitable(ask_cents: int, inputs: ProfitInputs) -> bool:
    return ask_cents <= max_buy_price_cents(inputs)

