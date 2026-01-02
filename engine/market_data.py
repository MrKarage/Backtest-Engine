import pandas as pd
import io
import uuid
from typing import List, Dict
from .models import Candle, DatasetMetadata

class MarketDataStore:
    def __init__(self):
        self.datasets: Dict[str, List[Candle]] = {}
        self.metadata: Dict[str, DatasetMetadata] = {}

    def upload_data(self, content: bytes, filename: str) -> str:
        dataset_id = str(uuid.uuid4())

        # Simple heuristic to detect format
        try:
            # Try JSON first if it looks like it
            if filename.endswith('.json'):
                df = pd.read_json(io.BytesIO(content))
            else:
                df = pd.read_csv(io.BytesIO(content))
        except Exception as e:
            # If failed, try the other one
            try:
                df = pd.read_json(io.BytesIO(content))
            except:
                raise ValueError(f"Could not parse file: {e}")

        # Normalize columns
        df.columns = df.columns.str.lower()

        required_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
             raise ValueError(f"Missing columns: {missing}. Required: {required_cols}")

        # Sort by time
        df = df.sort_values('time').reset_index(drop=True)

        # Validate monotonic
        if not df['time'].is_monotonic_increasing:
             raise ValueError("Time is not monotonic increasing")

        candles = [
            Candle(
                time=int(r['time']),
                open=float(r['open']),
                high=float(r['high']),
                low=float(r['low']),
                close=float(r['close']),
                volume=float(r['volume'])
            ) for _, r in df.iterrows()
        ]

        self.datasets[dataset_id] = candles
        self.metadata[dataset_id] = DatasetMetadata(
            id=dataset_id,
            filename=filename,
            count=len(candles),
            symbol="UNKNOWN"
        )

        return dataset_id

    def get_candles(self, dataset_id: str) -> List[Candle]:
        return self.datasets.get(dataset_id, [])

# Global instance
data_store = MarketDataStore()
