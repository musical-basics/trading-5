# Level 4 Tactical Execution: The Component Diff

## 1. Pure ECS Execution
In ECS, Execution is just a diff between two states.
* State A: `PortfolioStateComponent` (Current real-world holdings, pulled via SQLite mock).
* State B: `TargetPortfolioComponent` (Target weights outputted by the Risk System).

## 2. Vectorized Squeeze Filter
The Widowmaker defense (killing short trades when VIX > 30) is executed via Polars `pl.when().then().otherwise()` array masking BEFORE the diff is calculated.
```python
safe_orders = target_df.with_columns(
    pl.when((pl.col("target_weight") < 0) & (pl.col("vix") > 30))
    .then(0.0) # Kill trade
    .otherwise(pl.col("target_weight"))
    .alias("target_weight")
)
```

## 3. Fast API Handoff
Once the final `safe_orders` DataFrame is computed, it is dumped to DuckDB/SQLite. The FastAPI layer provides an endpoint `GET /api/v1/execution/pending` which serves the JSON to the Next.js UI in ~5 milliseconds. When the user clicks "Execute" in the UI, it sends a POST request to lock the trades into the ledger.
