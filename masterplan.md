Here is the 50-step implementation plan for your AI agent to upgrade QuantPrime from Level 4 (Research Lab) to Level 5 (The God Engine).

This plan strictly follows the Execution Order and directives defined in your level_5_manifesto.md. It commands the agent to preserve the core Polars/ECS mathematical logic (zero-look-ahead bias, separation of Alpha and Risk) while wrapping the system in a cloud-native, autonomous, live-execution infrastructure.

Phase 1: Infrastructure First & Database Migration (Objective A)
Agent Directive: Do not alter the core financial matrix math (src/ecs/, src/pipeline/scoring/). Focus strictly on Infrastructure and transactional state migration.

[Architect] Create docker-compose.yml: Define the orchestration for api (FastAPI), web (Next.js), postgres (transactional database), redis (message broker), and celery_worker services (Ref: Obj A - Containerization).

[Architect] Configure Persistent Volumes: In docker-compose.yml, map a persistent volume to /app/data/components/ so the DuckDB analytical Parquet files persist between container restarts (Ref: Obj A - Containerization).

[Tank] Create Dockerfile.api: Create a Dockerfile for the FastAPI backend using a Python 3.11+ slim image.

[Switch] Create Dockerfile.web: Create a Dockerfile for the Next.js frontend, utilizing pnpm (as per project conventions) to build and serve the production React app.

[Niobe] Environment Configuration: Update src/config.py and .env.local to route transactional connections to DATABASE_URL (Postgres) and REDIS_URL, explicitly keeping PARQUET_DIR for analytical data.

[Tank] Update Dependencies: Add sqlalchemy, alembic, psycopg2-binary, celery, redis, and websockets to requirements.txt.

[Tank] Initialize Alembic: Run alembic init alembic and configure alembic.ini to connect to the Postgres DATABASE_URL.

[Tank] Define SQLAlchemy Models: Create src/core/models.py, translating the existing SQLite schemas (traders, trader_constraints, portfolios, paper_executions) into SQLAlchemy ORM models (Ref: Obj A - Database Migration).

[Tank] Define Alpha Lab ORM: Add an AlphaLabExperiments SQLAlchemy model in models.py to move the isolated Alpha Lab storage out of local Parquet files and into PostgreSQL.

[Tank] Generate Initial Migration: Run alembic revision --autogenerate -m "Initial Postgres Schema" to create the transactional tables.

[Tank] Write Data Migration Script: Create src/scripts/migrate_sqlite_to_pg.py to transfer existing records from data/level3_trading.db into the new Postgres database to prevent data loss.

[Tank] Refactor Trader Manager: Update src/core/trader_manager.py to replace raw sqlite3 queries with SQLAlchemy ORM sessions via FastAPI Depends().

[Tank] Refactor Alpha Lab Store: Refactor src/alpha_lab/alpha_lab_store.py to use SQLAlchemy sessions for experiment metadata while keeping the actual generated equity curves stored in the EQUITY_CURVES_DIR Parquet files.

[Oracle] Expand Universe: Update DEFAULT_UNIVERSE in src/config.py from 50 to 3,000+ tickers (Russell 3000 equivalent) to utilize Polars' out-of-core scaling capabilities (Ref: Obj A - Universe Expansion).

Phase 2: Autonomous Operations & The Master Clock (Objective B)
Agent Directive: Eliminate manual pipeline execution and implement the Master Clock.

[Tank] Initialize Celery: Create src/core/celery_app.py, initializing the Celery application and binding it to the Redis broker.

[Tank] Define Ingestion Tasks: Create src/tasks/ingestion_tasks.py. Wrap the data ingestion logic (data_ingestion.ingest(), macro_ingestion, etc.) into a @celery.task.

[Morpheus] Schedule Daily Tick (Ingestion): Configure Celery Beat to trigger the Ingestion task automatically at exactly 4:00 PM EST daily (Ref: Obj B - Daily Tick).

[Tank] Define ECS Pipeline Tasks: Create src/tasks/pipeline_tasks.py. Wrap Systems 2, 3, and 4 (Alignment, Strategy Evaluation, Risk APT) into a @celery.task.

[Morpheus] Schedule Daily Tick (Pipeline): Configure Celery Beat to trigger the ECS Math/Risk pipeline task automatically at exactly 4:15 PM EST daily, automatically queuing execution orders upon completion (Ref: Obj B - Daily Tick).

[Tank] Implement Continuous Learning Task: Wrap xgb_wfo_engine.run_xgb_wfo() into a background @celery.task.

[Morpheus] Schedule Continuous Learning: Configure Celery Beat to run the WFO Retraining task as a weekend cron job (e.g., Saturday at 2:00 AM) to automatically roll the WFO training window forward (Ref: Obj B - Continuous Learning).

[Tank] Deprecate Manual Execution: Refactor main.py from a sequential blocking script into a CLI interface that dispatches the Celery workflow chain if an admin requires a forced manual run.

Phase 3: Alpha Lab 2.0 (Manifesto Section 5)
Agent Directive: Transform the LLM sandbox into an automated, self-healing strategy factory.

[Oracle] Expand Feature Context: Modify _load_aligned_data() in lab_backtester.py to explicitly merge macro_factors (vix, tnx) into the Sandbox DataFrame so the LLM can write cross-asset regime logic without hallucinating (Ref: Sec 5.4).

[Tank] Capture Sandbox Tracebacks: Update execute_strategy() in sandbox_executor.py to intercept runtime exceptions and return the full Python traceback string.

