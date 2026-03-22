# Level 4 Data Flow: The ECS Tick Loop

## 1. Core Philosophy: Flat Data
Systems (Functions) do not loop over tickers. They request flat arrays from DuckDB, manipulate them using Polars, and write them back. The pipeline is constructed as a Directed Acyclic Graph (DAG) before execution.

## 2. The Systems Pipeline

### System 1: Ingestion System (I/O)
* Fetches APIs. Translates tickers to `entity_id`. Writes directly to `MarketDataComponent` and `FundamentalComponent` parquet files.

### System 2: Alignment & Math Engine (Zero-Copy)
* Polars executes `pl.LazyFrame.join_asof(strategy='backward')` to perfectly align daily prices with quarterly fundamentals in Rust (microseconds). Replaces the slow Pandas merge_asof.
* Computes rolling OLS betas using `numpy.linalg.lstsq` across vectorized windows instead of slow `statsmodels` loops.

### System 3: The Modular Strategy System
* **Query:** "Give me `MarketData` + `FeatureComponent` for all active entities."
* Instead of running a python `for` loop per strategy, strategies are evaluated in parallel via Polars `.with_columns()`. Output is written to `ActionIntentComponent`.

### System 4: The Risk System (The Iterative Bouncer)
* Converts the Polars column to a flat NumPy array. Runs the matrix multiplication ($\sigma_p^2 = w^T \Sigma w$). Calculates the MCR.
* **The Iterative Fix:** Scales down breaching weights, then safely re-normalizes the cash buffer *without* pushing safe stocks back over the MCR limit. Loops until converged.
* **Crucial Audit Step:** Writes the `mcr_penalty_scalars` to `RiskAuditComponent` so the UI can X-Ray the math.

### System 5: Execution Ledger
* Diffs `TargetPortfolioComponent` against the simulated inventory state via `pl.when().then()`. Appends to the SQLite `paper_executions` table.
