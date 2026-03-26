"""
stats_engine.py — Aligned Data Profile Generator

Computes statistical distributions from the JOINED aligned dataset —
the exact same data that the backtester and LLM strategies operate on.

Uses _load_aligned_data() + Polars .describe() for accurate stats that
reflect what Claude will actually see when generating strategies.

Separate from INDICATOR_METADATA (schema/semantics) in config.py.
This module provides the distribution layer (how the data behaves).
"""

import math
import json
from typing import Optional

import polars as pl

from src.alpha_lab.lab_backtester import _load_aligned_data
from src.config import INDICATOR_METADATA


# Columns to skip in stats (identifiers, not features)
_SKIP_COLS = {"entity_id", "date", "ticker", "filing_date"}


def generate_aligned_data_profile() -> dict:
    """Generate the statistical profile from the joined aligned dataset.

    This loads the exact same data the backtester uses (market + feature +
    macro + fundamental joined), so the stats reflect reality.

    Returns:
        {
            "total_rows": int,
            "features": {
                "col_name": {
                    "dtype": str,
                    "category": str,
                    "description": str,
                    "stats": { "min", "max", "mean", "median", "std_dev", "null_pct" }
                }
            }
        }
    """
    try:
        df = _load_aligned_data()
    except Exception as e:
        return {"error": f"Failed to load aligned data: {e}"}

    if df.is_empty():
        return {"error": "Aligned dataset is empty."}

    # Use Polars .describe() to get standard stats
    stats_df = df.describe()
    stats_dicts = stats_df.to_dicts()

    # Polars .describe() key column name varies by version
    stat_key_col = "statistic" if "statistic" in stats_df.columns else "describe"

    total_rows = len(df)
    features = {}

    for col in df.columns:
        if col in _SKIP_COLS:
            continue

        # Map stats for this column from .describe() output
        col_stats = {}
        for row in stats_dicts:
            stat_name = row[stat_key_col]
            val = row.get(col)
            # Clean up NaN/Inf for JSON serialization
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                col_stats[stat_name] = None
            else:
                col_stats[stat_name] = val

        null_count = float(col_stats.get("null_count", 0) or 0)

        # Get semantic metadata from config
        meta = INDICATOR_METADATA.get(col, {})
        if isinstance(meta, str):
            # Handle flat string format (backward compat)
            category = "other"
            description = meta
        elif isinstance(meta, dict):
            category = meta.get("category", "other")
            description = meta.get("description", "Engineered feature component.")
        else:
            category = "other"
            description = "Engineered feature component."

        features[col] = {
            "dtype": str(df[col].dtype),
            "category": category,
            "description": description,
            "stats": {
                "min": col_stats.get("min"),
                "max": col_stats.get("max"),
                "mean": col_stats.get("mean"),
                "median": col_stats.get("50%"),
                "std_dev": col_stats.get("std"),
                "null_pct": round((null_count / total_rows) * 100, 2) if total_rows > 0 else 0,
            },
        }

    return {"total_rows": total_rows, "features": features}


def build_profile_for_llm() -> str:
    """Build a JSON string of the profile for LLM prompt injection.

    Returns the profile as formatted JSON that Claude can parse as a
    structured data reference for calibrating thresholds.
    """
    profile = generate_aligned_data_profile()
    if "error" in profile:
        return ""

    # Build a compact version for the LLM (exclude category, keep description + stats)
    llm_profile = {}
    for col_name, col_info in profile.get("features", {}).items():
        llm_profile[col_name] = {
            "description": col_info["description"],
            "dtype": col_info["dtype"],
            **{k: v for k, v in col_info["stats"].items() if v is not None},
        }

    return json.dumps(
        {"total_rows": profile.get("total_rows", 0), "features": llm_profile},
        indent=2,
    )
