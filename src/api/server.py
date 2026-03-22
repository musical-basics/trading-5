"""
server.py — Level 4 FastAPI Application

The central REST API server for the trading terminal.
Serves the Next.js frontend with endpoints for:
  - Strategy tournaments & backtesting
  - X-Ray diagnostic inspection
  - Risk matrix & macro regime data
  - Execution ledger management

Run with: uvicorn src.api.server:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.duckdb_store import init_store
from src.api.routers import tournament, xray, risk, execution, traders, portfolios


# ── Lifespan: initialize DuckDB on startup ───────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize the DuckDB store when the server starts."""
    conn = init_store()
    app.state.db = conn
    print("✓ DuckDB store initialized")
    yield
    conn.close()
    print("✓ DuckDB store closed")


# ── FastAPI App ──────────────────────────────────────────────
app = FastAPI(
    title="QuantPrime Level 4 API",
    description="ECS Data-Oriented Trading Pipeline API",
    version="4.0.0",
    lifespan=lifespan,
)

# ── CORS: Allow Next.js frontend ────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Include Routers ──────────────────────────────────────────
app.include_router(tournament.router)
app.include_router(xray.router)
app.include_router(risk.router)
app.include_router(execution.router)
app.include_router(traders.router)
app.include_router(portfolios.router)

from src.api.routers import indicators
app.include_router(indicators.router)

from src.api.routers import alpha_lab
app.include_router(alpha_lab.router)


# ── Health Check ─────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "version": "4.0.0",
        "engine": "polars+duckdb",
    }

