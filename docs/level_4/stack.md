# Level 4 Tech Stack & Infrastructure

## 1. System Architecture (Decoupled)
We are moving to a Client-Server architecture. The Python backend runs the ECS pipeline and exposes endpoints. The Next.js frontend acts strictly as a visualization and control layer.

## 2. The "Zero-Copy" Backend Stack
* **Language:** Python 3.11+
* **Engine:** `polars` (replacing `pandas`). Polars is written in Rust, natively multithreaded, and uses Apache Arrow for zero-copy memory transfers.
* **Database:** `duckdb`. An embedded analytical database that queries Polars DataFrames and Parquet files directly with SQL at C++ speeds.
* **API Layer:** `fastapi` + `uvicorn`.
* **Machine Learning:** `xgboost` (accepts Polars/Arrow arrays natively).
* **Math:** `numpy` (for Risk APT matrix algebra).

## 3. The Frontend Stack (For v0.dev)
* **Framework:** Next.js 14 (App Router) + React.
* **Styling:** Tailwind CSS + shadcn/ui (Radix primitives).
* **Charting:** Recharts (for equity curves) and Lightweight Charts (for financial overlays).

## 4. AI Agent Guardrails (The Polars Shift)
* **Strictly No Pandas:** Do not use `import pandas as pd`. Use `import polars as pl`. 
* **Lazy Evaluation:** Use `pl.LazyFrame` (`.scan_parquet()` or `.lazy()`) for large historical WFO datasets, executing only via `.collect()` at the end of the query plan.
* **No Iterrows:** `df.iterrows()` is fundamentally banned. All cross-sectional logic must use Polars window functions (`pl.col().over("date")`).
