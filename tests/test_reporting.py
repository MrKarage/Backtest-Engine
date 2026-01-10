import os
import shutil
import pytest
from datetime import datetime, timezone
from engine.reporting import ReportGenerator
from engine.models import BacktestResult, Summary, Trade, Side, Candle, Position, EquityPoint

@pytest.fixture
def mock_backtest_result():
    return BacktestResult(
        backtest_id="test_report_id",
        summary=Summary(
            net_profit=100.0,
            gross_profit=200.0,
            gross_loss=-100.0,
            win_rate=0.5,
            profit_factor=2.0,
            max_drawdown=50.0,
            max_drawdown_percent=5.0,
            total_trades=2,
            avg_trade=50.0,
            avg_win=200.0,
            avg_loss=-100.0
        ),
        equity_curve=[
            EquityPoint(time=1672531200, balance=10000, equity=10000, drawdown=0, drawdown_percent=0)
        ],
        trades=[
            Trade(
                position_id="p1",
                symbol="EURUSD",
                side=Side.BUY,
                entry_time=1672531200, # 2023-01-01 00:00
                entry_price=1.0500,
                exit_time=1672534800, # 2023-01-01 01:00
                exit_price=1.0550,
                lots=1.0,
                gross_pnl=500.0,
                commission=0.0,
                swap=0.0,
                spread_cost=0.0,
                net_pnl=500.0
            ),
            Trade(
                position_id="p2",
                symbol="EURUSD",
                side=Side.SELL,
                entry_time=1672617600, # 2023-01-02 00:00
                entry_price=1.0600,
                exit_time=1672621200, # 2023-01-02 01:00
                exit_price=1.0650,
                lots=1.0,
                gross_pnl=-500.0,
                commission=0.0,
                swap=0.0,
                spread_cost=0.0,
                net_pnl=-500.0
            )
        ],
        open_positions=[]
    )

@pytest.fixture
def mock_candles():
    # Generate some dummy candles for 2023-01-01 and 2023-01-02
    candles = []
    # Day 1: 2023-01-01 (1672531200 start)
    for i in range(10):
        t = 1672531200 + i * 3600
        candles.append(Candle(time=t, open=1.0500, high=1.0550, low=1.0450, close=1.0510, volume=100))

    # Day 2: 2023-01-02 (1672617600 start)
    for i in range(10):
        t = 1672617600 + i * 3600
        candles.append(Candle(time=t, open=1.0600, high=1.0650, low=1.0550, close=1.0590, volume=100))

    return candles

def test_generate_report(mock_backtest_result, mock_candles):
    output_dir = "test_reports/test_report_id"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    reporter = ReportGenerator(output_dir)
    paths = reporter.generate(mock_backtest_result, mock_candles)

    # Check return values
    assert paths["report_path"].endswith("report.md")
    assert len(paths["chart_paths"]) == 2 # 2 days

    # Check files exist
    assert os.path.exists(paths["report_path"])
    for p in paths["chart_paths"]:
        assert os.path.exists(p)

    # Check report content
    with open(paths["report_path"], "r") as f:
        content = f.read()
        assert "Backtest Report" in content
        assert "Net Profit" in content
        assert "EURUSD" in content

    # Cleanup
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
