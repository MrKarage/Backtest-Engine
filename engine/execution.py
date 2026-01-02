from typing import List, Tuple, Optional
from .models import Order, Candle, Config, Position, Side, Trade, OrderType
from .accounting import calculate_commission, calculate_pnl, calculate_spread_cost
import uuid

class ExecutionEngine:
    def __init__(self, config: Config):
        self.config = config

    def execute_order(self, order: Order, candle: Candle, positions: List[Position], price_override: Optional[float] = None) -> Tuple[List[Position], List[Trade], float]:
        """
        Executes an order against the current candle.
        Returns:
            updated_positions: List of positions after execution
            trades: List of realized trades (if any closed)
            cost: Total immediate cost (commission) incurred (exit commission is incurred now)
        """
        # 1. Determine Execution Price
        # Default: Market Order at Open, unless price_override is provided
        base_price = price_override if price_override is not None else candle.open
        half_spread = (self.config.spread * self.config.pip_size) / 2.0

        if order.side == Side.BUY:
            price = base_price + half_spread
        else:
            price = base_price - half_spread

        # 2. Calc Commission (for this transaction)
        # Commission is charged on Open and Close.
        commission = calculate_commission(order.lots, self.config)

        # 3. Calc Spread Cost (Entry) - only for New Position.
        # For Closing, spread cost is realized implicitly in price, but we want to report the TOTAL spread cost for the trade.
        # We store spread cost incurred on Entry in the Position.
        # On Close, we add the spread cost incurred on Exit (if we track it per side) or just total spread.
        # The prompt says "buy fills at price + spread/2, sell fills at price - spread/2".
        # So spread cost is paid half on entry, half on exit.
        # Total Spread Cost for the Round Trip = Spread * Lots * LotSize.
        # We can calculate the portion for this transaction.
        spread_cost_this_exec = calculate_spread_cost(order.lots, self.config.spread, self.config.pip_size, self.config.lot_size) / 2.0

        # 4. Handle Closing
        if order.close_position_id:
            # Targeted Close
            target_pos = next((p for p in positions if p.id == order.close_position_id), None)
            if not target_pos:
                # Position not found
                return positions, [], 0.0

            # Closing order must be opposite side?
            # Typically yes. If I have Long, I Sell to close.
            # If strategy sends explicit Close instruction, we assume it's correct side or force it.
            # But the Order model has 'side'.
            # If I have a Buy position, I need a Sell order to close it.
            if target_pos.side == order.side:
                # Invalid: trying to close a Buy with a Buy order?
                # Maybe adding to position? But 'close_position_id' implies closing.
                # I will ignore this for now or raise error.
                # Let's assume strategy is smart. If not, we skip.
                return positions, [], 0.0

            return self._close_position(target_pos, order, price, commission, spread_cost_this_exec, positions, candle.time)

        elif order.reduce_only:
            # FIFO Close opposite positions
            opp_side = Side.SELL if order.side == Side.BUY else Side.BUY
            opp_positions = [p for p in positions if p.side == opp_side and p.symbol == order.symbol]
            opp_positions.sort(key=lambda p: p.entry_time) # FIFO

            remaining_lots = order.lots
            new_positions = list(positions)
            trades = []
            total_comm_charged = 0.0

            # We consume the commission 'commission' (calculated on total order lots) as we close positions.
            # Actually, calculate_commission is linear.

            for pos in opp_positions:
                if remaining_lots < 0.000001: # Epsilon
                    break

                # How much to close?
                close_lots = min(remaining_lots, pos.lots)

                # Commission for this portion
                part_comm = calculate_commission(close_lots, self.config)
                total_comm_charged += part_comm

                # Spread cost for this portion (closing part)
                part_spread_cost = calculate_spread_cost(close_lots, self.config.spread, self.config.pip_size, self.config.lot_size) / 2.0

                # Create partial order wrapper
                part_order = order.model_copy(update={'lots': close_lots})

                updated_pos_list, new_trades, _ = self._close_position(pos, part_order, price, part_comm, part_spread_cost, new_positions, candle.time)

                new_positions = updated_pos_list
                trades.extend(new_trades)
                remaining_lots -= close_lots

            # If reduce_only, we do NOT open new position with remainder.
            return new_positions, trades, total_comm_charged

        else:
            # Open New Position
            new_pos = Position(
                id=str(uuid.uuid4()),
                symbol=order.symbol,
                side=order.side,
                entry_time=candle.time,
                entry_price=price,
                lots=order.lots,
                commission_cost=commission,
                swap_cost=0.0,
                spread_cost=spread_cost_this_exec # Store entry spread cost
            )
            return positions + [new_pos], [], commission

    def _close_position(self, pos: Position, order: Order, price: float, commission: float, spread_cost_exit: float, all_positions: List[Position], fill_time: int) -> Tuple[List[Position], List[Trade], float]:
        # Closes `pos` with `order` at `price`.
        # `commission` is the cost incurred for this closing transaction.
        # `spread_cost_exit` is the spread cost incurred for this closing transaction (half spread).

        if order.lots >= pos.lots - 0.000001:
            # Full Close
            pnl = calculate_pnl(pos.entry_price, price, pos.side, pos.lots, self.config.lot_size)
            trade = Trade(
                position_id=pos.id,
                symbol=pos.symbol,
                side=pos.side,
                entry_time=pos.entry_time,
                entry_price=pos.entry_price,
                exit_time=fill_time,
                exit_price=price,
                lots=pos.lots,
                gross_pnl=pnl,
                commission=pos.commission_cost + commission, # Total comm (entry + exit)
                swap=pos.swap_cost,
                spread_cost=pos.spread_cost + spread_cost_exit, # Total spread (entry + exit)
                net_pnl=pnl - (pos.commission_cost + commission) + pos.swap_cost # Net PnL (already accounts for spread via price execution, so we don't deduct spread_cost again from PnL, we just report it)
            )
            new_list = [p for p in all_positions if p.id != pos.id]
            return new_list, [trade], 0.0

        else:
            # Partial Close
            close_lots = order.lots
            remain_lots = pos.lots - close_lots

            # Pro-rate costs
            entry_comm_part = pos.commission_cost * (close_lots / pos.lots)
            remain_comm = pos.commission_cost - entry_comm_part

            entry_spread_part = pos.spread_cost * (close_lots / pos.lots)
            remain_spread = pos.spread_cost - entry_spread_part

            swap_part = pos.swap_cost * (close_lots / pos.lots)
            remain_swap = pos.swap_cost - swap_part

            pnl = calculate_pnl(pos.entry_price, price, pos.side, close_lots, self.config.lot_size)

            trade = Trade(
                position_id=pos.id,
                symbol=pos.symbol,
                side=pos.side,
                entry_time=pos.entry_time,
                entry_price=pos.entry_price,
                exit_time=fill_time,
                exit_price=price,
                lots=close_lots,
                gross_pnl=pnl,
                commission=entry_comm_part + commission,
                swap=swap_part,
                spread_cost=entry_spread_part + spread_cost_exit,
                net_pnl=pnl - (entry_comm_part + commission) + swap_part
            )

            updated_pos = pos.model_copy(update={
                'lots': remain_lots,
                'commission_cost': remain_comm,
                'swap_cost': remain_swap,
                'spread_cost': remain_spread
            })

            new_list = [p if p.id != pos.id else updated_pos for p in all_positions]
            return new_list, [trade], 0.0
