"""
alpha_lab_store.py — Isolated parquet-based storage for Alpha Lab experiments.

Fully decoupled from production DuckDB, trader tables, and portfolio state.
All data lives under data/alpha_lab/ and uses its own schema.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Optional

import polars as pl

from src.config import PROJECT_ROOT

ALPHA_LAB_DIR = os.path.join(PROJECT_ROOT, "data", "alpha_lab")
EXPERIMENTS_PATH = os.path.join(ALPHA_LAB_DIR, "experiments.parquet")
EQUITY_CURVES_DIR = os.path.join(ALPHA_LAB_DIR, "equity_curves")


def _ensure_dirs():
    os.makedirs(ALPHA_LAB_DIR, exist_ok=True)
    os.makedirs(EQUITY_CURVES_DIR, exist_ok=True)


def _empty_experiments() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "experiment_id": pl.Utf8,
            "hypothesis": pl.Utf8,
            "strategy_code": pl.Utf8,
            "strategy_name": pl.Utf8,
            "model_tier": pl.Utf8,          # haiku | sonnet | opus
            "status": pl.Utf8,              # generated | backtesting | passed | failed | error
            "created_at": pl.Utf8,
            "metrics_json": pl.Utf8,        # JSON string of backtest metrics
            "cost_input_tokens": pl.Int64,
            "cost_output_tokens": pl.Int64,
            "cost_usd": pl.Float64,
            "rationale": pl.Utf8,
        }
    )


def save_experiment(
    hypothesis: str,
    strategy_code: str,
    strategy_name: str,
    model_tier: str,
    rationale: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
) -> str:
    """Create a new experiment record. Returns experiment_id."""
    _ensure_dirs()
    eid = str(uuid.uuid4())[:8]

    new_row = pl.DataFrame({
        "experiment_id": [eid],
        "hypothesis": [hypothesis],
        "strategy_code": [strategy_code],
        "strategy_name": [strategy_name],
        "model_tier": [model_tier],
        "status": ["generated"],
        "created_at": [datetime.now().isoformat()],
        "metrics_json": [None],
        "cost_input_tokens": [input_tokens],
        "cost_output_tokens": [output_tokens],
        "cost_usd": [cost_usd],
        "rationale": [rationale],
    })

    if os.path.exists(EXPERIMENTS_PATH):
        existing = pl.read_parquet(EXPERIMENTS_PATH)
        combined = pl.concat([existing, new_row], how="diagonal_relaxed")
    else:
        combined = new_row

    combined.write_parquet(EXPERIMENTS_PATH)
    return eid


def update_experiment_status(
    experiment_id: str,
    status: str,
    metrics: Optional[dict] = None,
):
    """Update status and optionally metrics for an experiment."""
    if not os.path.exists(EXPERIMENTS_PATH):
        return

    df = pl.read_parquet(EXPERIMENTS_PATH)
    mask = df["experiment_id"] == experiment_id

    updates = {"status": pl.when(mask).then(pl.lit(status)).otherwise(pl.col("status"))}

    if metrics is not None:
        metrics_str = json.dumps(metrics)
        updates["metrics_json"] = (
            pl.when(mask).then(pl.lit(metrics_str)).otherwise(pl.col("metrics_json"))
        )

    df = df.with_columns(**updates)
    df.write_parquet(EXPERIMENTS_PATH)


def list_experiments() -> list[dict]:
    """Return all experiments as a list of dicts, newest first."""
    if not os.path.exists(EXPERIMENTS_PATH):
        return []
    df = pl.read_parquet(EXPERIMENTS_PATH).sort("created_at", descending=True)
    return df.to_dicts()


def get_experiment(experiment_id: str) -> Optional[dict]:
    """Get a single experiment by ID."""
    if not os.path.exists(EXPERIMENTS_PATH):
        return None
    df = pl.read_parquet(EXPERIMENTS_PATH).filter(
        pl.col("experiment_id") == experiment_id
    )
    if df.is_empty():
        return None
    return df.to_dicts()[0]


def delete_experiment(experiment_id: str) -> bool:
    """Delete an experiment and its equity curve."""
    if not os.path.exists(EXPERIMENTS_PATH):
        return False

    df = pl.read_parquet(EXPERIMENTS_PATH)
    filtered = df.filter(pl.col("experiment_id") != experiment_id)

    if len(filtered) == len(df):
        return False  # Not found

    filtered.write_parquet(EXPERIMENTS_PATH)

    # Clean up equity curve
    ec_path = os.path.join(EQUITY_CURVES_DIR, f"{experiment_id}.parquet")
    if os.path.exists(ec_path):
        os.remove(ec_path)

    return True


def update_experiment_code(experiment_id: str, strategy_code: str):
    """Update the strategy code for an experiment (for human edits)."""
    if not os.path.exists(EXPERIMENTS_PATH):
        return
    df = pl.read_parquet(EXPERIMENTS_PATH)
    mask = df["experiment_id"] == experiment_id
    df = df.with_columns(
        strategy_code=pl.when(mask).then(pl.lit(strategy_code)).otherwise(pl.col("strategy_code")),
        status=pl.when(mask).then(pl.lit("generated")).otherwise(pl.col("status")),
    )
    df.write_parquet(EXPERIMENTS_PATH)


def save_equity_curve(experiment_id: str, equity_df: pl.DataFrame):
    """Save equity curve data for an experiment."""
    _ensure_dirs()
    path = os.path.join(EQUITY_CURVES_DIR, f"{experiment_id}.parquet")
    equity_df.write_parquet(path)


def get_equity_curve(experiment_id: str) -> Optional[pl.DataFrame]:
    """Load equity curve for an experiment."""
    path = os.path.join(EQUITY_CURVES_DIR, f"{experiment_id}.parquet")
    if not os.path.exists(path):
        return None
    return pl.read_parquet(path)
