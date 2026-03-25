"""
portfolio_rebalancer.py — Level 3 Phase 4: Target Weight Portfolio Rebalancer

Translates target portfolio weights from target_portfolio (risk-adjusted) into
physical buy/sell orders by computing the delta between desired and
actual positions. Applies:
  - Concentration limits (max 10% per stock)
  - Cash buffer (5% minimum cash)
  - Liquidity gating (1% of 30-day ADV max order size)
"""

import sqlite3
import math
import pandas as pd
from datetime import datetime, timedelta
from src.config import (
    DB_PATH, MAX_SINGLE_WEIGHT, CASH_BUFFER, ADV_LOOKBACK, ADV_MAX_PCT
)
from src.pipeline.execution.portfolio_state import get_portfolio_state_by_id
from src.core.database import SessionLocal
from src.core.models import Portfolio, Trader


def extract_portfolio_intents():
    """
    Calculate rebalance orders by comparing target weights against
    current holdings per sub-portfolio. Returns a list of discrete intents.

    Returns:
        list of {ticker, side, quantity, price, target_weight, portfolio_id, trader_id, strategy_id}
    """
    print("=" * 60)
    print("PHASE 4: Hierarchical Portfolio Rebalancer")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    session = SessionLocal()

    # ── Step 1: Load today's target weights ──────────────────
    print("  Loading global target weights...", end=" ")
    targets = pd.read_sql_query("""
        SELECT ticker, target_weight
        FROM target_portfolio
        WHERE date = (SELECT MAX(date) FROM target_portfolio)
          AND target_weight > 0
    """, conn)

    if targets.empty:
        print("⚠ No target portfolio found. Run Phase 3b first.")
        conn.close()
        session.close()
        return []

    latest_date = pd.read_sql_query(
        "SELECT MAX(date) as d FROM target_portfolio", conn
    )["d"].iloc[0]
    print(f"✓ {len(targets)} tickers (date: {latest_date})")

    # ── Step 2: Apply global concentration limits ────────────
    print("  Applying concentration limits...", end=" ")
    targets["target_weight"] = targets["target_weight"].clip(upper=MAX_SINGLE_WEIGHT)

    total_weight = targets["target_weight"].sum()
    max_total = 1.0 - CASH_BUFFER
    if total_weight > max_total:
        scale = max_total / total_weight
        targets["target_weight"] *= scale
        print(f"scaled by {scale:.3f} ", end="")
    print(f"✓ Total weight: {targets['target_weight'].sum():.3f}")

    # ── Step 3: Get current prices ───────────────────────────
    prices = pd.read_sql_query("""
        SELECT ticker, adj_close as price
        FROM daily_bars
        WHERE date = (SELECT MAX(date) FROM daily_bars)
    """, conn)
    price_map = dict(zip(prices["ticker"], prices["price"]))

    # ── Step 4: Extract intents per Portfolio ────────────────
    print("  Calculating sub-portfolio intents...")
    intents = []
    
    portfolios = session.query(Portfolio).all()
    if not portfolios:
        print("  ⚠ No active portfolios found in database.")
    
    for port in portfolios:
        print(f"\n    Portfolio: {port.name} (ID: {port.id})")
        # For now, default to the ML pipeline global targets
        # In the future, this can be filtered by port.strategy_id
        
        total_equity, holdings = get_portfolio_state_by_id(port.id)
        print(f"      Equity=${total_equity:,.2f}, {len(holdings)} positions")
        
        port_intents = []
        for _, row in targets.iterrows():
            ticker = row["ticker"]
            target_weight = row["target_weight"]
            price = price_map.get(ticker)

            if price is None or price <= 0:
                continue

            target_shares = math.floor((total_equity * target_weight) / price)
            current_shares = holdings.get(ticker, {}).get("shares", 0)
            delta = target_shares - current_shares

            if delta == 0:
                continue

            side = "BUY" if delta > 0 else "SELL"
            quantity = abs(delta)

            port_intents.append({
                "ticker": ticker,
                "side": side,
                "quantity": quantity,
                "price": price,
                "target_weight": target_weight,
                "portfolio_id": port.id,
                "trader_id": port.trader_id,
                "strategy_id": port.strategy_id or "default_ml",
            })

        # Liquidate positions not in targets for this portfolio
        target_tickers = set(targets["ticker"].tolist())
        for ticker, info in holdings.items():
            if ticker not in target_tickers and info["shares"] > 0:
                price = price_map.get(ticker, info.get("avg_price", 0))
                port_intents.append({
                    "ticker": ticker,
                    "side": "SELL",
                    "quantity": info["shares"],
                    "price": price,
                    "target_weight": 0.0,
                    "portfolio_id": port.id,
                    "trader_id": port.trader_id,
                    "strategy_id": port.strategy_id or "default_ml",
                })
        
        print(f"      ✓ Generated {len(port_intents)} intent(s)")
        intents.extend(port_intents)

    # ── Step 5: Apply ADV liquidity gating globally ──────────
    if intents:
        print("\n  Applying global ADV liquidity gating...", end=" ")
        gated = 0
        cutoff_date = (datetime.now() - timedelta(days=ADV_LOOKBACK + 10)).strftime("%Y-%m-%d")

        # Group intents by ticker to gate the TOTAL quantity
        # Since we are pacing based on global volume, we need to reduce proportional to intent
        import polars as pl
        intent_df = pl.DataFrame(intents)
        
        if not intent_df.is_empty():
            sum_by_ticker = intent_df.group_by("ticker").agg(pl.col("quantity").sum().alias("total_qty"))
            
            for row in sum_by_ticker.iter_rows(named=True):
                ticker = row["ticker"]
                total_qty = row["total_qty"]
                
                adv_result = pd.read_sql_query("""
                    SELECT AVG(volume) as adv
                    FROM (
                        SELECT volume FROM daily_bars
                        WHERE ticker = ? AND date >= ?
                        ORDER BY date DESC
                        LIMIT ?
                    )
                """, conn, params=(ticker, cutoff_date, ADV_LOOKBACK))

                if not adv_result.empty and adv_result["adv"].iloc[0] is not None:
                    adv = adv_result["adv"].iloc[0]
                    max_trade = math.floor(adv * ADV_MAX_PCT)

                    if total_qty > max_trade and max_trade > 0:
                        # Scale down all intents for this ticker proportionally
                        scale = max_trade / total_qty
                        for intent in intents:
                            if intent["ticker"] == ticker:
                                original = intent["quantity"]
                                intent["quantity"] = math.floor(original * scale)
                                gated += 1
                        print(f"\n    ⚠ {ticker}: global intent {total_qty} → {max_trade} (1% ADV)", end="")

        print(f"\n  ✓ {gated} intent items scaled down")

    # ── Sort: SELLs first ────────────────────────────────────
    intents.sort(key=lambda x: (0 if x["side"] == "SELL" else 1, x["ticker"], x.get("portfolio_id", 0)))

    conn.close()
    session.close()

    # ── Print summary ────────────────────────────────────────
    if intents:
        print()
        print(f"  {'SIDE':<6} {'TICKER':<8} {'QTY':>6} {'PRICE':>10} {'PORTFOLIO':>10}")
        print(f"  {'─' * 6} {'─' * 8} {'─' * 6} {'─' * 10} {'─' * 10}")
        for i in intents:
            print(f"  {i['side']:<6} {i['ticker']:<8} {i['quantity']:>6} "
                  f"${i['price']:>9.2f} {i['portfolio_id']:>10}")
    else:
        print("  ✓ All portfolios already at target. No intents needed.")

    print()
    print(f"  ✓ {len(intents)} discrete intents extracted across all portfolios")
    print()

    return intents


if __name__ == "__main__":
    intents = extract_portfolio_intents()
