# Bug: XGBoost Sparse Data pct_change() Teleportation

**Date:** 2026-03-21  
**Severity:** Critical  
**Impact:** XGBoost strategy showed 2,500%+ returns instead of ~87%  
**Status:** FIXED

## Root Cause

The XGBoost strategy SQL query filtered `WHERE p.target_weight > 0`, creating a
*sparse* DataFrame that only contained days where a stock was actively held.

When `pct_change()` was computed on this sparse data, it calculated the return
between adjacent rows — which could span **months** if the model dropped and
re-selected a stock. A stock bought at $100 in January and re-selected at $150
in June would show a +50% "daily" return.

## Example

```
# Sparse DataFrame (filtered to target_weight > 0 only)
ticker  date        adj_close
AAPL    2024-01-15  185.00
AAPL    2024-06-10  215.00    ← pct_change() = +16.2% in "1 day"
```

That 16.2% return (actually 5 months of gain) was captured in a single trading day.

## Fix

Load continuous price timelines from `daily_bars` FIRST, compute `pct_change()` on
the contiguous series, THEN merge `target_portfolio` weights onto it:

```python
# CORRECT: continuous prices → pct_change → merge weights
prices = pd.read_sql("SELECT ticker, date, adj_close FROM daily_bars ...", conn)
prices["daily_return"] = prices.groupby("ticker")["adj_close"].pct_change()
df = pd.merge(prices, weights, on=["ticker", "date"], how="left")
df["target_weight"] = df["target_weight"].fillna(0)
```

## Before/After

| Metric | Before (Bug) | After (Fixed) |
|--------|-------------|---------------|
| Total Return | +2,500% | +87% |
| CAGR | 247% | 13.4% |
| Sharpe | 2.87 | 0.80 |
| Max DD | — | -22.8% |

## Lesson

**Never filter rows before computing `pct_change()`.** Always compute returns on
contiguous daily data, then join signals/weights afterward.
