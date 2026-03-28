"""
forensic_auditor.py — Forensic AI Backtest Auditor (QuantPrime Level 5.5)

This module acts as an independent "Glass Box" AI auditing layer. It:
  1. Samples the most informative trades from a backtest ledger.
  2. Compiles a point-in-time evidence file using DuckDB (T-5 to T+5 window).
  3. Sends the evidence + strategy code to Claude to classify errors into
     three strict taxonomies and produce a structured JSON verdict.
"""

import os
import json
from typing import Optional
from datetime import timedelta, datetime

import polars as pl

from src.core.duckdb_store import get_parquet_path
from src.alpha_lab.alpha_lab_store import (
    get_trade_ledger,
    get_experiment,
    update_audit_result,
)


# ── Error taxonomy definitions (injected verbatim into LLM prompt) ──────────

TAXONOMY_DEFINITIONS = """
## Error Taxonomy

### A. STRUCTURAL (App-Level Data / Math Issues)
- Stock splits or dividends not adjusted in market data (price drops 50%+ overnight)
- Portfolio total equity ignores cash drag or miscalculates aggregate P/L
- Prices have decimal errors, zeros, or null-propagating infinities
→ Resolution: Hardcoded patch in Data Ingestion or ECS Alignment

### B. BACKTEST (Backtester-Level Physics Issues)
- Survivorship Bias: Trading a stock with 0 volume on that date (halted/bankrupt)
- Liquidity Hallucination: target_shares > daily_volume × 0.01 (position > 1% ADV)
- Frictionless Vacuum: High Sharpe achieved via micro-trades without slippage penalty
→ Resolution: Patch lab_backtester.py with liquidity gates, delisting checks, slippage

### C. STRATEGY (Alpha Lab / Strategy Code Issues)
- Lookahead Bias: Strategy uses .shift(-1) or fill_null(strategy="backward") to peek future
- Earnings Leakage: Fundamental data used on exact quarter-end date, not SEC filing_date+45d
- Hallucinated Data: Pulling columns or sources that do not exist in the data dictionary
→ Resolution: Reject strategy, update swarm_generator.py prompts, add AST guardrails

### D. NONE — all checks pass, backtest appears physically and logically sound
"""

# ── Sampling ────────────────────────────────────────────────────────────────


def _sample_trades(ledger: pl.DataFrame, n: int = 10) -> pl.DataFrame:
    """Return top N trades by forensic interest.

    Splits equally between:
      - The highest absolute PnL contributors (if pnl column exists)
      - The largest absolute weight_delta (biggest allocation changes)
    """
    half = n // 2

    # Sort by |weight_delta| for largest allocation changes
    largest_delta = (
        ledger
        .with_columns(pl.col("weight_delta").abs().alias("_abs_delta"))
        .sort("_abs_delta", descending=True)
        .head(half)
        .drop("_abs_delta")
    )

    # For the other half, prioritise SELL rows (realised positions) or highest price impact
    other_half = (
        ledger
        .filter(pl.col("action") == "SELL")
        .sort(pl.col("weight_delta").abs(), descending=True)
        .head(half)
    )
    if other_half.is_empty():
        other_half = (
            ledger
            .sort(pl.col("weight_delta").abs(), descending=True)
            .head(half)
        )

    combined = pl.concat([largest_delta, other_half]).unique(subset=["date", "entity_id"])
    return combined.sort("date")


# ── DuckDB Evidence Compiler ─────────────────────────────────────────────────


def _compile_evidence(sampled_trades: pl.DataFrame) -> list[dict]:
    """For each sampled trade (T, ticker), extract T-5 to T+5 market context."""
    market_path = get_parquet_path("market_data")
    fundamental_path = get_parquet_path("fundamental")

    try:
        market = pl.read_parquet(market_path)
    except Exception:
        market = None

    try:
        fundamental = pl.read_parquet(fundamental_path)
    except Exception:
        fundamental = None

    evidence_windows = []

    for row in sampled_trades.to_dicts():
        trade_date_raw = row.get("date")
        entity_id = row.get("entity_id")
        ticker = row.get("ticker", f"entity_{entity_id}")

        # Normalise trade_date to datetime.date
        if hasattr(trade_date_raw, "date"):
            trade_date = trade_date_raw.date()
        elif isinstance(trade_date_raw, str):
            trade_date = datetime.fromisoformat(trade_date_raw).date()
        else:
            trade_date = trade_date_raw

        window_start = trade_date - timedelta(days=10)
        window_end = trade_date + timedelta(days=10)

        # Market context: T-10 to T+10 calendar days (≈ T-5 to T+5 trading days)
        market_context = []
        if market is not None and entity_id is not None:
            mkt_cols = ["date", "adj_close", "volume"]
            available_mkt_cols = [c for c in mkt_cols if c in market.columns]
            mkt_window = (
                market
                .filter(pl.col("entity_id") == entity_id)
                .filter(pl.col("date") >= window_start)
                .filter(pl.col("date") <= window_end)
                .select(available_mkt_cols)
                .sort("date")
            )
            market_context = mkt_window.to_dicts()

        # Fundamental context: most recent row prior to trade_date
        fundamental_context = None
        if fundamental is not None and entity_id is not None:
            date_col = "filing_date" if "filing_date" in fundamental.columns else "date"
            if date_col in fundamental.columns:
                fund_prior = (
                    fundamental
                    .filter(pl.col("entity_id") == entity_id)
                    .filter(pl.col(date_col) <= trade_date)
                    .sort(date_col, descending=True)
                    .head(1)
                )
                if not fund_prior.is_empty():
                    fundamental_context = fund_prior.to_dicts()[0]

        evidence_windows.append({
            "trade": {
                "date": str(trade_date),
                "ticker": ticker,
                "entity_id": entity_id,
                "action": row.get("action"),
                "weight_delta": row.get("weight_delta"),
                "norm_weight": row.get("norm_weight"),
                "adj_close": row.get("adj_close"),
                "volume": row.get("volume"),
            },
            "market_window_T-5_to_T+5": market_context,
            "latest_fundamental_prior_to_T": fundamental_context,
        })

    return evidence_windows


