from src.core.profit import ProfitInputs, buyer_to_proceeds, is_profitable, max_buy_price_cents, price_to_cents


def test_price_to_cents_parses_dollars():
    assert price_to_cents("$1.23") == 123
    assert price_to_cents("0.99") == 99
    assert price_to_cents(".50") == 50


def test_profit_math():
    inputs = ProfitInputs(target_resale_usd=200.0, min_profit_usd=10.0, combined_fee_rate=0.15, combined_fee_min_cents=1)
    max_buy = max_buy_price_cents(inputs)
    assert max_buy > 0
    assert is_profitable(max_buy, inputs)
    assert not is_profitable(max_buy + 1, inputs)


def test_buyer_to_proceeds_respects_fee_min():
    proceeds = buyer_to_proceeds(100, combined_fee_rate=0.15, fee_min_cents=1)
    assert proceeds <= 100
    assert proceeds >= 0

