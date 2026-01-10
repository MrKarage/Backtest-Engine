from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from engine.models import Config, Order, BacktestResult
from engine.market_data import data_store
from engine.backtest import BacktestEngine
from engine.reporting import ReportGenerator
from engine import run_backtest
import uuid
import os
from typing import List

app = FastAPI(title="Forex Backtest Engine API", version="1.0.0")

class UploadResponse(BaseModel):
    dataset_id: str
    message: str

class BacktestRequest(BaseModel):
    dataset_id: str
    orders: List[Order]
    config: Config

@app.post("/data/upload", response_model=UploadResponse)
async def upload_data(file: UploadFile = File(...)):
    try:
        content = await file.read()
        # Pass filename to detect format
        dataset_id = data_store.upload_data(content, file.filename or "data.csv")
        return UploadResponse(dataset_id=dataset_id, message="Data uploaded successfully")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/backtest/run", response_model=BacktestResult)
async def run_backtest_endpoint(request: BacktestRequest):
    try:
        # Check dataset exists
        candles = data_store.get_candles(request.dataset_id)
        if not candles:
             raise HTTPException(status_code=404, detail="Dataset not found")

        # Run Backtest
        # Note: Depending on size, this should be async/background task.
        # For V1 sync is acceptable.

        result = run_backtest(request.dataset_id, request.orders, request.config)

        # Generate Report
        output_dir = os.path.join("reports", result.backtest_id)
        reporter = ReportGenerator(output_dir)
        report_paths = reporter.generate(result, candles)

        result.report_text_file = report_paths["report_path"]
        result.report_chart_files = report_paths["chart_paths"]

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}
