from typing import List, Optional
import pandas as pd
from datetime import datetime, timedelta, timezone
from .models import Candle, Order, Config, Position, Trade, BacktestResult, Summary, EquityPoint, Side
from .execution import ExecutionEngine
from .accounting import calculate_swap
import uuid

class BacktestEngine:
    def __init__(self, candles: List[Candle], config: Config):
        self.candles = candles
        self.config = config
        self.execution = ExecutionEngine(config)

        # State
        self.positions: List[Position] = []
        self.trades: List[Trade] = []
        self.equity_curve: List[EquityPoint] = []
        self.current_balance = config.initial_balance
        self.current_equity = config.initial_balance
        self.max_equity = config.initial_balance
        self.max_drawdown = 0.0
        self.max_drawdown_percent = 0.0

    def run(self, orders: List[Order]) -> BacktestResult:
        return self._run_loop(orders)

    def _run_loop(self, orders):
        orders.sort(key=lambda o: o.time)
        order_idx = 0

        last_swap_date = datetime.fromtimestamp(self.candles[0].time, tz=timezone.utc).date()

        for i, candle in enumerate(self.candles):
            current_dt = datetime.fromtimestamp(candle.time, tz=timezone.utc)

            # 1. Swap
            # Check if we crossed the swap hour of the day.
            # Config swap_hour (e.g. 17).
            # If current_dt.hour >= 17 and last_swap_check < today_17?
            # Rollover happens at 17:00 NY.
            # Let's just use day change for simplicity if timezone is messy.
            # Prompt: "charged once per rollover event... or simply once per day boundary".
            # Let's use day boundary of the data timestamps.
            if current_dt.date() > last_swap_date:
                # Apply swap for each position held
                nights = (current_dt.date() - last_swap_date).days
                for pos in self.positions:
                    sw = calculate_swap(pos.lots, pos.side, nights, self.config)
                    # Swap is cost (negative) or credit (positive).
                    # Config swap values are usually points or currency.
                    # Prompt: "swap/rollover (overnight fee credited/debited)"
                    # I assumed calculate_swap returns the signed amount to ADD to PnL.
                    # e.g. if swap_long is -10, then we add -10.
                    pos.swap_cost += sw # Keep track of total swap on position
                    # Does it hit balance immediately?
                    # Usually swap is realized on close, OR daily.
                    # In MT4, swap is a separate column, realized on Close.
                    # Equity includes swap.
                    pass
                last_swap_date = current_dt.date()

            # 2. Process Orders
            while order_idx < len(orders) and orders[order_idx].time <= candle.time:
                order = orders[order_idx]
                order_idx += 1

                # Execute
                new_positions, new_trades, cost = self.execution.execute_order(order, candle, self.positions)

                # Cost is commission for this transaction.
                # Deduct from Balance?
                # Let's strictly follow: Balance changes only on Realized PnL events (Close).
                # But Commission is immediate.
                # Let's treat Commission as immediate deduction from Balance.
                self.current_balance -= cost

                # Handle Closed Trades
                for trade in new_trades:
                    # Trade.gross_pnl is the price diff.
                    # Balance += Gross PnL
                    self.current_balance += trade.gross_pnl
                    # Trade.swap is the swap accumulated.
                    # Balance += Swap
                    self.current_balance += trade.swap
                    # Trade.commission is total commission (Entry+Exit).
                    # We already deducted Entry comm when it opened, and Exit comm just now (in 'cost').
                    # So we don't deduct commission again.

                self.positions = new_positions
                self.trades.extend(new_trades)

            # 3. Update Equity
            # Equity = Balance + Unrealized PnL + Unrealized Swap?
            # Wait, if we deduct Swap from Balance daily, then it's realized daily?
            # Standard: Swap is unrealized until close? Or realized daily?
            # In MT4, swap shows up in 'Swap' column and affects Equity. Balance unaffected until close.
            # So let's NOT deduct swap from Balance daily. Just accumulate in Position.
            # Only deduct Commission from Balance if it's "Commission per trade".
            # Some brokers deduct comm on Open/Close from Balance.
            # Let's stick to: Balance reflects Realized.
            # Commission is Realized immediately.
            # Swap is Realized on Close.

            # Unrealized PnL
            floating_pnl = 0.0
            floating_swap = 0.0
            for pos in self.positions:
                # Valuation at Close
                if pos.side == Side.BUY:
                    pnl = (candle.close - pos.entry_price) * pos.lots * self.config.lot_size
                else:
                    pnl = (pos.entry_price - candle.close) * pos.lots * self.config.lot_size
                floating_pnl += pnl
                floating_swap += pos.swap_cost

            self.current_equity = self.current_balance + floating_pnl + floating_swap

            # 4. Record History
            self.max_equity = max(self.max_equity, self.current_equity)
            dd = self.max_equity - self.current_equity
            self.max_drawdown = max(self.max_drawdown, dd)
            dd_percent = (dd / self.max_equity) * 100 if self.max_equity > 0 else 0
            self.max_drawdown_percent = max(self.max_drawdown_percent, dd_percent)

            self.equity_curve.append(EquityPoint(
                time=candle.time,
                balance=self.current_balance,
                equity=self.current_equity,
                drawdown=dd,
                drawdown_percent=dd_percent
            ))

        # End of Loop

        # Calculate Summary
        gross_profit = sum(t.gross_pnl for t in self.trades if t.gross_pnl > 0)
        gross_loss = sum(t.gross_pnl for t in self.trades if t.gross_pnl <= 0)
        net_profit = self.current_equity - self.config.initial_balance # Based on Equity (inc open positions)?
        # Or based on Realized Balance?
        # Usually Summary includes open positions (mark to market).
        # So Net Profit = Final Equity - Initial Balance.

        wins = [t for t in self.trades if t.net_pnl > 0]
        losses = [t for t in self.trades if t.net_pnl <= 0]

        return BacktestResult(
            backtest_id=str(uuid.uuid4()),
            summary=Summary(
                net_profit=net_profit,
                gross_profit=gross_profit,
                gross_loss=gross_loss,
                win_rate=len(wins)/len(self.trades) if self.trades else 0.0,
                profit_factor=abs(gross_profit/gross_loss) if gross_loss != 0 else 0.0,
                max_drawdown=self.max_drawdown,
                max_drawdown_percent=self.max_drawdown_percent,
                total_trades=len(self.trades),
                avg_trade=sum(t.net_pnl for t in self.trades)/len(self.trades) if self.trades else 0.0,
                avg_win=sum(t.net_pnl for t in wins)/len(wins) if wins else 0.0,
                avg_loss=sum(t.net_pnl for t in losses)/len(losses) if losses else 0.0
            ),
            equity_curve=self.equity_curve,
            trades=self.trades,
            open_positions=self.positions
        )
