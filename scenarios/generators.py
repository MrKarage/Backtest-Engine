import math
import random
from typing import List
from engine.models import Candle

def generate_sine_wave_market(
    start_time: int,
    num_candles: int,
    base_price: float,
    amplitude: float,
    period: int,
    volatility: float
) -> List[Candle]:
    """
    Generates a sine wave market with noise.
    """
    candles = []
    current_time = start_time

    for i in range(num_candles):
        angle = (i / period) * 2 * math.pi
        trend = math.sin(angle) * amplitude

        # Random noise for OHLC
        noise = lambda: random.gauss(0, volatility)

        center = base_price + trend

        open_p = center + noise()
        close_p = center + noise()
        high_p = max(open_p, close_p) + abs(noise())
        low_p = min(open_p, close_p) - abs(noise())

        candles.append(Candle(
            time=current_time,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=1000 + int(random.gauss(0, 100))
        ))

        current_time += 60 * 60 # 1 hour candles

    return candles

def generate_ranging_market(
    start_time: int = 1600000000,
    num_candles: int = 1000,
    base_price: float = 1.1000,
    range_width: float = 0.0050, # 50 pips
    volatility: float = 0.0005 # 5 pips noise
) -> List[Candle]:
    """
    Generates a ranging market (Sine wave).
    """
    return generate_sine_wave_market(
        start_time, num_candles, base_price, range_width, 100, volatility
    )