# ── LLM Forensic Analysis ────────────────────────────────────────────────────

_AUDITOR_SYSTEM_PROMPT = """You are a Forensic Quantitative Auditor. You are reviewing the output of an algorithmic trading backtest.

Your job is to classify any detected anomaly into EXACTLY one of the error categories below, and produce a structured JSON verdict.

{taxonomy}

## Instructions
1. Examine the Strategy Code carefully for lookahead patterns (.shift(-1), fill_null backward, etc.).
2. Examine each Trade in the Evidence File. For each trade, cross-reference:
   - The volume on the trade date (was there actually volume?)
   - The price trajectory (any suspicious overnight jumps suggesting unadjusted splits?)
   - The fundamental filing_date (was it available before the trade date?)
3. Classify the overall backtest into one category only.
4. List ALL flagged individual trades with a short reason.
5. Output ONLY valid JSON — no markdown, no preamble.

Required output schema (JSON only, no other text):
{{
  "status": "PASS" | "FAIL" | "WARNING",
  "error_category": "STRUCTURAL" | "BACKTEST" | "STRATEGY" | "NONE",
  "confidence": <float 0.0-1.0>,
  "flagged_trades": [
    {{"ticker": "AAPL", "date": "2023-01-05", "reason": "Traded 500% of daily volume. Liquidity hallucination."}}
  ],
  "recommendation": "<1-2 sentence actionable fix targeting the correct stack layer>"
}}
"""

_AUDITOR_USER_PROMPT = """## Strategy Code Under Review

```python
{strategy_code}
```

## Sampled Trade Evidence ({num_trades} trades)

{evidence_json}

Audit this backtest. Output ONLY the JSON verdict.
"""


def run_forensic_audit(experiment_id: str) -> dict:
    """
    Master entry point for the Forensic Auditor.

    1. Loads the experiment record and trade ledger.
    2. Samples top 10 most informative trades.
    3. Compiles T-5 to T+5 evidence windows via DuckDB.
    4. Calls Claude to classify errors and produce a structured JSON verdict.
    5. Persists the verdict to Supabase / local parquet.
    6. Returns the parsed verdict dict.
    """
    # ── Fetch experiment ─────────────────────────────────────────
    exp = get_experiment(experiment_id)
    if not exp:
        return {"error": f"Experiment {experiment_id} not found"}

    strategy_code = exp.get("strategy_code", "")

    # ── Load trade ledger ─────────────────────────────────────────
    ledger = get_trade_ledger(experiment_id)
    if ledger is None or ledger.is_empty():
        return {"error": "No trade ledger found — run a full backtest first to generate it"}

    # ── Sample trades ────────────────────────────────────────────
    sampled = _sample_trades(ledger, n=10)
    num_trades = len(sampled)

    # ── Compile evidence ─────────────────────────────────────────
    evidence = _compile_evidence(sampled)
    evidence_json_str = json.dumps(evidence, indent=2, default=str)

    # ── Build prompts ─────────────────────────────────────────────
    system_prompt = _AUDITOR_SYSTEM_PROMPT.format(taxonomy=TAXONOMY_DEFINITIONS)
    user_prompt = _AUDITOR_USER_PROMPT.format(
        strategy_code=strategy_code,
        num_trades=num_trades,
        evidence_json=evidence_json_str,
    )

    # ── Call Claude ───────────────────────────────────────────────
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set in environment"}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw_text = response.content[0].text.strip()

        # Strip markdown code fences if Claude wrapped the JSON
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        verdict = json.loads(raw_text)

    except json.JSONDecodeError as e:
        return {"error": f"LLM returned non-JSON response: {e}", "raw": raw_text}
    except Exception as e:
        return {"error": f"Claude API call failed: {type(e).__name__}: {e}"}

    # ── Persist verdict ───────────────────────────────────────────
    audit_status = verdict.get("status", "WARNING")
    try:
        update_audit_result(
            experiment_id=experiment_id,
            audit_status=audit_status,
            audit_report_json=json.dumps(verdict),
        )
    except Exception as e:
        print(f"  ⚠️  Audit result persistence failed (non-critical): {e}")

    return verdict
