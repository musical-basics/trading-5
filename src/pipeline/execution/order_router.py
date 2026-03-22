"""
execution.py — Level 1 Phase 4: Execution Routing

Routes approved orders to the Alpaca Paper Trading API and logs
successful executions to the paper_executions SQLite table.

If Alpaca API keys are not configured, falls back to a simulated
dry-run mode that logs trades locally without hitting the network.

Includes idempotency check: won't re-submit orders for tickers
that were already executed today.
"""

import sqlite3
import os
from datetime import datetime
from src.config import DB_PATH


def _get_alpaca_client():
    """
    Attempt to create an Alpaca API client.
    Returns None if keys are not configured.
    """
    api_key = os.getenv("ALPACA_API_KEY", "").strip()
    secret_key = os.getenv("ALPACA_SECRET_KEY", "").strip()
    base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets").strip()

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


def route_orders(approved_orders, trader_id=None, portfolio_id=None):
    """
    Route approved orders to Alpaca Paper API (or dry-run if keys not set).
    Log successful executions to the paper_executions table.

    Args:
        approved_orders: List of order dicts with ticker, action, quantity, price
        trader_id: Optional trader ID for execution provenance
        portfolio_id: Optional portfolio ID for execution provenance
    """
    print("=" * 60)
    print("PHASE 4: Execution Routing")
    print("=" * 60)

    if not approved_orders:
        print("  No orders to route. Pipeline complete.")
        print()
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")

    # ── Idempotency Check ────────────────────────────────────
    already_executed = set()
    idem_sql = "SELECT DISTINCT ticker FROM paper_executions WHERE DATE(timestamp) = ?"
    idem_params = [today_str]
    if portfolio_id is not None:
        idem_sql += " AND portfolio_id = ?"
        idem_params.append(portfolio_id)
    cursor.execute(idem_sql, idem_params)
    already_executed = {row[0] for row in cursor.fetchall()}

    if already_executed:
        print(f"  ⚠ Already executed today: {', '.join(already_executed)}")

    # ── Try to connect to Alpaca ─────────────────────────────
    alpaca = _get_alpaca_client()
    is_live = alpaca is not None

    if is_live:
        print("  ✓ Connected to Alpaca Paper Trading API")
    else:
        print("  ℹ Running in DRY-RUN mode (no Alpaca API keys configured)")

    print()

    executed_count = 0

    for order in approved_orders:
        ticker = order["ticker"]
        action = order["action"]
        quantity = order["quantity"]
        price = order["price"]
        strategy_id = order.get("strategy_id", "sma_crossover")

        if ticker in already_executed:
            print(f"  ⊘ SKIPPED {action} {ticker}: Already executed today")
            continue

        try:
            if is_live:
                side = action.lower()
                alpaca.submit_order(
                    symbol=ticker, qty=quantity, side=side,
                    type="market", time_in_force="day",
                )
                print(f"  ✓ ROUTED {action} {quantity} x {ticker} @ ~${price:.2f} → Alpaca Paper")
            else:
                print(f"  ✓ DRY-RUN {action} {quantity} x {ticker} @ ${price:.2f}")

            cursor.execute("""
                INSERT INTO paper_executions
                (timestamp, ticker, action, quantity, simulated_price,
                 strategy_id, trader_id, portfolio_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ticker, action, quantity, price,
                strategy_id, trader_id, portfolio_id,
            ))
            executed_count += 1

        except Exception as e:
            print(f"  ✗ FAILED {action} {ticker}: {e}")
            continue

    conn.commit()
    conn.close()

    print()
    print(f"  ✓ {executed_count} orders executed and logged.")
    print()


if __name__ == "__main__":
    test_orders = [
        {"ticker": "AAPL", "action": "BUY", "quantity": 5, "price": 195.50},
    ]
    route_orders(test_orders)

