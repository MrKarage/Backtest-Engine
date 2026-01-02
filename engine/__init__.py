from .market_data import data_store
from .backtest import BacktestEngine
from .models import Order, Config, BacktestResult

def run_backtest(dataset_id: str, orders: list[Order], config: Config) -> BacktestResult:
    candles = data_store.get_candles(dataset_id)
    if not candles:
        raise ValueError("Dataset not found or empty")

    engine = BacktestEngine(candles, config)
    return engine.run(orders)
