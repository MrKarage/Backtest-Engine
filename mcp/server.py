from mcp.server.fastapi import FastAPIServer
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
import mcp.types as types
from engine.market_data import data_store
from engine.backtest import BacktestEngine
from engine.models import Config, Order
import json
import uuid
import base64

# Since we are integrating with FastAPI, we can expose MCP tools via a sub-app or just standalone server.
# However, the prompt asks for "MCP server tools that wrap the same engine functions".
# And "REST API server runnable locally" AND "MCP server runnable locally".
# I'll create a standalone MCP server script using `mcp` library (assuming standard python SDK).
# Wait, standard `mcp` library usage:
# Usually `mcp` is for Model Context Protocol.
# I'll implement a simple MCP server using `mcp` package.

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

# But I need to define tools.
# Let's create `mcp/server.py`.

# Re-checking imports. The `mcp` package installed might be different.
# I'll assume `mcp` package provides the server.

import asyncio
from mcp.server.models import InitializationOptions
import mcp.server.stdio
from mcp.server import Server
from mcp.types import Tool, TextContent, CallToolRequest, CallToolResult

# Engine imports
from engine.market_data import data_store
from engine import run_backtest as engine_run_backtest
from engine.models import Config, Order

app = Server("forex-backtest-engine")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="upload_market_data",
            description="Uploads market data from a file path (on server) or raw CSV string. Returns dataset_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to CSV/JSON file on local disk"},
                    "content": {"type": "string", "description": "Raw content of CSV/JSON"},
                    "filename": {"type": "string", "description": "Filename for format detection (e.g. data.csv)"}
                }
            }
        ),
        Tool(
            name="run_backtest",
            description="Runs a backtest simulation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "orders": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "time": {"type": "integer"},
                                "symbol": {"type": "string"},
                                "side": {"type": "string", "enum": ["buy", "sell"]},
                                "type": {"type": "string", "enum": ["market"]},
                                "lots": {"type": "number"},
                                "close_position_id": {"type": "string"},
                                "reduce_only": {"type": "boolean"}
                            },
                            "required": ["time", "symbol", "side", "type", "lots"]
                        }
                    },
                    "config": {
                        "type": "object",
                        "properties": {
                            "initial_balance": {"type": "number"},
                            "spread": {"type": "number"},
                            "commission_per_lot": {"type": "number"},
                            "swap_long": {"type": "number"},
                            "swap_short": {"type": "number"}
                        }
                    }
                },
                "required": ["dataset_id", "orders"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "upload_market_data":
        content = None
        filename = arguments.get("filename", "data.csv")

        if "file_path" in arguments:
            # Read local file
            try:
                with open(arguments["file_path"], "rb") as f:
                    content = f.read()
            except Exception as e:
                return [TextContent(type="text", text=f"Error reading file: {e}")]
        elif "content" in arguments:
            content = arguments["content"].encode('utf-8')
        else:
             return [TextContent(type="text", text="Either file_path or content must be provided")]

        try:
            dataset_id = data_store.upload_data(content, filename)
            return [TextContent(type="text", text=json.dumps({"dataset_id": dataset_id}))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error processing data: {e}")]

    elif name == "run_backtest":
        try:
            dataset_id = arguments["dataset_id"]
            orders_data = arguments["orders"]
            config_data = arguments.get("config", {})

            # Convert dicts to Pydantic models
            orders = [Order(**o) for o in orders_data]
            config = Config(**config_data)

            result = engine_run_backtest(dataset_id, orders, config)

            # Serialize result
            return [TextContent(type="text", text=result.model_dump_json())]
        except Exception as e:
            return [TextContent(type="text", text=f"Error running backtest: {e}")]

    raise ValueError(f"Tool {name} not found")

async def main():
    # Run stdio server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="forex-backtest",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
