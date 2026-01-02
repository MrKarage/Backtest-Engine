import pytest
from engine.models import Order, Config, Side, OrderType, Candle
from engine.backtest import BacktestEngine
from engine.accounting import calculate_swap

def test_swap_application_over_days():
    # Simulate 3 days of data
    # Day 1: 10:00 AM
    # Day 2: 10:00 AM (Rollover passed)
    # Day 3: 10:00 AM (Rollover passed)

    # Timestamps (approx)
    t1 = 1609495200 # 2021-01-01 10:00 UTC
    t2 = t1 + 86400 # 2021-01-02 10:00 UTC
    t3 = t2 + 86400 # 2021-01-03 10:00 UTC

    candles = [
        Candle(time=t1, open=1.1, high=1.2, low=1.0, close=1.1, volume=100),
        Candle(time=t2, open=1.1, high=1.2, low=1.0, close=1.1, volume=100),
        Candle(time=t3, open=1.1, high=1.2, low=1.0, close=1.1, volume=100)
    ]

    # Config: Swap Long = -10.0 per lot per night
    config = Config(
        swap_long=-10.0,
        initial_balance=10000.0
    )

    # Buy 1 lot at t1. Hold until end.
    orders = [
        Order(time=t1, symbol="EURUSD", side=Side.BUY, type=OrderType.MARKET, lots=1.0)
    ]

    be = BacktestEngine(candles, config)
    result = be.run(orders)

    # We expect swap applied twice?
    # t1 -> t2: 1 night
    # t2 -> t3: 1 night
    # Order executes at t1 (since matches candle time).
    # Loop:
    # i=0 (t1): Order filled. Position Open. Swap check: t1 > last_swap? No (last is t1 date).
    # i=1 (t2): Swap check: t2 > t1 date? Yes. Nights = 1. Apply swap (-10). last=t2.
    # i=2 (t3): Swap check: t3 > t2 date? Yes. Nights = 1. Apply swap (-10). last=t3.
    # Total Swap = -20.0

    assert len(result.open_positions) == 1
    pos = result.open_positions[0]
    assert pos.swap_cost == pytest.approx(-20.0)

    # Equity should reflect swap
    # Price didn't change (1.1 -> 1.1). PnL = 0.
    # Equity = Balance + PnL + Swap
    # Balance = 10000 (no comm).
    # Equity = 10000 + 0 - 20 = 9980.

    assert result.summary.net_profit == pytest.approx(-20.0)
