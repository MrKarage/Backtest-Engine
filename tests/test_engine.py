import pytest
from engine.models import Order, Config, Side, OrderType, Candle
from engine.execution import ExecutionEngine
from engine.accounting import calculate_pnl
from engine.backtest import BacktestEngine

def test_pnl_calculation():
    # Long: Entry 1.1000, Exit 1.1050, Lot 100k
    pnl = calculate_pnl(1.1000, 1.1050, Side.BUY, 1.0, 100000)
    assert pnl == pytest.approx(500.0) # 50 pips * $10 = $500

    # Short: Entry 1.1050, Exit 1.1000
    pnl = calculate_pnl(1.1050, 1.1000, Side.SELL, 1.0, 100000)
    assert pnl == pytest.approx(500.0)

def test_spread_application():
    config = Config(spread=2.0, pip_size=0.0001) # 2 pips spread
    # 2 pips = 0.0002. Half = 0.0001.
    engine = ExecutionEngine(config)
    candle = Candle(time=100, open=1.2000, high=1.2100, low=1.1900, close=1.2050, volume=100)

    # Buy Order
    order = Order(time=100, symbol="EURUSD", side=Side.BUY, type=OrderType.MARKET, lots=1.0)
    positions, trades, cost = engine.execute_order(order, candle, [])
    assert len(positions) == 1
    # Entry price should be Open + Half Spread = 1.2000 + 0.0001 = 1.2001
    assert positions[0].entry_price == pytest.approx(1.2001)

    # Sell Order
    order = Order(time=100, symbol="EURUSD", side=Side.SELL, type=OrderType.MARKET, lots=1.0)
    positions, trades, cost = engine.execute_order(order, candle, [])
    # Entry price should be Open - Half Spread = 1.2000 - 0.0001 = 1.1999
    assert positions[0].entry_price == pytest.approx(1.1999)

def test_commission_application():
    config = Config(commission_per_lot=5.0) # 5 per lot per side
    engine = ExecutionEngine(config)
    candle = Candle(time=100, open=1.0, high=1.0, low=1.0, close=1.0, volume=0)

    order = Order(time=100, symbol="EURUSD", side=Side.BUY, type=OrderType.MARKET, lots=2.0)
    positions, trades, cost = engine.execute_order(order, candle, [])

    # Cost should be 5.0 * 2.0 = 10.0
    assert cost == pytest.approx(10.0)
    assert positions[0].commission_cost == pytest.approx(10.0)

def test_backtest_simple_run():
    # 3 Candles
    candles = [
        Candle(time=1000, open=1.1000, high=1.1010, low=1.0990, close=1.1005, volume=100),
        Candle(time=2000, open=1.1005, high=1.1020, low=1.1000, close=1.1015, volume=100),
        Candle(time=3000, open=1.1015, high=1.1030, low=1.1010, close=1.1025, volume=100)
    ]
    config = Config(initial_balance=10000.0, spread=0.0, commission_per_lot=0.0)

    # Buy at 1000, Sell at 3000 (Executes at 3000 open?)
    # Wait, order time <= candle time.
    # Order at 1000 matches Candle 1000. Executes at Candle 1000 Open (1.1000).
    # Order at 2500 matches Candle 3000. Executes at Candle 3000 Open (1.1015).

    orders = [
        Order(time=1000, symbol="EURUSD", side=Side.BUY, type=OrderType.MARKET, lots=1.0),
        Order(time=2500, symbol="EURUSD", side=Side.SELL, type=OrderType.MARKET, lots=1.0, reduce_only=True)
    ]

    be = BacktestEngine(candles, config)
    result = be.run(orders)

    # Check trades
    assert len(result.trades) == 1
    t = result.trades[0]
    assert t.entry_price == 1.1000
    assert t.exit_price == 1.1015 # Candle 3000 Open

    # PnL = (1.1015 - 1.1000) * 100000 = 0.0015 * 100000 = 150
    assert t.gross_pnl == pytest.approx(150.0)
    assert result.summary.net_profit == pytest.approx(150.0)

def test_spread_cost_reporting():
    # Verify spread cost is reported in Trade object
    candles = [
        Candle(time=1000, open=1.0, high=1.0, low=1.0, close=1.0, volume=0),
        Candle(time=2000, open=1.0, high=1.0, low=1.0, close=1.0, volume=0)
    ]
    # Spread 2 pips. 2 * 0.0001 = 0.0002.
    # Cost per lot = 0.0002 * 100000 = 20.0
    config = Config(spread=2.0, pip_size=0.0001, commission_per_lot=0.0)

    orders = [
        Order(time=1000, symbol="EURUSD", side=Side.BUY, type=OrderType.MARKET, lots=1.0),
        Order(time=2000, symbol="EURUSD", side=Side.SELL, type=OrderType.MARKET, lots=1.0, reduce_only=True)
    ]

    be = BacktestEngine(candles, config)
    result = be.run(orders)

    assert len(result.trades) == 1
    t = result.trades[0]
    # Spread cost should be 20.0
    assert t.spread_cost == pytest.approx(20.0)

    # Net PnL calculation:
    # Entry Price (Buy): 1.0 + 0.0001 = 1.0001
    # Exit Price (Sell): 1.0 - 0.0001 = 0.9999
    # PnL = (0.9999 - 1.0001) * 100000 = -0.0002 * 100000 = -20.0
    assert t.net_pnl == pytest.approx(-20.0)

    # Check that spread cost is NOT double counted in Net PnL (Net PnL is derived from price diff which already includes spread)
    # If spread cost was deducted again: -20 - 20 = -40.
    # So assertions above confirm correctness.
