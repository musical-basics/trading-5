# Bug Record: Rebalancer Strategy Execution Crash & Silent Failures

## The Bug
When a user assigned a custom Alpha Lab generated strategy (e.g., `alphalab_fb2f54f9` / `vix_regime_value_timing`) to a portfolio and attempted to run the master clock rebalancer (or hit "Force Rebalance"), the system silently generated **zero paper executions** and logged no overt errors in the UI. 

Simultaneously, attempting to run a backtest on the strategy produced this error: 
`polars.exceptions.ColumnNotFoundError: unable to find column "filing_date"` 
and later:
`polars.exceptions.ColumnNotFoundError: unable to find column "date"`

## The Cause
There were three intertwined issues causing strategy evaluation to fail gracefully within the rebalancer, returning empty orders:

1. **Missing Fundamental Data via `_prepare_data()`**: The generic vector matrix used for both the Execution Engine's portfolio evaluation AND the Tournament evaluation did not load `fundamental.parquet`. Because `filing_date` only exists in `fundamental.parquet`, the custom strategy immediately crashed when filtering for stale SEC filings. 
2. **Backward Asof Join Confusion**: Unlike `market_data`, `feature`, and `macro` which share a common `date` column, `fundamental.parquet` is indexed by `filing_date`. Attempting to use a standard `.join("date")` on the fundamentals failed. We needed to properly snap fundamentals to the actual daily bar using `join_asof` with backward fill.
3. **Mismatched Column Output from Alpha Lab**: The dynamically executed `evaluate_single_strategy()` expected Alpha Lab strategies to define a `raw_weight_{strategy_id}` column. However, the generated script output `raw_weight_vix_regime_value_timing`. Because of the mismatch, `evaluate_single_strategy` failed to find the mapped column name and threw an internal KeyError, defaulting gracefully to zero trades rather than halting the Master Clock routing.

## Failed Fixes
- Attempting to `.join()` `fundamental.parquet` in `src/ecs/tournament_system.py` directly using `["entity_id", "date"]` failed because the `date` column does not exist on sparse fundamental records, throwing a Polars `ColumnNotFoundError`.

## The Final Solution
1. Rather than reinventing the join logic, we patched `_prepare_data()` in `tournament_system.py` to seamlessly defer to `src.ecs.alignment_system.align_fundamentals()`. This single function perfectly handles `join_asof`, aligning the sparse `filing_date` accurately backwards across all daily market rows, providing every necessary fundamental column.
2. We fixed the dynamic column matching by simply hardcoding the return column inside the generated Alpha Lab script to match the expected format: `raw_weight_{STRATEGY_ID}` (i.e., `raw_weight_alphalab_fb2f54f9`). 

*Note: After these technical crashes were resolved, the `vix_regime_value_timing` strategy still correctly outputted 0 executing shares on the specific test date (March 27, 2026), purely because its native VIX algorithmic gates tripped "risk-off". The system behaved exactly as quantifiably designed!*