[Oracle] Implement Self-Healing Reflection Loop: In src/api/routers/alpha_lab.py, catch backtest sandbox failures and automatically feed the traceback back to the LLM: "Your code failed with this error: [Traceback]. Please fix the code." Limit to 3 retries (Ref: Sec 5.1).

[Morpheus] Create Nightly Discovery Task: Add @celery.task(cron='0 2 * * *') in src/tasks/alpha_tasks.py to trigger the evolutionary genetic prompting every night at 2:00 AM (Ref: Sec 5.2).

[Tank] Implement Genetic Prompting: In the nightly task, query Postgres for previous passed experiments with the highest Sharpe ratios. Feed their Python code back to Claude with the prompt: "Mutate these by introducing a new feature or combining logic to reduce Max Drawdown. Generate 3 new variants."

[Tank] Implement One-Click Production Promotion: Create the POST /api/alpha-lab/{id}/promote endpoint in alpha_lab.py (Ref: Sec 5.3).

[Tank] Build Handoff Logic: Inside the /promote endpoint, extract the successful Python code from the DB and write it physically to a new file: src/ecs/strategies/custom/generated_{id}.py.

[Architect] Dynamic Registry Update: Update src/ecs/strategy_registry.py to dynamically scan the custom/ directory on startup, importing and registering the new AI strategies into STRATEGY_REGISTRY.

[Switch] Frontend Promotion UI: Update frontend/components/alpha-lab.tsx to display a "🚀 Promote to Production" button for experiments with a "passed" status.

Phase 4: True Multi-Manager Execution & Live Broker Sync (Objectives C & D)
Agent Directive: Move away from Paper Ledgers; implement Net-Delta, Pacing, and Alpaca Live API.

[Architect] Design Multi-Manager Execution: Refactor portfolio_rebalancer.py to evaluate the hierarchy (Traders -> Portfolios -> Strategies), extracting intents tagged by their specific portfolio_id (Ref: Obj D - Hierarchical Execution).

[Tank] Implement the Net-Delta Router: In order_router.py, aggregate all individual sub-portfolio BUY/SELL intents for a given ticker into a single, master "Net Delta" bulk order to save on commissions/spread (Ref: Obj D - Net-Delta Routing).

[Tank] Connect the Live Broker: Update _get_alpaca_client() in order_router.py to connect to Alpaca Live or Interactive Brokers using credentials from .env.production (Ref: Obj C - Live API Integration).

[Tank] Implement Order Pacing (TWAP/VWAP): Calculate if the Net-Delta order exceeds 1% of the 30-day Average Daily Volume (ADV) obtained from market_data.parquet (Ref: Obj C - Order Pacing).

[Tank] Slice & Schedule Orders: If the 1% ADV threshold is exceeded, slice the master order into smaller chunks and use Celery apply_async(countdown=...) to execute them progressively over the trading day.

[Tank] Implement Fractional Internal Ledgering: After the master bulk order executes, mathematically distribute the filled fractional shares back to the respective sub-portfolios in the PostgreSQL executions table (Ref: Obj D).

[Tank] Implement State Reconciliation: Create a Celery task sync_broker_state() that compares the internal Postgres PortfolioStateComponent with the actual live broker inventory via REST to correct drift (Ref: Obj C - State Reconciliation).

[Oracle] Implement Intraday Squeeze Monitor: Create a high-frequency polling script that runs via Celery every 5 minutes during market hours to monitor ^VIX (Ref: Obj C - Intraday Squeeze Defense).

[Tank] Squeeze Defense Trigger: If the 5-minute task detects VIX > 30, bypass the EOD schedule, instantly invoke squeeze_filter.py, and immediately route emergency liquidations for short positions.

Phase 5: Real-Time Telemetry & WebSockets (Objective E)
Agent Directive: Push events directly to the frontend; completely replace REST polling.

[Tank] Setup WebSocket Manager: In src/api/server.py, establish a WebSocketConnectionManager to handle live client connections via a new /api/ws/telemetry endpoint.

[Tank] Integrate Redis Pub/Sub: Configure the FastAPI backend to subscribe to Redis broadcast channels.

[Tank] Broadcast Execution Hooks: Add Redis publish events inside order_router.py to push status changes (Pending → Partial → Filled) in real-time as Alpaca webhooks/polling return updates (Ref: Obj E).

[Tank] Broadcast PnL Ticks: Set up an async background task listening to Alpaca's WebSockets to stream real-time PnL ticks and publish them to the Redis WebSocket channel.

[Switch] Create Frontend WS Provider: Implement a global WebSocket Context Provider in frontend/lib/ws.ts that connects to the FastAPI WS endpoint on mount.

[Switch] Update Execution UI: Modify frontend/components/execution-ledger.tsx to consume the WebSocket context, dynamically updating order statuses (Pending -> Complete) and flashing rows green/red as real-time fills arrive without page refreshes.

[Switch] Update Dashboard Status: In frontend/components/dashboard-shell.tsx, replace the static footer timestamp with a live WebSocket heartbeat and real-time PnL tick stream.

[Switch] Net-Delta UI Toggle: Add a view toggle to the Execution Ledger to allow users to dynamically switch between "Raw Sub-Portfolio Intent" and "Aggregated Net-Delta Execution".

[Switch] Update Trader Manager UI: Modify frontend/components/trader-manager.tsx to automatically refetch the strategy list so newly promoted AI strategies are instantly available for live capital allocation.

[Mouse] End-to-End Live Simulation: Spin up the full Docker stack using docker-compose up -d --build. Verify Postgres persistence, test the Alpha Lab self-healing loop, confirm Net-Delta Alpaca routing, and validate real-time WebSocket UI updates.