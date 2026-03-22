"""
lab_backtester.py — Sandboxed backtester for Alpha Lab experiments.

Uses the same metrics computation as the production tournament (Sharpe, MaxDD,
CAGR, Total Return) but reads only from parquet files and writes only to the
isolated alpha_lab directory.
"""

import os
from typing import Optional

import polars as pl
import numpy as np

from src.core.duckdb_store import get_parquet_path
from src.alpha_lab.sandbox_executor import execute_strategy
from src.alpha_lab.alpha_lab_store import save_equity_curve, update_experiment_status


def _load_aligned_data() -> pl.DataFrame:
    """Load market + feature data aligned for strategy evaluation.

    Returns a DataFrame with entity_id, date, adj_close, volume, and
    all feature columns — read-only from existing parquet files.
    """
    market_path = get_parquet_path("market_data")
    feature_path = get_parquet_path("feature")

    if not os.path.exists(market_path):
        raise FileNotFoundError("market_data.parquet not found — run the pipeline first")

    market = pl.read_parquet(market_path).select([
        "entity_id", "date", "adj_close", "volume"
    ]).sort(["entity_id", "date"])

    # Join entity_map to add ticker names (enables ticker-specific strategies)
    entity_map_path = os.path.join(os.path.dirname(market_path), "entity_map.parquet")
    if os.path.exists(entity_map_path):
        emap = pl.read_parquet(entity_map_path)
        if "ticker" in emap.columns and "entity_id" in emap.columns:
            market = market.join(
                emap.select(["entity_id", "ticker"]),
                on="entity_id",
                how="left",
            )

    if os.path.exists(feature_path):
        features = pl.read_parquet(feature_path)
        # Join features onto market data
        join_cols = ["entity_id", "date"]
        market = market.join(features, on=join_cols, how="left")

    # Also try to join macro data for VIX/TNX columns
    macro_path = get_parquet_path("macro")
    if os.path.exists(macro_path):
        macro = pl.read_parquet(macro_path)
        # Macro has date-level data (not entity-level), so cross-join by date
        macro_cols = [c for c in macro.columns if c != "date"]
        if macro_cols:
            macro_select = ["date"] + macro_cols
            market = market.join(
                macro.select(macro_select),
                on="date",
                how="left",
            )

    # Also try fundamental data (uses filing_date instead of date)
    fund_path = get_parquet_path("fundamental")
    if os.path.exists(fund_path):
        fund = pl.read_parquet(fund_path)
        # Rename filing_date → date for the join
        if "filing_date" in fund.columns and "date" not in fund.columns:
            fund = fund.rename({"filing_date": "date"})
        if "date" in fund.columns and "entity_id" in fund.columns:
            # Only pick columns not already in market
            new_cols = [c for c in fund.columns if c not in market.columns]
            if new_cols:
                fund_select = ["entity_id", "date"] + new_cols
                market = market.join(
                    fund.select(fund_select),
                    on=["entity_id", "date"],
                    how="left",
                )

    return market


def _compute_metrics(equity: pl.DataFrame) -> dict:
    """Compute backtest metrics from equity curve DataFrame.

    Expects columns: date, daily_return, equity
    """
    returns = equity["daily_return"].drop_nulls().to_numpy()
    eq_vals = equity["equity"].to_numpy()

    trading_days = len(returns)

    # Sharpe
    if returns.std() > 0:
        sharpe = float(returns.mean() / returns.std() * np.sqrt(252))
    else:
        sharpe = 0.0

    # Max Drawdown
    running_max = np.maximum.accumulate(eq_vals)
    drawdown = 1 - eq_vals / running_max
    max_dd = float(drawdown.max())

    # CAGR
    if trading_days > 0 and eq_vals[0] > 0:
        total_factor = eq_vals[-1] / eq_vals[0]
        cagr = float(total_factor ** (252 / max(trading_days, 1)) - 1)
    else:
        cagr = 0.0

    # Total Return
    total_return = float(eq_vals[-1] / eq_vals[0] - 1) if eq_vals[0] > 0 else 0.0

    return {
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(max_dd, 4),
        "cagr": round(cagr, 4),
        "total_return": round(total_return, 4),
        "trading_days": trading_days,
    }


def run_lab_backtest(
    experiment_id: str,
    strategy_code: str,
    starting_capital: float = 10000.0,
) -> dict:
    """Run a full backtest for an Alpha Lab experiment.

    This is the main entry point: loads data, executes strategy in sandbox,
    computes equity curve, saves results to isolated storage.

    Returns dict with 'metrics' and 'equity_curve' keys, or 'error'.
    """
    update_experiment_status(experiment_id, "backtesting")

    try:
        # 1. Load aligned data
        data = _load_aligned_data()

        # 2. Execute strategy in sandbox
        result_df, error = execute_strategy(strategy_code, data)
        if error:
            update_experiment_status(experiment_id, "error", {"error": error})
            return {"error": error}

        # 3. Find the weight column
        weight_col = [c for c in result_df.columns if c.startswith("raw_weight_")][0]

        # 4. Normalize weights per date → dollar-neutral long-short portfolio
        #    Longs sum to +1.0, shorts sum to -1.0 (no leverage)
        result_df = (
            result_df
            .with_columns([
                # Sum of positive weights per date
                pl.col(weight_col)
                .filter(pl.col(weight_col) > 0)
                .sum()
                .over("date")
                .alias("_long_sum"),
                # Sum of abs(negative weights) per date
                pl.col(weight_col)
                .filter(pl.col(weight_col) < 0)
                .abs()
                .sum()
                .over("date")
                .alias("_short_sum"),
            ])
            .with_columns(
                pl.when(pl.col(weight_col) > 0)
                .then(pl.col(weight_col) / pl.col("_long_sum").clip(1e-8, None))
                .when(pl.col(weight_col) < 0)
                .then(-pl.col(weight_col).abs() / pl.col("_short_sum").clip(1e-8, None))
                .otherwise(0.0)
                .alias("_norm_weight")
            )
            .drop("_long_sum", "_short_sum")
        )

        # 5. Compute portfolio returns
        # For each date: portfolio return = sum(norm_weight_i * return_i)
        portfolio = (
            result_df
            .sort(["entity_id", "date"])
            .with_columns(
                (pl.col("adj_close") / pl.col("adj_close").shift(1).over("entity_id") - 1)
                .alias("_daily_ret")
            )
            .with_columns(
                (pl.col("_norm_weight").shift(1).over("entity_id") * pl.col("_daily_ret"))
                .alias("_weighted_ret")
            )
            .group_by("date")
            .agg(pl.col("_weighted_ret").sum().alias("daily_return"))
            .sort("date")
            .with_columns(
                (starting_capital * (1 + pl.col("daily_return").fill_null(0)).cum_prod())
                .alias("equity")
            )
        )

        # 5. Compute metrics
        metrics = _compute_metrics(portfolio)

        # 6. Determine pass/fail (basic threshold: Sharpe > 0)
        status = "passed" if metrics["sharpe"] > 0 else "failed"

        # 7. Save results
        save_equity_curve(experiment_id, portfolio)
        update_experiment_status(experiment_id, status, metrics)

        return {
            "metrics": metrics,
            "equity_curve": portfolio.select(["date", "daily_return", "equity"]).to_dicts(),
            "status": status,
        }

    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        update_experiment_status(experiment_id, "error", {"error": err_msg})
        return {"error": err_msg}
