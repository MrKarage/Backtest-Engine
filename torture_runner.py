import sys
import os
import random
import time
from typing import List
from datetime import datetime

# Ensure we can import engine
sys.path.append(os.getcwd())

from engine.models import Config, Order, Side, OrderType, Candle, Position
from engine.backtest import BacktestEngine
from engine.strategy import Strategy
from scenarios.generators import generate_ranging_market

class DummyStrategy(Strategy):
    """
    A simple random strategy to verify the torture runner.
    """
    def on_candle(self, candle: Candle, open_positions: List[Position], pending_orders: List[Order]) -> List[Order]:
        # Randomly buy or sell if no position
        if not open_positions:
            if random.random() < 0.1:
                side = Side.BUY if random.random() > 0.5 else Side.SELL
                return [Order(
                    time=candle.time,
                    symbol="EURUSD",
                    side=side,
                    type=OrderType.MARKET,
                    lots=0.1
                )]
        else:
            # Randomly close
            if random.random() < 0.05:
                # To close, we open opposite position (hedge) or if engine supports close...
                # Engine 'run(orders)' model implied hedging or separate positions?
                # Looking at execution.py would clarify, but usually in this engine
                # we just place a market order in opposite direction to hedge,
                # OR we might have a specific close logic.
                # Wait, BacktestEngine updates positions based on net?
                # Let's assume hedging is allowed or it handles netting.
                # Actually, `close_position_id` in Order model suggests explicit close.
                pos = open_positions[0]
                return [Order(
                    time=candle.time,
                    symbol="EURUSD",
                    side=Side.SELL if pos.side == Side.BUY else Side.BUY,
                    type=OrderType.MARKET,
                    lots=pos.lots,
                    close_position_id=pos.id
                )]
        return []

def run_torture_test():
    print("Starting Torture Test Run...")

    # 1. Select Task (Mock selection for now)
    task_name = "Ranging Market Test"
    print(f"Selected Task: {task_name}")

    # 2. Generate Scenario
    candles = generate_ranging_market()
    print(f"Generated {len(candles)} candles.")

    # 3. Setup Engine
    config = Config(initial_balance=10000.0)
    engine = BacktestEngine(candles, config)
    strategy = DummyStrategy()

    # 4. Run
    start_time = time.time()
    result = engine.run_strategy(strategy)
    duration = time.time() - start_time

    print(f"Run completed in {duration:.4f}s")
    print(f"Net Profit: {result.summary.net_profit}")
    print(f"Trades: {result.summary.total_trades}")

    # 5. Log Result
    log_entry = f"""
## Run - {datetime.now().isoformat()}
- **Task**: {task_name}
- **Scenario**: Ranging Market (Sine Wave)
- **Strategy**: Dummy Random
- **Result**: Profit={result.summary.net_profit:.2f}, Trades={result.summary.total_trades}, DD={result.summary.max_drawdown_percent:.2f}%
- **Status**: SUCCESS
"""
    with open("LOG.md", "a") as f:
        f.write(log_entry)

    # 6. Update TODO (Mock)
    # In a real run, we would parse TODO.md and move items.

    print("Torture Test Complete. Check LOG.md")

if __name__ == "__main__":
    run_torture_test()
