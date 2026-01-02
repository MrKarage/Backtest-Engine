from fastapi.testclient import TestClient
from api.main import app
import json

client = TestClient(app)

def test_api_full_flow():
    # 1. Upload Data
    csv_content = """time,open,high,low,close,volume
1609459200,1.2215,1.2218,1.2210,1.2212,100
1609459260,1.2212,1.2216,1.2209,1.2214,150
1609459320,1.2214,1.2219,1.2213,1.2217,120
1609459380,1.2217,1.2220,1.2215,1.2218,130
1609459440,1.2218,1.2222,1.2216,1.2220,110
"""
    response = client.post(
        "/data/upload",
        files={"file": ("data.csv", csv_content, "text/csv")}
    )
    assert response.status_code == 200
    dataset_id = response.json()["dataset_id"]

    # 2. Run Backtest
    payload = {
        "dataset_id": dataset_id,
        "orders": [
            {"time": 1609459200, "symbol": "EURUSD", "side": "buy", "type": "market", "lots": 1.0},
            {"time": 1609459440, "symbol": "EURUSD", "side": "sell", "type": "market", "lots": 1.0, "reduce_only": True}
        ],
        "config": {
            "initial_balance": 10000.0,
            "spread": 1.0,
            "commission_per_lot": 5.0
        }
    }

    resp = client.post("/backtest/run", json=payload)
    assert resp.status_code == 200
    result = resp.json()

    # Verify basics
    assert result["summary"]["total_trades"] == 1
    assert result["summary"]["net_profit"] != 0
    assert len(result["equity_curve"]) == 5
