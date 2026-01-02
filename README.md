# Forex Backtest Engine

A modular backtest engine for Forex trading, featuring realistic cost execution (spread, commission, swap) and reporting.

## Features

- **Data Handling**: CSV/JSON OHLCV data ingestion.
- **Execution**: Market orders with spread logic.
- **Accounting**: Detailed PnL tracking, including commission and swap/rollover.
- **Reporting**: Equity curve, trade ledger, and summary metrics.
- **API**: REST API (FastAPI) and MCP Server interface.

## Installation

```bash
pip install -r requirements.txt
```

## REST API

Run the server:

```bash
uvicorn api.main:app --reload
```

### Usage

1.  **Upload Data**

    ```bash
    curl -X POST -F "file=@examples/data.csv" http://localhost:8000/data/upload
    ```
    Response: `{"dataset_id": "uuid..."}`

2.  **Run Backtest**

    ```bash
    curl -X POST http://localhost:8000/backtest/run \
      -H "Content-Type: application/json" \
      -d '{
        "dataset_id": "uuid...",
        "orders": [
            {"time": 1767322980, "symbol": "EURUSD", "side": "buy", "type": "market", "lots": 0.10},
            {"time": 1767324000, "symbol": "EURUSD", "side": "sell", "type": "market", "lots": 0.10, "reduce_only": true}
        ],
        "config": {
            "spread": 1.0,
            "commission_per_lot": 7.0
        }
      }'
    ```

## MCP Server

Run the MCP server (stdio mode):

```bash
python mcp/server.py
```

This exposes `upload_market_data` and `run_backtest` tools to MCP clients (like Claude Desktop).

## Project Structure

- `engine/`: Core logic (Execution, Accounting, Backtest loop).
- `api/`: FastAPI implementation.
- `mcp/`: MCP Server implementation.
- `tests/`: Pytest suite.

## Testing

Run tests:

```bash
pytest tests/
```
