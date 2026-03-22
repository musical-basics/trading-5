# Product Requirements Document (PRD): Level 4 - The Matrix Awakening (ECS)

## 1. System Overview
Level 4 is the **Great Engine Swap**. We are transitioning the system from an Object-Oriented/Pandas paradigm into an Entity-Component-System (ECS) Data-Oriented pipeline. We are ripping out Streamlit and replacing it with a decoupled FastAPI backend and a React/Next.js frontend. The primary goals are blistering execution speed (100x faster WFO backtests), modular strategy grouping, and absolute mathematical transparency.

## 2. Core Philosophy: "Dumb Data, Smart Pipelines"
* **Data-Oriented Design (DOD):** Tickers are no longer "objects" or grouped by slow Pandas indices. They are `Entity IDs` (integers). Data is stored in contiguous columnar arrays (`Components`). Operations are strictly vectorized matrix math (`Systems`).
* **Modular Strategy Pods:** Running all 12 strategies at once is overwhelming. We introduce "Strategy Pods" (e.g., Pod A = XGBoost + Low Beta). The FastAPI backend evaluates requested strategies in parallel as distinct Polars columns, not sequential loops.
* **The Glass Box (X-Ray):** Because data flows through flat arrays, the pipeline must emit "Audit Components". We must be able to slice any row by `(date, ticker)` via the API and see the exact lineage of calculations (Raw Data → DCF Score → XGBoost Weight → Risk MCR Penalty → Final Weight).

## 3. Scope of Level 4 Features
* **Polars & DuckDB:** Complete replacement of `pandas` and `sqlite3` for the math desk and backtesting engine. (SQLite remains *only* for the execution ledger).
* **Iterative Risk APT:** A multi-pass MCR scaler that respects the 5% threshold mathematically without accidentally inflating safe stocks during cash-buffer normalization.
* **FastAPI Backend:** A dedicated REST API layer to serve calculations, backtest results, and X-Ray diagnostics asynchronously.
* **Next.js Frontend:** A professional, modular web dashboard generated via v0.dev.

## 4. Out of Scope for Level 4
* Live broker execution (Routing remains Paper/Dry-Run).
* High-Frequency intraday tick data.
