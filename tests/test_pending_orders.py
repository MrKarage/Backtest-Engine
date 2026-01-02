import pytest
from engine.models import Order, Config, Side, OrderType, Candle
from engine.backtest import BacktestEngine

def test_buy_limit_fill():
    # Buy Limit at 1.0500.
    # Candle 1: Open 1.0600, Low 1.0550 (No fill)
    # Candle 2: Open 1.0550, Low 1.0490 (Fill at 1.0500)

    candles = [
        Candle(time=1000, open=1.0600, high=1.0650, low=1.0550, close=1.0600, volume=100),
        Candle(time=2000, open=1.0550, high=1.0550, low=1.0490, close=1.0500, volume=100)
    ]

    order = Order(
        time=1000,
        symbol="EURUSD",
        side=Side.BUY,
        type=OrderType.LIMIT,
        lots=1.0,
        price=1.0500
    )

    config = Config(initial_balance=10000.0, spread=0.0) # Zero spread for clarity

    be = BacktestEngine(candles, config)
    result = be.run([order])

    assert len(result.open_positions) == 1
    pos = result.open_positions[0]
    # Should fill at Limit Price
    assert pos.entry_price == 1.0500
    assert pos.entry_time == 2000

def test_buy_limit_gap_fill():
    # Buy Limit at 1.0500.
    # Candle: Open 1.0400 (Gap down). High 1.0450.
    # Should fill at Open (Better price)

    candles = [
        Candle(time=1000, open=1.0400, high=1.0450, low=1.0300, close=1.0350, volume=100)
    ]

    order = Order(
        time=1000,
        symbol="EURUSD",
        side=Side.BUY,
        type=OrderType.LIMIT,
        lots=1.0,
        price=1.0500
    )

    config = Config(initial_balance=10000.0, spread=0.0)
    be = BacktestEngine(candles, config)
    result = be.run([order])

    assert len(result.open_positions) == 1
    pos = result.open_positions[0]
    # Filled at Open because Open < Limit
    assert pos.entry_price == 1.0400

def test_sell_limit_fill():
    # Sell Limit at 1.0600
    # Candle 1: High 1.0550 (No fill)
    # Candle 2: High 1.0650 (Fill at 1.0600)

    candles = [
        Candle(time=1000, open=1.0500, high=1.0550, low=1.0500, close=1.0500, volume=100),
        Candle(time=2000, open=1.0500, high=1.0650, low=1.0500, close=1.0600, volume=100)
    ]

    order = Order(
        time=1000,
        symbol="EURUSD",
        side=Side.SELL,
        type=OrderType.LIMIT,
        lots=1.0,
        price=1.0600
    )

    config = Config(initial_balance=10000.0, spread=0.0)
    be = BacktestEngine(candles, config)
    result = be.run([order])

    assert len(result.open_positions) == 1
    pos = result.open_positions[0]
    assert pos.entry_price == 1.0600
    assert pos.entry_time == 2000

def test_buy_stop_fill():
    # Buy Stop at 1.0600 (Breakout)
    # Candle 1: High 1.0550
    # Candle 2: High 1.0650 (Triggered)

    candles = [
        Candle(time=1000, open=1.0500, high=1.0550, low=1.0500, close=1.0500, volume=100),
        Candle(time=2000, open=1.0500, high=1.0650, low=1.0500, close=1.0600, volume=100)
    ]

    order = Order(
        time=1000,
        symbol="EURUSD",
        side=Side.BUY,
        type=OrderType.STOP,
        lots=1.0,
        price=1.0600
    )

    config = Config(initial_balance=10000.0, spread=0.0)
    be = BacktestEngine(candles, config)
    result = be.run([order])

    assert len(result.open_positions) == 1
    pos = result.open_positions[0]
    # Stop becomes Market order at Price (slippage not modeled yet, so fills at Price)
    # But checking gap logic: Open (1.05) < Price (1.06). So gap didn't happen.
    # Price touched 1.06 during candle. Fill at 1.06.
    assert pos.entry_price == 1.0600

def test_buy_stop_gap_fill():
    # Buy Stop at 1.0600
    # Candle: Open 1.0700 (Gap up).
    # Fill at Open (Worse price)

    candles = [
        Candle(time=1000, open=1.0700, high=1.0800, low=1.0700, close=1.0800, volume=100)
    ]

    order = Order(
        time=1000,
        symbol="EURUSD",
        side=Side.BUY,
        type=OrderType.STOP,
        lots=1.0,
        price=1.0600
    )

    config = Config(initial_balance=10000.0, spread=0.0)
    be = BacktestEngine(candles, config)
    result = be.run([order])

    assert len(result.open_positions) == 1
    pos = result.open_positions[0]
    assert pos.entry_price == 1.0700
