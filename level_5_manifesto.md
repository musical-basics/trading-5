# QuantPrime Architecture: The Road to Level 5 (The God Engine)

## 1. The Evolutionary Journey (Levels 1 → 4)

QuantPrime was built using a strict philosophy: **Separate Financial Engineering from Systems Engineering.** We iteratively scaled the system to isolate quantitative logic from software engineering bottlenecks.

- **Level 1 (The Walking Skeleton):**
  - *Goal:* Prove the pipes connect.
  - *Paradigm:* Procedural Python, standard Pandas, SQLite, Streamlit.
  - *Mechanics:* Fetched EOD prices via `yfinance`, calculated simple 50/200-day SMAs in a loop, simulated paper trades with fixed sizing.

- **Level 2 (The Quant Sandbox):**
  - *Goal:* Institutional cross-sectional mechanics.
  - *Paradigm:* Intermediate Pandas, `merge_asof`.
  - *Mechanics:* Introduced quarterly fundamentals. Solved **Look-Ahead Bias** by joining prices to fundamentals using the *filing date* (period_end + 45 days) via `pd.merge_asof(direction='backward')`. Shifted from time-series to cross-sectional fundamental ranking (EV/Sales Z-scores). Built a Walk-Forward Optimization (WFO) backtester with hard slippage/commission friction.

- **Level 3 (The Neurosymbolic Pod):**
  - *Goal:* Peak financial complexity (Object-Oriented/Pandas limits).
  - *Paradigm:* Heavy Pandas DataFrames, Machine Learning, `statsmodels`.
  - *Mechanics:* Introduced Arbitrage Pricing Theory (APT) via 90-day rolling OLS regressions against SPY, VIX, and 10Y Yield. Built a Dynamic DCF valuation model. Trained an **XGBoost Meta-Model** via an expanding-window, purged WFO to predict forward 20-day returns. Decoupled Alpha (XGBoost weights) from Risk (Marginal Contribution to Risk matrix scaling).
  - *The Wall:* We hit the "Pandas Wall." Rolling OLS regressions across hundreds of tickers took minutes. We found a "teleportation bug" caused by `pct_change()` on sparse DataFrames.

- **Level 4 (The Matrix Awakening):**
  - *Goal:* Infinite scale and transparency via Data-Oriented Design (DOD).
  - *Paradigm:* Entity-Component-System (ECS), Polars, DuckDB, FastAPI, Next.js.
  - *Mechanics:* The Great Engine Swap. Tickers became Integer `entity_id`s. Time-series data was flattened into contiguous `.parquet` columns (Components). Python loops were replaced by Polars SIMD vectorized expressions (Systems) running in DuckDB. The Streamlit UI was replaced by a decoupled FastAPI backend and a Next.js/React frontend.
  - *Innovations:*
    - **Iterative Risk APT:** A convergence loop that safely scales down breaching assets without dangerously inflating cash buffers.
    - **X-Ray Inspector:** The "Glass Box" that exposes the exact mathematical lineage of any ticker on any date to audit the pipeline.
    - **Alpha Lab:** An autonomous LLM agent (Anthropic Claude) that writes, compiles, and backtests novel Polars strategies in an isolated Python sandbox.

---

## 2. Current Architecture & System State (Level 4)

The system currently operates as a blazing-fast, decoupled Client-Server architecture for research and paper-trading.

### Tech Stack

- **Backend Engine:** Python 3.11+, `polars` (Rust-based multithreading), `duckdb` (Columnar analytical SQL), `numpy`, `xgboost`.
- **API Layer:** `fastapi` + `uvicorn` (REST endpoints).
- **Frontend:** Next.js 14 (App Router), React, Tailwind CSS, `shadcn/ui`, Recharts.
- **Storage:**
  - *Analytical (Time-Series):* Parquet files in `data/components/` (`market_data`, `fundamental`, `macro`, `feature`, `action_intent`, `target_portfolio`).
  - *Transactional (State):* SQLite `level3_trading.db` (`traders`, `portfolios`, `paper_executions`, `alpha_lab`).

### The ECS Pipeline Flow

1. **Ingestion (System 1):** Fetches data, casts to Polars, writes to Parquet. Calculates contiguous `daily_return` immediately to prevent sparse data bugs.
2. **Alignment & Math (System 2):** `pl.join_asof` merges fundamentals instantly. `numpy.linalg.lstsq` calculates rolling betas. EV/Sales, DCFs, and Z-scores are vectorized and written to `feature.parquet`.
3. **Strategy Registry (System 3):** 12 declarative Polars strategies evaluate the features concurrently via `.with_columns()`, outputting `action_intent.parquet`.
4. **Risk Bouncer (System 4):** Iteratively calculates Covariance and MCR, scaling down portfolio weights until variance limits are respected, outputting `target_portfolio.parquet`.
5. **Execution (System 5):** Diffs target weights against current holdings in the SQLite ledger to generate execution orders.

