"""
execution.py — FastAPI router for the Execution Ledger.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from fastapi import APIRouter
import polars as pl

from src.config import DB_PATH
from src.core.duckdb_store import get_parquet_path, PARQUET_DIR

router = APIRouter(prefix="/api/execution", tags=["execution"])


@router.get("/pending")
async def get_pending_orders():
    """Return pending execution orders from target portfolio vs current state.

    In paper mode, "current state" is from the paper_executions ledger.
    """
    try:
        target = pl.read_parquet(get_parquet_path("target_portfolio"))
        emap = pl.read_parquet(os.path.join(PARQUET_DIR, "entity_map.parquet"))

        latest_date = target["date"].max()
        orders = (
            target.filter(
                (pl.col("date") == latest_date)
                & (pl.col("target_weight").abs() > 0.001)
            )
            .sort("target_weight", descending=True)
            .join(emap, on="entity_id", how="left")
        )

        return {
            "date": str(latest_date),
            "orders": [
                {
                    "id": i + 1,
                    "ticker": row["ticker"],
                    "action": "BUY" if row["target_weight"] > 0 else "SELL",
                    "target_weight": round(row["target_weight"] * 100, 2),
                    "mcr": round(abs(row.get("mcr", 0)) * 100, 2),
                    "status": "pending",
                }
                for i, row in enumerate(orders.to_dicts())
            ],
        }
    except Exception as e:
        return {"date": None, "orders": [], "error": str(e)}


@router.post("/route")
async def route_paper_trades():
    """Lock pending orders into the paper execution ledger (SQLite)."""
    try:
        target = pl.read_parquet(get_parquet_path("target_portfolio"))
        emap = pl.read_parquet(os.path.join(PARQUET_DIR, "entity_map.parquet"))
        market = pl.read_parquet(get_parquet_path("market_data"))

        latest_date = target["date"].max()
        orders = (
            target.filter(
                (pl.col("date") == latest_date)
                & (pl.col("target_weight").abs() > 0.001)
            )
            .join(emap, on="entity_id", how="left")
        )

        # Get latest prices for simulated execution
        latest_prices = (
            market.filter(pl.col("date") == latest_date)
            .select(["entity_id", "adj_close"])
        )
        orders = orders.join(latest_prices, on="entity_id", how="left")

        # Write to SQLite paper_executions
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        count = 0

        for row in orders.to_dicts():
            cursor.execute("""
                INSERT INTO paper_executions (ticker, action, quantity, simulated_price, strategy_id)
                VALUES (?, ?, ?, ?, ?)
            """, (
                row["ticker"],
                "BUY" if row["target_weight"] > 0 else "SELL",
                1,  # Quantity placeholder (weight-based system)
                row.get("adj_close", 0),
                row.get("strategy_id", "ecs_pipeline"),
            ))
            count += 1

        conn.commit()
        conn.close()

        return {
            "status": "routed",
            "orders_routed": count,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
