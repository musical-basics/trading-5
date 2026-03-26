"""
stats_engine.py — Aligned Data Profile Generator

Computes statistical distributions (min, max, mean, median, std, null%)
per column across all parquet data sources. Kept separate from schema
metadata (INDICATOR_METADATA) so the LLM gets:
  1. Schema + semantic descriptions (via _build_dynamic_schema)
  2. Distribution profile (via this module) as a reference block

Also powers the "Aligned Data Pipeline" UI page.
"""

import os
from typing import Optional

import polars as pl

from src.core.duckdb_store import get_parquet_path, PARQUET_DIR
from src.config import INDICATOR_METADATA


# Columns to skip in stats (identifiers, not features)
_SKIP_COLS = {"entity_id", "date", "ticker", "filing_date"}


def _compute_source_stats(source_name: str) -> Optional[dict]:
    """Compute column-level stats for a single parquet source.

    Returns dict of {col_name: {dtype, category, description, stats: {...}}}
    or None if the parquet doesn't exist.
    """
    path = get_parquet_path(source_name)
    if not os.path.exists(path):
        return None

    df = pl.read_parquet(path)
    if df.is_empty():
        return None

    total_rows = len(df)
    result = {}

    for col_name in df.columns:
        if col_name in _SKIP_COLS:
            continue

        col = df[col_name]
        dtype_str = str(col.dtype)
        meta = INDICATOR_METADATA.get(col_name, {})
        category = meta.get("category", "other")
        description = meta.get("description", f"Numerical feature ({dtype_str}).")

        # Compute stats only for numeric columns
        stats = {}
        null_count = col.null_count()
        stats["null_pct"] = round((null_count / total_rows) * 100, 2) if total_rows > 0 else 0
        stats["count"] = total_rows - null_count

        if col.dtype.is_numeric():
            numeric = col.drop_nulls().cast(pl.Float64)
            if len(numeric) > 0:
                stats["min"] = round(float(numeric.min()), 6)
                stats["max"] = round(float(numeric.max()), 6)
                stats["mean"] = round(float(numeric.mean()), 6)
                stats["median"] = round(float(numeric.median()), 6)
                stats["std"] = round(float(numeric.std()), 6) if len(numeric) > 1 else 0.0
                # Percentiles
                stats["p25"] = round(float(numeric.quantile(0.25)), 6)
                stats["p75"] = round(float(numeric.quantile(0.75)), 6)

        result[col_name] = {
            "dtype": dtype_str,
            "category": category,
            "description": description,
            "stats": stats,
        }

    return result


def generate_aligned_data_profile() -> dict:
    """Generate the full aligned data profile across all parquet sources.

    Returns:
        {
            "market_data": {col: {dtype, category, description, stats}, ...},
            "feature": {...},
            "macro": {...},
            "fundamental": {...},
            "meta": {"total_tickers": int, "sample_tickers": list}
        }
    """
    profile = {}

    for source in ["market_data", "feature", "macro", "fundamental"]:
        stats = _compute_source_stats(source)
        if stats is not None:
            profile[source] = stats

    # Add universe metadata
    entity_map_path = os.path.join(PARQUET_DIR, "entity_map.parquet")
    if os.path.exists(entity_map_path):
        emap = pl.read_parquet(entity_map_path)
        tickers = sorted(emap["ticker"].to_list()) if "ticker" in emap.columns else []
        profile["meta"] = {
            "total_tickers": len(tickers),
            "sample_tickers": tickers[:10],
        }

    return profile


def build_profile_for_llm() -> str:
    """Build a compact JSON-like text block for LLM prompt injection.

    Only includes numeric stats (min/max/mean/std) to keep tokens low.
    """
    profile = generate_aligned_data_profile()
    lines = []

    for source_name in ["market_data", "feature", "macro", "fundamental"]:
        source_data = profile.get(source_name)
        if not source_data:
            continue

        lines.append(f"[{source_name}]")
        for col_name, col_info in sorted(source_data.items()):
            stats = col_info.get("stats", {})
            if "min" in stats:
                lines.append(
                    f"  {col_name}: "
                    f"min={stats['min']}, max={stats['max']}, "
                    f"mean={stats['mean']}, std={stats['std']}, "
                    f"null={stats['null_pct']}%"
                )

    return "\n".join(lines)