---

## 3. Core Design Principles (Non-Negotiable)

As we enter Level 5, the following design principles must be strictly maintained:

1. **Dumb Data, Smart Pipelines (ECS):** Tickers do not have methods. State is flat. We join columnar arrays; we do not loop over objects.
2. **Heuristics Bounding the Black Box (Neurosymbolic AI):** XGBoost never sees raw prices. It is only trained on mathematically deterministic "Score Components" (EV/Sales Z-scores, Beta to the VIX, DCF NPV Gaps).
3. **Strict Separation of Alpha and Risk:** Strategies/ML models generate *Raw Weights* (Offense). The Risk APT system scales them down based on Covariance and MCR limits (Defense). Offense and Defense never mix.
4. **Zero-Look-Ahead Bias:** `join_asof(strategy='backward')` on filing dates is sacred. During ML training, the "Embargo" (purging) step must ruthlessly delete training rows whose forward-return labels overlap with the test window.
5. **Fail-Deadly Modularity (Graceful Degradation):** If an API fails to pull a stock's data, the feature row becomes `null`. The math propagates the null, dropping the stock for that tick. The pipeline *never* crashes due to a single missing data point.

---

## 4. Level 5 Objectives: The "Everything Everywhere" God Engine

Level 5 bridges the gap between a backtesting research warehouse and an **autonomous, cloud-native, live-execution institutional trading firm.**

### Objective A: Infrastructure Migration (Docker & Postgres)

- **Database Migration:** While Parquet/DuckDB remains the absolute king for *analytical* time-series data, the *transactional* data (live account balances, live execution receipts, multi-user configurations, trader constraints, Alpha Lab history) must migrate from local SQLite to a production **PostgreSQL** database (via SQLAlchemy/Alembic) to handle concurrent asynchronous read/writes from the live execution engine and background workers.
- **Containerization:** Complete `Dockerfile` setup and `docker-compose.yml` orchestrating the FastAPI backend, Next.js frontend, Redis broker, Celery workers, and PostgreSQL database, ready for AWS ECS or GCP deployment.
- **Universe Expansion:** Scale the `EntityMap` from 50 to 3,000+ tickers (Russell 3000) utilizing Polars' out-of-core capabilities.

### Objective B: Autonomous Operations (The Master Clock)

The system currently requires a human to run `python main.py` or click a button in the UI. Level 5 must run completely autonomously.

- **Task Queue:** Introduce a scheduling and worker layer (e.g., `Celery + Redis`, `Temporal`, or `APScheduler`).
- **Daily Tick:** Automatically trigger Data Ingestion at 4:00 PM EST, run the ECS Math/Risk pipelines at 4:15 PM, and queue execution orders.
- **Continuous Learning:** A weekend cron job that automatically rolls the WFO XGBoost training window forward, retrains the model asynchronously, saves the artifact, and updates the live weights for Monday.

### Objective C: Live Broker Sync & Execution Algorithms

We are leaving "Paper Ledger" mode.

- **Live API Integration:** Connect the execution router to a live broker (Alpaca Live or Interactive Brokers).
- **State Reconciliation:** Sync the internal `PortfolioStateComponent` with the actual live broker inventory via REST/WebSockets to correct drift.
- **Order Pacing (TWAP/VWAP):** Large orders exceeding 1% of Average Daily Volume (ADV) must be sliced into smaller chunks and executed over time to minimize market impact and slippage.
- **Intraday Squeeze Defense:** If VIX spikes > 30 intraday, the Bouncer must trigger an emergency intra-day rebalance to liquidate dangerous short positions immediately, rather than waiting for EOD.

### Objective D: True Multi-Manager Execution (Net-Delta Routing)

Currently, execution evaluates portfolios individually. In Level 5, we respect the hierarchy: `Traders -> Portfolios -> Strategies`.

- **The Problem:** Portfolio A wants to BUY 100 shares of AAPL. Portfolio B wants to SELL 50 shares of AAPL.
- **Net-Delta Router:** The Execution module must aggregate all intent across all portfolios, calculate the **Net Delta** (Net Buy 50 AAPL), execute a single bulk order to the broker to save on commissions/bid-ask spread, and then internally ledger the fractional shares back to the respective sub-portfolios.

### Objective E: Real-Time Telemetry & WebSockets

- **Current:** We poll the FastAPI REST endpoints.
- **Level 5:** FastAPI pushes live execution fills, order status changes (Pending → Partial → Filled), and PnL ticks directly to the Next.js frontend via WebSockets in real-time.

