from .models import Config, Side

def calculate_spread_cost(lots: float, spread_pips: float, pip_size: float, lot_size: float) -> float:
    """Calculates the cost of spread for a trade (entry + exit).
    Since the price is adjusted by half spread on each side, the total price difference is the full spread.
    """
    return spread_pips * pip_size * lots * lot_size

def calculate_commission(lots: float, config: Config) -> float:
    """Calculates commission for a single transaction (one side)."""
    return config.commission_per_lot * lots

def calculate_swap(lots: float, side: Side, nights: int, config: Config) -> float:
    """Calculates swap cost/credit for a position held over nights."""
    if nights <= 0:
        return 0.0
    rate = config.swap_long if side == Side.BUY else config.swap_short
    # Assuming rate is in account currency per lot per night
    return rate * lots * nights

def calculate_pnl(entry_price: float, exit_price: float, side: Side, lots: float, lot_size: float) -> float:
    """Calculates Gross PnL based on entry and exit prices."""
    if side == Side.BUY:
        return (exit_price - entry_price) * lots * lot_size
    else:
        return (entry_price - exit_price) * lots * lot_size
