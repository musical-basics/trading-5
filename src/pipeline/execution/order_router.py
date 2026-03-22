"""
order_router.py — Level 5 Execution Routing

Routes approved orders through a multi-layer execution pipeline:
  1. Sub-portfolio intents → Net-Delta aggregation
  2. Order pacing (TWAP/VWAP slicing for large orders)
  3. Broker submission (Alpaca Live or Paper, with dry-run fallback)
  4. Execution logging via SQLAlchemy ORM (Postgres or SQLite)
  5. Redis pub/sub for real-time WebSocket broadcasting

Supports both paper and live trading based on ALPACA_PAPER env flag.
"""

import os
import math
import time
from datetime import datetime

from src.config import DB_PATH


def _get_alpaca_client():
    """
    Attempt to create an Alpaca API client.
    Returns None if keys are not configured.
    Supports both paper and live mode based on ALPACA_PAPER env var.
    """
    api_key = os.getenv("ALPACA_API_KEY", "").strip()
    secret_key = os.getenv("ALPACA_SECRET_KEY", "").strip()
    is_paper = os.getenv("ALPACA_PAPER", "true").lower() in ("true", "1", "yes")

    if is_paper:
        base_url = "https://paper-api.alpaca.markets"
    else:
        base_url = "https://api.alpaca.markets"

    if not api_key or not secret_key:
        return None

    try:
        import alpaca_trade_api as tradeapi
        api = tradeapi.REST(api_key, secret_key, base_url, api_version="v2")
        api.get_account()
        return api
    except Exception as e:
        print(f"  ⚠ Alpaca API connection failed: {e}")
        print(f"  ⚠ Falling back to dry-run mode.")
        return None


# ── TWAP/VWAP Order Pacing ──────────────────────────────────────

def _should_pace(order: dict, adv: float = 0) -> bool:
    """Determine if an order is large enough to require slicing."""
    notional = order["quantity"] * order["price"]
    # Pace orders > $50k notional or > 1% of ADV
    if notional > 50_000:
        return True
    if adv > 0 and order["quantity"] > (adv * 0.01):
        return True
    return False


def _twap_slices(order: dict, num_slices: int = 5) -> list[dict]:
    """Split a large order into TWAP slices for even execution."""
    base_qty = order["quantity"] // num_slices
    remainder = order["quantity"] % num_slices

    slices = []
    for i in range(num_slices):
        qty = base_qty + (1 if i < remainder else 0)
        if qty > 0:
            slices.append({
                **order,
                "quantity": qty,
                "slice_index": i + 1,
                "total_slices": num_slices,
            })

    return slices


# ── Execution Engine ────────────────────────────────────────────

def _publish_execution_event(event: dict):
    """Broadcast an execution event via Redis pub/sub."""
    try:
        import redis
        from src.config import REDIS_URL
        r = redis.from_url(REDIS_URL)
        import json
        r.publish("execution_events", json.dumps({
            "event_type": "execution",
            "payload": event,
        }))
    except Exception:
        pass  # Redis not available — non-critical


def _log_execution_orm(order: dict, trader_id=None, portfolio_id=None):
    """Log execution to Postgres/SQLite via SQLAlchemy ORM."""
    try:
        from src.core.database import SessionLocal
        from src.core.models import PaperExecution

        session = SessionLocal()
        execution = PaperExecution(
            ticker=order["ticker"],
            action=order["action"],
            quantity=order["quantity"],
            simulated_price=order["price"],
            strategy_id=order.get("strategy_id", "sma_crossover"),
            trader_id=trader_id,
            portfolio_id=portfolio_id,
        )
        session.add(execution)
        session.commit()
        session.close()
    except Exception:
        # Fallback to raw SQLite if ORM not available
        _log_execution_sqlite(order, trader_id, portfolio_id)