---

## 5. Alpha Lab 2.0: The Autonomous Strategy Factory

The Alpha Lab successfully generated complex, market-neutral composites (like `trinity_alpha_composite`). In Level 5, we upgrade it from a manual prompt box to an automated strategy factory.

### 5.1 Self-Healing Reflection Loop

- **The Problem:** Currently, if the LLM generates Polars code with a syntax error or runtime exception, the experiment simply marks as `Failed` or `Error`.
- **The Fix:** Implement an LLM "Reflection" loop. If the sandbox executor returns a traceback, the API automatically sends the traceback back to the LLM: *"Your code failed with this error: [Traceback]. Please fix the code and return the updated function."* (Limit to 3 retries).

### 5.2 Evolutionary "Genetic" Prompting (Nightly Discovery)

- **The Feature:** A Celery background task (`@celery.task(cron='0 2 * * *')`) runs overnight.
- **The Action:** It queries the `metrics_json` of previously *passed* experiments with the highest Sharpe ratios. The system feeds the Python code of those top strategies back into the LLM with the prompt: *"Here are our best performing strategies. Mutate them by introducing a new feature, altering the window sizing, or combining their logic to reduce Max Drawdown. Generate 3 new variants."* You wake up to new, genetically evolved strategies every morning.

### 5.3 One-Click Production Promotion (The Handoff)

- **The Problem:** Good strategies generated in Alpha Lab are stuck in the sandbox parquet file. They must be manually copied to `src/ecs/strategies/` to be used in the Strategy Studio/Tournament.
- **The Fix:** Create a `POST /api/alpha-lab/{id}/promote` endpoint. This endpoint will:
  1. Extract the successful Python code from the database.
  2. Physically write it to a new file: `src/ecs/strategies/custom/generated_{id}.py`.
  3. Safely update `src/ecs/strategy_registry.py` to import and register the new strategy dynamically.
  4. Make the AI strategy instantly available for live capital allocation in the Trader Manager UI.

### 5.4 Expanded Feature Context

- **The Upgrade:** Ensure the LLM has frictionless access to *all* Level 4 data. `_load_aligned_data()` in the Alpha Lab currently provides features and market data. We will explicitly make sure `macro_factors` (`vix`, `vix3m`, `tnx`, `spy`) are fully merged and available in the sandbox namespace so the LLM can write complex cross-asset regime logic without hallucinating missing columns.

---

## 6. Directives for the AI Agent (Execution Plan)

When implementing Level 5, execute in the following strict order.

> [!CAUTION]
> **DO NOT REWRITE THE CORE ECS MATHEMATICAL LOGIC (`src/ecs/`, `src/pipeline/scoring/`).** It is highly optimized, vectorized in Polars, and mathematically verified. Your focus is strictly on **Infrastructure, Automation, and the Network Edge.**

**Execution Order:**

1. **Infrastructure First:** Write `docker-compose.yml`, `Dockerfile.api`, `Dockerfile.web`, and set up the PostgreSQL + Redis stack.
2. **Database Migration:** Use Alembic/SQLAlchemy to migrate `traders`, `portfolios`, `paper_executions`, and `alpha_lab` from SQLite to PostgreSQL.
3. **Task Queue:** Implement Celery and configure the Daily Tick (4:00 PM Ingestion, 4:15 PM Pipeline).
4. **Alpha Lab V2:** Implement the Nightly "Dream" Celery task, the Self-Healing retry loop, and the `/promote` API endpoint.
5. **Execution & WebSockets:** Rewrite `order_router.py` to support Net-Delta Aggregation and connect it to the Alpaca Live API. Implement WebSocket broadcasting.

---

## How to Initiate Level 5

When you are ready to start Level 5, open a fresh chat context with your AI assistant (Cursor, Windsurf, Copilot, etc.), ensure the `docs/level_5_manifesto.md` file is attached to the context, and prompt:

> *"I am the Portfolio Manager. We are transitioning our platform from Level 4 (Research Lab) to Level 5 (The Autonomous God Engine). Read the `docs/level_5_manifesto.md` file carefully to understand the entire history of this codebase, our ECS/Polars design patterns, and our end goal for Level 5.*
>
> *Confirm that you understand our strict requirement to NEVER alter the core financial matrix math (Risk APT, Dynamic DCF, Polars ECS systems) without explicit permission.*
>
> *Once you confirm, let's start by productionizing the infrastructure. Please write a comprehensive `docker-compose.yml` and the necessary Dockerfiles (one for the FastAPI backend, one for the Next.js frontend, and a Redis container) so we can run our platform in isolated, production-ready containers. After that, we will migrate SQLite to PostgreSQL."*