from typing import List, Optional
import pandas as pd
from datetime import datetime, timedelta, timezone
from .models import Candle, Order, Config, Position, Trade, BacktestResult, Summary, EquityPoint, Side, OrderType
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
        self.pending_orders: List[Order] = [] # Limit/Stop orders waiting to trigger
        self.trades: List[Trade] = []
        self.equity_curve: List[EquityPoint] = []
        self.current_balance = config.initial_balance
        self.current_equity = config.initial_balance
        self.max_equity = config.initial_balance
        self.max_drawdown = 0.0
        self.max_drawdown_percent = 0.0

    def run(self, orders: List[Order]) -> BacktestResult:
        return self._run_loop(orders)

    def run_strategy(self, strategy) -> BacktestResult:
        return self._run_strategy_loop(strategy)

    def _run_strategy_loop(self, strategy):
        strategy.on_start(self.config)
        last_swap_date = datetime.fromtimestamp(self.candles[0].time, tz=timezone.utc).date()

        for i, candle in enumerate(self.candles):
            current_dt = datetime.fromtimestamp(candle.time, tz=timezone.utc)

            # 1. Swap
            if current_dt.date() > last_swap_date:
                nights = (current_dt.date() - last_swap_date).days
                for pos in self.positions:
                    sw = calculate_swap(pos.lots, pos.side, nights, self.config)
                    pos.swap_cost += sw
                last_swap_date = current_dt.date()

            # 2. Ask Strategy for Orders
            new_orders = strategy.on_candle(candle, self.positions, self.pending_orders)

            # Process New Orders
            for order in new_orders:
                # Ensure order time is set to candle time if not provided (though Order requires time)
                # We assume Strategy sets it correctly, or we can enforce it:
                # order.time = candle.time

                if order.type == OrderType.MARKET:
                    self._execute_order(order, candle)
                elif order.type in (OrderType.LIMIT, OrderType.STOP):
                    self.pending_orders.append(order)

            # 3. Check Pending Orders
            triggered_orders = []
            remaining_orders = []

            for order in self.pending_orders:
                is_triggered, fill_price = self._check_trigger(order, candle)
                if is_triggered:
                    self._execute_order(order, candle, fill_price)
                else:
                    remaining_orders.append(order)

            self.pending_orders = remaining_orders

            # 4. Update Equity
            floating_pnl = 0.0
            floating_swap = 0.0
            for pos in self.positions:
                if pos.side == Side.BUY:
                    pnl = (candle.close - pos.entry_price) * pos.lots * self.config.lot_size
                else:
                    pnl = (pos.entry_price - candle.close) * pos.lots * self.config.lot_size
                floating_pnl += pnl
                floating_swap += pos.swap_cost

            self.current_equity = self.current_balance + floating_pnl + floating_swap

            # 5. Record History
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
        return self._finalize_result()

    def _finalize_result(self) -> BacktestResult:
        gross_profit = sum(t.gross_pnl for t in self.trades if t.gross_pnl > 0)
        gross_loss = sum(t.gross_pnl for t in self.trades if t.gross_pnl <= 0)
        net_profit = self.current_equity - self.config.initial_balance

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

            # 2. Process New Incoming Orders
            while order_idx < len(orders) and orders[order_idx].time <= candle.time:
                order = orders[order_idx]
                order_idx += 1

                if order.type == OrderType.MARKET:
                    # Execute Market immediately
                    self._execute_order(order, candle)
                elif order.type in (OrderType.LIMIT, OrderType.STOP):
                    # Add to Pending
                    self.pending_orders.append(order)

            # 3. Check Pending Orders
            triggered_orders = []
            remaining_orders = []

            for order in self.pending_orders:
                is_triggered, fill_price = self._check_trigger(order, candle)
                if is_triggered:
                    # Execute triggered order
                    self._execute_order(order, candle, fill_price)
                else:
                    remaining_orders.append(order)

            self.pending_orders = remaining_orders

            # 4. Update Equity
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

            # 5. Record History
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

        # End of Loop
        return self._finalize_result()

    def _check_trigger(self, order: Order, candle: Candle) -> tuple[bool, float]:
        """Checks if a pending order is triggered by the candle. Returns (is_triggered, fill_price)."""
        target_price = order.price
        if target_price is None:
            # Should not happen for Limit/Stop
            return False, 0.0

        if order.type == OrderType.LIMIT:
            if order.side == Side.BUY:
                # Buy Limit: Fill if Low <= Price
                # If Open < Price, we gap down below limit -> Fill at Open (better price)
                # Else if Low <= Price, fill at Price
                if candle.open < target_price:
                    return True, candle.open
                elif candle.low <= target_price:
                    return True, target_price
            else:
                # Sell Limit: Fill if High >= Price
                # If Open > Price, gap up -> Fill at Open (better)
                # Else if High >= Price, fill at Price
                if candle.open > target_price:
                    return True, candle.open
                elif candle.high >= target_price:
                    return True, target_price

        elif order.type == OrderType.STOP:
            if order.side == Side.BUY:
                # Buy Stop: Fill if High >= Price
                # If Open > Price, gap up -> Fill at Open (worse)
                # Else if High >= Price, fill at Price
                if candle.open > target_price:
                    return True, candle.open
                elif candle.high >= target_price:
                    return True, target_price
            else:
                # Sell Stop: Fill if Low <= Price
                # If Open < Price, gap down -> Fill at Open (worse)
                # Else if Low <= Price, fill at Price
                if candle.open < target_price:
                    return True, candle.open
                elif candle.low <= target_price:
                    return True, target_price

        return False, 0.0

    def _execute_order(self, order: Order, candle: Candle, price: Optional[float] = None):
        new_positions, new_trades, cost = self.execution.execute_order(order, candle, self.positions, price_override=price)

        # Deduct cost from Balance immediately
        self.current_balance -= cost

        # Handle Closed Trades
        for trade in new_trades:
            self.current_balance += trade.gross_pnl
            self.current_balance += trade.swap
            # Comm already deducted on open and close

        self.positions = new_positions
        self.trades.extend(new_trades)