def _log_execution_sqlite(order: dict, trader_id=None, portfolio_id=None):
    """Fallback: log execution via raw SQLite (backward compat)."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO paper_executions
        (timestamp, ticker, action, quantity, simulated_price,
         strategy_id, trader_id, portfolio_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        order["ticker"], order["action"], order["quantity"],
        order["price"], order.get("strategy_id", "sma_crossover"),
        trader_id, portfolio_id,
    ))
    conn.commit()
    conn.close()


def route_orders(approved_orders, trader_id=None, portfolio_id=None):
    """
    Route approved orders to Alpaca (Paper/Live) or dry-run.
    Large orders are automatically sliced via TWAP.
    Executions are logged to the database and broadcast via WebSocket.

    Args:
        approved_orders: List of order dicts with ticker, action, quantity, price
        trader_id: Optional trader ID for execution provenance
        portfolio_id: Optional portfolio ID for execution provenance
    """
    print("=" * 60)
    print("PHASE 4: Execution Routing (Level 5)")
    print("=" * 60)

    if not approved_orders:
        print("  No orders to route. Pipeline complete.")
        print()
        return

    today_str = datetime.now().strftime("%Y-%m-%d")

    # ── Idempotency Check ────────────────────────────────────
    already_executed = set()
    try:
        from src.core.database import SessionLocal
        from src.core.models import PaperExecution
        from sqlalchemy import func
        session = SessionLocal()
        results = session.query(PaperExecution.ticker).filter(
            func.date(PaperExecution.timestamp) == today_str,
        )
        if portfolio_id is not None:
            results = results.filter(PaperExecution.portfolio_id == portfolio_id)
        already_executed = {r.ticker for r in results.all()}
        session.close()
    except Exception:
        # Fallback to SQLite
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        idem_sql = "SELECT DISTINCT ticker FROM paper_executions WHERE DATE(timestamp) = ?"
        idem_params = [today_str]
        if portfolio_id is not None:
            idem_sql += " AND portfolio_id = ?"
            idem_params.append(portfolio_id)
        cursor = conn.cursor()
        cursor.execute(idem_sql, idem_params)
        already_executed = {row[0] for row in cursor.fetchall()}
        conn.close()

    if already_executed:
        print(f"  ⚠ Already executed today: {', '.join(already_executed)}")

    # ── Try to connect to Alpaca ─────────────────────────────
    alpaca = _get_alpaca_client()
    is_live = alpaca is not None
    is_paper = os.getenv("ALPACA_PAPER", "true").lower() in ("true", "1", "yes")

    if is_live:
        mode = "PAPER" if is_paper else "LIVE"
        print(f"  ✓ Connected to Alpaca {mode} Trading API")
    else:
        print("  ℹ Running in DRY-RUN mode (no Alpaca API keys configured)")

    print()

    executed_count = 0
    filled_orders = {}

    for order in approved_orders:
        ticker = order["ticker"]
        action = order["action"]
        quantity = order["quantity"]
        price = order["price"]

        if ticker in already_executed:
            print(f"  ⊘ SKIPPED {action} {ticker}: Already executed today")
            continue

        # Determine if TWAP slicing is needed
        if _should_pace(order):
            slices = _twap_slices(order)
            print(f"  📊 TWAP: Splitting {action} {quantity} x {ticker} into {len(slices)} slices")
        else:
            slices = [order]

        for sl in slices:
            sl_qty = sl["quantity"]
            try:
                if is_live:
                    side = action.lower()
                    alpaca_order = alpaca.submit_order(
                        symbol=ticker, qty=sl_qty, side=side,
                        type="market", time_in_force="day",
                    )
                    print(f"  ✓ ROUTED {action} {sl_qty} x {ticker} @ ~${price:.2f} → Alpaca")
                else:
                    print(f"  ✓ DRY-RUN {action} {sl_qty} x {ticker} @ ${price:.2f}")

                # Log execution
                _log_execution_orm(sl, trader_id, portfolio_id)

                # Broadcast real-time event
                _publish_execution_event({
                    "ticker": ticker,
                    "action": action,
                    "quantity": sl_qty,
                    "price": price,
                    "timestamp": datetime.now().isoformat(),
                    "trader_id": trader_id,
                    "portfolio_id": portfolio_id,
                })

                executed_count += 1

                # Track fills for Net-Delta distribution
                if ticker not in filled_orders:
                    filled_orders[ticker] = {"filled_qty": 0, "avg_price": price}
                filled_orders[ticker]["filled_qty"] += sl_qty

                # Small delay between TWAP slices
                if len(slices) > 1:
                    time.sleep(0.1)

            except Exception as e:
                print(f"  ✗ FAILED {action} {ticker}: {e}")
                continue

    print()
    print(f"  ✓ {executed_count} orders executed and logged.")
    print()

    return filled_orders


if __name__ == "__main__":
    test_orders = [
        {"ticker": "AAPL", "action": "BUY", "quantity": 5, "price": 195.50},
    ]
    route_orders(test_orders)
