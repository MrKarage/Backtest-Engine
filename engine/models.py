from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict
from enum import Enum
import uuid

class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    MARKET = "market"

class Candle(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float

class Order(BaseModel):
    time: int
    symbol: str
    side: Side
    type: OrderType
    lots: float
    close_position_id: Optional[str] = None
    reduce_only: bool = False

class Config(BaseModel):
    initial_balance: float = 10000.0
    account_currency: str = "USD"
    leverage: float = 100.0
    lot_size: float = 100000.0
    pip_size: float = 0.0001

    # Costs
    spread: float = 0.0  # Fixed spread in pips
    commission_per_lot: float = 0.0 # Per lot per side (charged on open and close)
    commission_per_trade: float = 0.0 # Flat fee per execution (optional, prompt mentions per lot or per trade)
    swap_long: float = 0.0 # Per lot per night
    swap_short: float = 0.0 # Per lot per night
    swap_hour: int = 17 # NY 5pm approx

class Position(BaseModel):
    id: str
    symbol: str
    side: Side
    entry_time: int
    entry_price: float
    lots: float
    swap_cost: float = 0.0
    commission_cost: float = 0.0
    spread_cost: float = 0.0

class Trade(BaseModel):
    """Represents a realized PnL event (closing or partial closing of a position)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str
    symbol: str
    side: Side # The side of the *position* that was closed (e.g. if I had a Long, this is Buy)
    entry_time: int
    entry_price: float
    exit_time: int
    exit_price: float
    lots: float
    gross_pnl: float
    commission: float
    swap: float
    spread_cost: float
    net_pnl: float

class Summary(BaseModel):
    net_profit: float
    gross_profit: float
    gross_loss: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_percent: float
    total_trades: int
    avg_trade: float
    avg_win: float
    avg_loss: float

class EquityPoint(BaseModel):
    time: int
    balance: float
    equity: float
    drawdown: float
    drawdown_percent: float

class BacktestResult(BaseModel):
    backtest_id: str
    summary: Summary
    equity_curve: List[EquityPoint]
    trades: List[Trade] # The ledger of closed trades
    open_positions: List[Position] # Remaining open positions

class DatasetMetadata(BaseModel):
    id: str
    filename: str
    count: int
    symbol: str
