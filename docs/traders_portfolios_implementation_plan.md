# Traders & Portfolios — 40-Step Implementation Plan

> **Goal**: Add a hierarchical Trader → Portfolio structure where each Trader has exactly 10 sub-portfolios, each running a single strategy with isolated capital allocation, risk constraints, and rebalance scheduling.

---

## Codebase Map (Read These First)

Before starting any phase, read and understand these files:

| File | What It Does | Lines |
|------|-------------|-------|
| [config.py](file:///Users/test2/Documents/trading-4/src/config.py) | All constants, paths, thresholds | 117 |
| [db_init.py](file:///Users/test2/Documents/trading-4/src/pipeline/core/db_init.py) | Creates 14 SQLite tables | 255 |
| [duckdb_store.py](file:///Users/test2/Documents/trading-4/src/core/duckdb_store.py) | 8 parquet views, `get_connection()`, `get_parquet_path()` | 112 |
| [migrate_sqlite_to_parquet.py](file:///Users/test2/Documents/trading-4/src/core/migrate_sqlite_to_parquet.py) | SQLite→Parquet migration (6 functions) | 320 |
| [strategy_registry.py](file:///Users/test2/Documents/trading-4/src/ecs/strategy_registry.py) | 12 strategies, `STRATEGY_REGISTRY`, `evaluate_strategies()` | 340 |
| [tournament_system.py](file:///Users/test2/Documents/trading-4/src/ecs/tournament_system.py) | `run_tournament()`, equity curves, metrics | 248 |
| [risk_system.py](file:///Users/test2/Documents/trading-4/src/ecs/risk_system.py) | MCR iterative scaling, `apply_risk_constraints()` | 271 |
| [portfolio_state.py](file:///Users/test2/Documents/trading-4/src/pipeline/execution/portfolio_state.py) | `get_portfolio_state()` → equity + holdings | 136 |
| [portfolio_rebalancer.py](file:///Users/test2/Documents/trading-4/src/pipeline/execution/portfolio_rebalancer.py) | Target weight → buy/sell deltas, ADV gating | 181 |
| [simulation.py](file:///Users/test2/Documents/trading-4/src/pipeline/execution/simulation.py) | Risk limit filtering, `simulate_and_filter()` | 138 |
| [squeeze_filter.py](file:///Users/test2/Documents/trading-4/src/pipeline/execution/squeeze_filter.py) | Short position kill-switch (VIX + momentum) | 123 |
| [order_router.py](file:///Users/test2/Documents/trading-4/src/pipeline/execution/order_router.py) | `route_orders()` → Alpaca or dry-run, logs to `paper_executions` | 132 |
| [server.py](file:///Users/test2/Documents/trading-4/src/api/server.py) | FastAPI app, 4 routers, CORS, DuckDB lifespan | 75 |
| [tournament.py](file:///Users/test2/Documents/trading-4/src/api/routers/tournament.py) | `GET /api/strategies/list`, `POST /api/strategies/tournament` | 46 |
| [dashboard-shell.tsx](file:///Users/test2/Documents/trading-4/frontend/components/dashboard-shell.tsx) | 4 nav views, sidebar, top bar | 230 |
| [api.ts](file:///Users/test2/Documents/trading-4/frontend/lib/api.ts) | `fetchStrategies()`, `runTournament()` typed client | 85 |
| [strategy-studio.tsx](file:///Users/test2/Documents/trading-4/frontend/components/strategy-studio.tsx) | Strategy selection, equity chart, metrics table | 524 |
| [execution-ledger.tsx](file:///Users/test2/Documents/trading-4/frontend/components/execution-ledger.tsx) | Order management UI | ~300 |
| [risk-war-room.tsx](file:///Users/test2/Documents/trading-4/frontend/components/risk-war-room.tsx) | Risk matrix + macro regime display | ~300 |
| [main.py](file:///Users/test2/Documents/trading-4/main.py) | Pipeline entry point (root level) | — |

> [!IMPORTANT]
> **Python 3.9 compatibility**: This codebase runs on Python 3.9. Do NOT use `list[str] | None` syntax in Pydantic models. Use `Optional[List[str]]` from `typing` instead. `from __future__ import annotations` does NOT fix Pydantic's runtime type evaluation.

> [!IMPORTANT]
> **User rules**: Never run `prisma migrate` or any migration/DB reset commands without user confirmation. Give the user SQL queries to run manually. API keys go in `.env.local`. Push to git after every successful change.

---

## Phase 1: Database & Schema Modeling

### Step 1 — Traders Table
**File**: [db_init.py](file:///Users/test2/Documents/trading-4/src/pipeline/core/db_init.py)

Add after the Level 3 tables section (after line 233):

```sql
CREATE TABLE IF NOT EXISTS traders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    total_capital REAL NOT NULL DEFAULT 10000.0,
    unallocated_capital REAL NOT NULL DEFAULT 0.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

Also add `"traders"` to the `all_tables` list on line 239.

---

### Step 2 — Trader Constraints Table
**File**: [db_init.py](file:///Users/test2/Documents/trading-4/src/pipeline/core/db_init.py)

Add immediately after the `traders` table:

```sql
CREATE TABLE IF NOT EXISTS trader_constraints (
    trader_id INTEGER PRIMARY KEY,
    max_drawdown_pct REAL NOT NULL DEFAULT 0.20,
    max_open_positions INTEGER NOT NULL DEFAULT 50,
    max_capital_per_trade REAL NOT NULL DEFAULT 1000.0,
    halt_trading_flag INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (trader_id) REFERENCES traders(id)
);
```

---

### Step 3 — Portfolios Table
**File**: [db_init.py](file:///Users/test2/Documents/trading-4/src/pipeline/core/db_init.py)

```sql
CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trader_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    allocated_capital REAL NOT NULL DEFAULT 1000.0,
    strategy_id TEXT DEFAULT NULL,
    rebalance_freq TEXT NOT NULL DEFAULT 'Daily',
    next_rebalance_date DATE DEFAULT NULL,
    FOREIGN KEY (trader_id) REFERENCES traders(id),
    FOREIGN KEY (strategy_id) REFERENCES NULL
);
```

> [!NOTE]  
> `strategy_id` values correspond to keys in `STRATEGY_REGISTRY` dict in [strategy_registry.py](file:///Users/test2/Documents/trading-4/src/ecs/strategy_registry.py) (e.g. `"buy_hold"`, `"ev_sales"`, `"momentum"`, etc.). There are currently 12 registered strategies.

---

### Step 4 — Update `target_portfolio` Table
**File**: [db_init.py](file:///Users/test2/Documents/trading-4/src/pipeline/core/db_init.py)

The existing `target_portfolio` table (line 199) has `PRIMARY KEY (ticker, date)`. Add two new columns:

```sql
CREATE TABLE IF NOT EXISTS target_portfolio (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    target_weight REAL,
    mcr REAL,
    trader_id INTEGER DEFAULT NULL,
    portfolio_id INTEGER DEFAULT NULL,
    PRIMARY KEY (ticker, date, portfolio_id)
);
```

> [!WARNING]
> Changing the primary key will require dropping and recreating the table. Give the user the SQL to backup existing data first:
> ```sql
> ALTER TABLE target_portfolio RENAME TO target_portfolio_backup;
> -- (then create new table, INSERT ... SELECT from backup)
> ```

---

### Step 5 — Update `paper_executions` Table
**File**: [db_init.py](file:///Users/test2/Documents/trading-4/src/pipeline/core/db_init.py)

The existing `paper_executions` table (line 73) needs two new FK columns:

```sql
CREATE TABLE IF NOT EXISTS paper_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    simulated_price REAL NOT NULL,
    strategy_id TEXT DEFAULT 'sma_crossover',
    trader_id INTEGER DEFAULT NULL,
    portfolio_id INTEGER DEFAULT NULL
);
```

The `DEFAULT NULL` makes this backwards-compatible — old rows without trader/portfolio data stay valid.

---

### Step 6 — Parquet Migration
**File**: [migrate_sqlite_to_parquet.py](file:///Users/test2/Documents/trading-4/src/core/migrate_sqlite_to_parquet.py)

Add 3 new migration functions following the existing pattern (see `migrate_market_data` on line 64 as a template):

```python
def migrate_traders(conn: sqlite3.Connection) -> None:
    """Migrate traders → traders.parquet."""
    df = _read_sqlite_table(conn, "SELECT * FROM traders")
    if df.is_empty(): return
    path = os.path.join(PARQUET_DIR, "traders.parquet")
    df.write_parquet(path)

def migrate_portfolios(conn: sqlite3.Connection) -> None:
    """Migrate portfolios → portfolios.parquet."""
    df = _read_sqlite_table(conn, "SELECT * FROM portfolios")
    if df.is_empty(): return
    path = os.path.join(PARQUET_DIR, "portfolios.parquet")
    df.write_parquet(path)

def migrate_trader_constraints(conn: sqlite3.Connection) -> None:
    """Migrate trader_constraints → trader_constraints.parquet."""
    df = _read_sqlite_table(conn, "SELECT * FROM trader_constraints")
    if df.is_empty(): return
    path = os.path.join(PARQUET_DIR, "trader_constraints.parquet")
    df.write_parquet(path)
```

Call these in `run_migration()` (line 276) after the existing migrations.

---

### Step 7 — DuckDB View Registration
**File**: [duckdb_store.py](file:///Users/test2/Documents/trading-4/src/core/duckdb_store.py)

Add to `COMPONENT_FILES` dict (line 27):

```python
COMPONENT_FILES = {
    # ... existing entries ...
    "traders":              "traders.parquet",
    "portfolios":           "portfolios.parquet",
    "trader_constraints":   "trader_constraints.parquet",
}
```

---

## Phase 2: Core Business Logic & Capital Allocation

### Step 8 — Trader Manager Utility
**File**: `[NEW] src/core/trader_manager.py`

Create this new file. It orchestrates trader lifecycle:

```python
"""
trader_manager.py — Trader instantiation, validation, and capital allocation.
"""
import sqlite3
from datetime import datetime, timedelta
from src.config import DB_PATH
from src.ecs.strategy_registry import get_all_strategy_ids


def create_trader(name: str, capital: float = 10000.0) -> int:
    """Create a new trader and auto-generate 10 sub-portfolios.

    Returns the trader_id.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Insert trader
    cursor.execute(
        "INSERT INTO traders (name, total_capital, unallocated_capital) VALUES (?, ?, ?)",
        (name, capital, 0.0),
    )
    trader_id = cursor.lastrowid

    # Insert default constraints
    cursor.execute(
        """INSERT INTO trader_constraints
           (trader_id, max_drawdown_pct, max_open_positions, max_capital_per_trade)
           VALUES (?, 0.20, 50, ?)""",
        (trader_id, capital / 10),
    )

    # Auto-create 10 portfolios with equal capital
    per_portfolio = capital / 10
    today = datetime.now().strftime("%Y-%m-%d")
    for i in range(1, 11):
        cursor.execute(
            """INSERT INTO portfolios
               (trader_id, name, allocated_capital, strategy_id, rebalance_freq, next_rebalance_date)
               VALUES (?, ?, ?, NULL, 'Daily', ?)""",
            (trader_id, f"Portfolio {i}", per_portfolio, today),
        )

    conn.commit()
    conn.close()
    return trader_id


def get_trader(trader_id: int) -> dict:
    """Fetch trader details + constraints."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    trader = dict(conn.execute("SELECT * FROM traders WHERE id = ?", (trader_id,)).fetchone())
    constraints = conn.execute("SELECT * FROM trader_constraints WHERE trader_id = ?", (trader_id,)).fetchone()
    if constraints:
        trader["constraints"] = dict(constraints)
    conn.close()
    return trader


def assign_strategy(portfolio_id: int, strategy_id: str) -> None:
    """Assign a single strategy to a portfolio. Validates against STRATEGY_REGISTRY."""
    valid_ids = get_all_strategy_ids()
    if strategy_id not in valid_ids:
        raise ValueError(f"Unknown strategy '{strategy_id}'. Valid: {valid_ids}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE portfolios SET strategy_id = ? WHERE id = ?",
        (strategy_id, portfolio_id),
    )
    conn.commit()
    conn.close()
```

---

### Step 9 — Capital Auto-Allocation (covered in Step 8)
The `create_trader()` function above already implements the 10-portfolio auto-creation with `capital / 10` each.

---

### Step 10 — Single Strategy Enforcement (covered in Step 8)
The `assign_strategy()` function validates `strategy_id` against `get_all_strategy_ids()` from the registry.

---

### Step 11 — Rebalance Scheduler
**File**: `[NEW] src/pipeline/core/rebalance_scheduler.py`

```python
"""
rebalance_scheduler.py — Evaluates each portfolio's rebalance schedule.
"""
import sqlite3
from datetime import datetime, timedelta
from src.config import DB_PATH


FREQ_MAP = {
    "Daily": 1,
    "Weekly": 7,
    "Monthly": 30,
}


def get_due_portfolios() -> list[dict]:
    """Return portfolios whose next_rebalance_date <= today."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT p.*, t.name as trader_name
           FROM portfolios p
           JOIN traders t ON p.trader_id = t.id
           WHERE p.strategy_id IS NOT NULL
             AND p.next_rebalance_date <= ?""",
        (today,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def advance_rebalance_date(portfolio_id: int) -> None:
    """After successful rebalance, advance next_rebalance_date."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT rebalance_freq FROM portfolios WHERE id = ?",
        (portfolio_id,),
    ).fetchone()
    if row:
        days = FREQ_MAP.get(row[0], 1)
        new_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        conn.execute(
            "UPDATE portfolios SET next_rebalance_date = ? WHERE id = ?",
            (new_date, portfolio_id),
        )
        conn.commit()
    conn.close()
```

---

### Step 12 — Pipeline Orchestration Loop
**File**: [main.py](file:///Users/test2/Documents/trading-4/main.py)

Update the main pipeline to iterate over active portfolios instead of running globally. Pseudocode:

```python
from src.pipeline.core.rebalance_scheduler import get_due_portfolios, advance_rebalance_date

due_portfolios = get_due_portfolios()
for portfolio in due_portfolios:
    strategy_id = portfolio["strategy_id"]
    portfolio_id = portfolio["id"]
    trader_id = portfolio["trader_id"]
    capital = portfolio["allocated_capital"]

    # 1. Evaluate single strategy for this portfolio
    weights = evaluate_single_strategy(strategy_id, data)

    # 2. Apply risk constraints scoped to this portfolio's capital
    risk_adjusted = apply_risk_constraints(weights, capital=capital)

    # 3. Generate orders scoped to this portfolio
    orders = rebalance_portfolio(risk_adjusted, portfolio_id, trader_id)

    # 4. Filter through trader-level constraints
    approved = apply_trader_constraints(orders, trader_id)

    # 5. Route orders
    route_orders(approved, trader_id=trader_id, portfolio_id=portfolio_id)

    # 6. Advance schedule
    advance_rebalance_date(portfolio_id)
```

---

### Step 13 — Scoped Action Intent
**File**: [strategy_registry.py](file:///Users/test2/Documents/trading-4/src/ecs/strategy_registry.py) and wherever action_intent is produced.

Tag all output weight DataFrames with `portfolio_id` and `trader_id` columns. The `evaluate_strategies()` function (currently takes `df` and `strategy_ids`) should accept optional `portfolio_id` and `trader_id` params and add them to the result DataFrame.

---

## Phase 3: ECS Pipeline & Execution Engine

### Step 14 — Strategy Context Injection
**File**: [strategy_registry.py](file:///Users/test2/Documents/trading-4/src/ecs/strategy_registry.py)

Add a new function alongside `evaluate_strategies()`:

```python
def evaluate_single_strategy(strategy_id: str, df: pl.DataFrame) -> pl.DataFrame:
    """Evaluate exactly one strategy. Used by portfolio-scoped pipeline."""
    if strategy_id not in STRATEGY_REGISTRY:
        raise KeyError(f"Unknown strategy: {strategy_id}")
    fn = STRATEGY_REGISTRY[strategy_id]
    result = fn(df)
    col_name = f"raw_weight_{strategy_id}"
    return result.select(["entity_id", "date", col_name]).rename({col_name: "raw_weight"})
```

---

### Step 15 — Portfolio-Level Risk (MCR)
**File**: [risk_system.py](file:///Users/test2/Documents/trading-4/src/ecs/risk_system.py)

Modify `apply_risk_constraints()` (line 123) to accept optional `capital: float` parameter. When provided, scale the weights relative to that capital amount instead of the full portfolio. The MCR computation already works on weights, so this mainly affects the audit output.

---

### Step 16 — Trader-Level Risk Rollup
**File**: [risk_system.py](file:///Users/test2/Documents/trading-4/src/ecs/risk_system.py)

Add a new function:

```python
def check_trader_risk(trader_id: int, market_df: pl.DataFrame) -> dict:
    """Aggregate risk across all 10 portfolios for a trader.

    Loads each portfolio's current holdings, computes combined
    covariance exposure, and checks against trader-level vol limit.
    """
    # 1. Load all portfolio holdings for this trader
    # 2. Combine into a single weight vector
    # 3. compute_mcr() on the combined weights
    # 4. Return {total_vol, max_mcr, breach: bool}
```

---

### Step 17 — Squeeze Filter Scoping
**File**: [squeeze_filter.py](file:///Users/test2/Documents/trading-4/src/pipeline/execution/squeeze_filter.py)

Modify `apply_squeeze_filter()` to accept optional `portfolio_id` parameter. When provided, filter the `target_portfolio` query to `WHERE portfolio_id = ?`. Log which portfolio's short was killed.

---

### Step 18 — Refactor Portfolio State
**File**: [portfolio_state.py](file:///Users/test2/Documents/trading-4/src/pipeline/execution/portfolio_state.py)

Add a new function alongside `get_portfolio_state()`:

```python
def get_portfolio_state_by_id(portfolio_id: int) -> tuple[float, dict]:
    """Get equity + holdings for a specific sub-portfolio.

    Queries paper_executions WHERE portfolio_id = ? and reconstructs
    net holdings using the portfolio's allocated_capital as the base.
    """
```

Keep the existing `get_portfolio_state()` untouched for backward compatibility.

---

### Step 19 — Trader Equity Aggregation
**File**: [portfolio_state.py](file:///Users/test2/Documents/trading-4/src/pipeline/execution/portfolio_state.py)

```python
def get_trader_state(trader_id: int) -> tuple[float, dict]:
    """Sum real-time equity of all 10 sub-portfolios for a trader."""
    conn = sqlite3.connect(DB_PATH)
    portfolio_ids = [r[0] for r in conn.execute(
        "SELECT id FROM portfolios WHERE trader_id = ?", (trader_id,)
    ).fetchall()]
    conn.close()

    total_equity = 0.0
    all_holdings = {}
    for pid in portfolio_ids:
        equity, holdings = get_portfolio_state_by_id(pid)
        total_equity += equity
        for ticker, info in holdings.items():
            if ticker in all_holdings:
                all_holdings[ticker]["shares"] += info["shares"]
            else:
                all_holdings[ticker] = info.copy()
    return total_equity, all_holdings
```

---

### Step 20 — Scoped Rebalancer Math
**File**: [portfolio_rebalancer.py](file:///Users/test2/Documents/trading-4/src/pipeline/execution/portfolio_rebalancer.py)

Modify `rebalance_portfolio()` to accept optional `portfolio_id` and `trader_id` params. When provided:
- Query `target_portfolio WHERE portfolio_id = ?` (instead of global latest)
- Get `allocated_capital` from `portfolios` table as `total_equity` (the $1k slice)
- Call `get_portfolio_state_by_id(portfolio_id)` instead of `get_portfolio_state()`

---

### Step 21 — Constraint Enforcement
**File**: [simulation.py](file:///Users/test2/Documents/trading-4/src/pipeline/execution/simulation.py)

Modify `simulate_and_filter()` to accept optional `trader_id`. When provided:
- Load `trader_constraints` for that trader
- Use `max_open_positions` and `max_capital_per_trade` from constraints instead of the hardcoded constants (lines 15-16)
- Count open positions across ALL 10 of that trader's portfolios combined

---

### Step 22 — Drawdown Kill-Switch
**File**: [simulation.py](file:///Users/test2/Documents/trading-4/src/pipeline/execution/simulation.py)

Add at the top of `simulate_and_filter()`:

```python
if trader_id:
    constraints = load_trader_constraints(trader_id)
    if constraints["halt_trading_flag"]:
        print(f"  ✗ HALTED: Trader {trader_id} has halt flag set")
        return []

    current_equity, _ = get_trader_state(trader_id)
    initial_capital = get_trader_capital(trader_id)
    drawdown = (initial_capital - current_equity) / initial_capital
    if drawdown >= constraints["max_drawdown_pct"]:
        print(f"  ✗ HALTED: Trader drawdown {drawdown:.1%} >= {constraints['max_drawdown_pct']:.1%}")
        # Tag all orders as HALTED_BY_CONSTRAINT
        return []
```

---

### Step 23 — Execution Ledger Tagging
**File**: [order_router.py](file:///Users/test2/Documents/trading-4/src/pipeline/execution/order_router.py)

Modify `route_orders()` to accept `trader_id` and `portfolio_id` kwargs. Update the INSERT (line 106):

```python
cursor.execute("""
    INSERT INTO paper_executions
    (timestamp, ticker, action, quantity, simulated_price, strategy_id, trader_id, portfolio_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (
    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ticker, action, quantity, price, strategy_id, trader_id, portfolio_id,
))
```

---

### Step 24 — Advance Rebalance Dates
Already covered in Step 11's `advance_rebalance_date()` function. Call it in the pipeline loop (Step 12) after successful execution.

---

## Phase 4: FastAPI Backend Endpoints

### Step 25 — Pydantic Models
**File**: `[NEW] src/api/routers/models.py`

```python
"""Pydantic models for Traders & Portfolios API."""
from typing import Optional, List
from pydantic import BaseModel


class TraderCreate(BaseModel):
    name: str
    total_capital: float = 10000.0

class TraderConstraintUpdate(BaseModel):
    max_drawdown_pct: Optional[float] = None
    max_open_positions: Optional[int] = None
    max_capital_per_trade: Optional[float] = None
    halt_trading_flag: Optional[bool] = None

class TraderResponse(BaseModel):
    id: int
    name: str
    total_capital: float
    unallocated_capital: float
    constraints: Optional[dict] = None
    portfolios_count: int = 10

class PortfolioResponse(BaseModel):
    id: int
    trader_id: int
    name: str
    allocated_capital: float
    strategy_id: Optional[str] = None
    strategy_name: Optional[str] = None
    rebalance_freq: str
    next_rebalance_date: Optional[str] = None

class StrategyAssignment(BaseModel):
    strategy_id: str

class ScheduleUpdate(BaseModel):
    rebalance_freq: str  # "Daily", "Weekly", "Monthly"
```

---

### Steps 26-27 — Traders Router
**File**: `[NEW] src/api/routers/traders.py`

```python
from fastapi import APIRouter, HTTPException
from src.api.routers.models import TraderCreate, TraderResponse, TraderConstraintUpdate
from src.core.trader_manager import create_trader, get_trader

router = APIRouter(prefix="/api/traders", tags=["traders"])

@router.get("/")
async def list_traders(): ...

@router.post("/", status_code=201)
async def create_new_trader(req: TraderCreate): ...

@router.put("/{trader_id}/constraints")
async def update_constraints(trader_id: int, req: TraderConstraintUpdate): ...
```

---

### Steps 29-31 — Portfolios Router
**File**: `[NEW] src/api/routers/portfolios.py`

```python
from fastapi import APIRouter, HTTPException
from src.api.routers.models import PortfolioResponse, StrategyAssignment, ScheduleUpdate
from src.core.trader_manager import assign_strategy

router = APIRouter(prefix="/api", tags=["portfolios"])

@router.get("/traders/{trader_id}/portfolios")
async def get_portfolios(trader_id: int): ...

@router.put("/portfolios/{portfolio_id}/strategy")
async def update_strategy(portfolio_id: int, req: StrategyAssignment): ...

@router.put("/portfolios/{portfolio_id}/schedule")
async def update_schedule(portfolio_id: int, req: ScheduleUpdate): ...
```

---

### Step 32 — Update Execution API
**File**: [execution.py](file:///Users/test2/Documents/trading-4/src/api/routers/execution.py)

Modify the pending orders endpoint to group by `trader_id` and `portfolio_id`. Add optional query params `?trader_id=X` for filtering.

---

### Step 33 — Wire Routers
**File**: [server.py](file:///Users/test2/Documents/trading-4/src/api/server.py)

Add to imports (line 23):
```python
from src.api.routers import tournament, xray, risk, execution, traders, portfolios
```

Add after line 62:
```python
app.include_router(traders.router)
app.include_router(portfolios.router)
```

---

## Phase 5: Frontend API Integration

### Step 34 — Frontend API Types
**File**: [api.ts](file:///Users/test2/Documents/trading-4/frontend/lib/api.ts)

Add TypeScript interfaces:

```typescript
export interface Trader {
  id: number
  name: string
  total_capital: number
  unallocated_capital: number
  constraints?: TraderConstraint
}

export interface TraderConstraint {
  max_drawdown_pct: number
  max_open_positions: number
  max_capital_per_trade: number
  halt_trading_flag: boolean
}

export interface Portfolio {
  id: number
  trader_id: number
  name: string
  allocated_capital: number
  strategy_id: string | null
  strategy_name: string | null
  rebalance_freq: string
  next_rebalance_date: string | null
}
```

---

### Step 35 — API Client Methods
**File**: [api.ts](file:///Users/test2/Documents/trading-4/frontend/lib/api.ts)

```typescript
export async function getTraders(): Promise<Trader[]> { ... }
export async function createTrader(name: string, capital: number): Promise<Trader> { ... }
export async function updateConstraints(traderId: number, data: Partial<TraderConstraint>): Promise<void> { ... }
export async function getPortfolios(traderId: number): Promise<Portfolio[]> { ... }
export async function updatePortfolioStrategy(portfolioId: number, strategyId: string): Promise<void> { ... }
export async function updatePortfolioSchedule(portfolioId: number, freq: string): Promise<void> { ... }
```

---

### Step 36 — Global Trader Context
**File**: `[NEW] frontend/lib/trader-context.tsx`

Create a React Context with:
- `selectedTrader: Trader | null`
- `setSelectedTrader(trader)`
- `portfolios: Portfolio[]`
- `refreshPortfolios()`

Wrap the app in this provider from [layout.tsx](file:///Users/test2/Documents/trading-4/frontend/app/layout.tsx).

---

## Phase 6: Frontend UI Architecture

### Step 37 — Trader Navigation
**File**: [dashboard-shell.tsx](file:///Users/test2/Documents/trading-4/frontend/components/dashboard-shell.tsx)

Add to `navItems` array (line 30) and `View` type (line 28):

```typescript
type View = "strategy-studio" | "xray-inspector" | "risk-war-room" | "execution-ledger" | "trader-manager"

// Add to navItems:
{
  id: "trader-manager" as const,
  label: "Traders & Portfolios",
  icon: Users,  // from lucide-react
  description: "Capital Management",
  badge: null
}
```

Add the render switch (line 212):
```tsx
{currentView === "trader-manager" && <TraderManager />}
```

---

### Step 38 — Trader Management View
**File**: `[NEW] frontend/components/trader-manager.tsx`

Build a component with:
- **Trader list** (left panel): Cards showing trader name, total capital, drawdown badge
- **Create Trader dialog**: Name + capital input, POST to `/api/traders`
- **Constraints card** (when trader selected): Sliders for max drawdown %, max positions, max capital/trade. PUT on change.
- **Portfolio grid** (right panel): 10-card grid for the selected trader (see Step 39)

---

### Step 39 — Portfolio Grid Component
**File**: `[NEW] frontend/components/portfolio-grid.tsx`

Each of the 10 cards shows:
- Portfolio name + allocated capital ($1,000)
- Strategy dropdown (fetched from `GET /api/strategies/list`), PUT on change
- Rebalance frequency selector (Daily/Weekly/Monthly)
- Next rebalance date display
- Status badge (Active/Unassigned/Halted)

---

### Step 40 — Execution & Risk Scoping
**File**: [execution-ledger.tsx](file:///Users/test2/Documents/trading-4/frontend/components/execution-ledger.tsx)
- Add "Portfolio" column to the orders table showing `portfolio.name`
- Add colored "Halted" badges for `HALTED_BY_CONSTRAINT` status orders
- Add a trader/portfolio filter dropdown at the top

**File**: [risk-war-room.tsx](file:///Users/test2/Documents/trading-4/frontend/components/risk-war-room.tsx)
- Add a toggle: "Trader Aggregate Risk" vs "Isolated Portfolio Risk"
- When "Isolated" is selected, show 10 mini risk panels (one per portfolio)
- When "Aggregate" is selected, show the combined risk matrix

---

## Implementation Order (Recommended)

Execute phases sequentially. Within each phase, steps are ordered by dependency:

1. **Phase 1** (Steps 1-7): Schema + migration. Git push after.
2. **Phase 2** (Steps 8-13): Business logic. Git push after.
3. **Phase 3** (Steps 14-24): ECS + execution engine. Git push after.
4. **Phase 4** (Steps 25-33): API endpoints. Git push after. Verify with curl.
5. **Phase 5** (Steps 34-36): Frontend API layer. Git push after.
6. **Phase 6** (Steps 37-40): Frontend UI. Git push after.

> [!CAUTION]
> After Phase 1, give the user SQL migration instructions (don't run them directly). After each phase, run `pnpm dev` (frontend) and `python3 -m uvicorn src.api.server:app --reload` (backend) to verify nothing is broken.

---

## Verification Checklist

- [ ] `python3 -c "from src.pipeline.core.db_init import init_db; init_db()"` creates new tables
- [ ] `curl http://localhost:8000/api/traders` returns `[]`
- [ ] `curl -X POST http://localhost:8000/api/traders -H 'Content-Type: application/json' -d '{"name":"Test","total_capital":10000}'` creates trader + 10 portfolios
- [ ] `curl http://localhost:8000/api/traders/1/portfolios` returns 10 portfolios
- [ ] Frontend shows "Traders & Portfolios" view in sidebar
- [ ] Portfolio grid displays 10 cards with strategy dropdowns
- [ ] Assigning a strategy and rebalancing produces scoped orders
- [ ] Drawdown kill-switch halts trading when breach threshold is hit
