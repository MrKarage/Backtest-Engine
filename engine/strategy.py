from abc import ABC, abstractmethod
from typing import List, Any
from .models import Candle, Order, Position, Trade

class Strategy(ABC):
    """
    Abstract base class for trading strategies.
    """

    @abstractmethod
    def on_candle(self, candle: Candle, open_positions: List[Position], pending_orders: List[Order]) -> List[Order]:
        """
        Called for each new candle.

        Args:
            candle: The current candle.
            open_positions: List of currently open positions.
            pending_orders: List of currently pending orders.

        Returns:
            A list of Order objects to be placed.
        """
        pass

    def on_start(self, config: Any):
        """Called before the backtest starts."""
        pass

    def on_end(self, summary: Any):
        """Called after the backtest ends."""
        pass
