"""
main.py — Level 3 Neurosymbolic Pod: CLI Pipeline Runner

Orchestrates all phases sequentially:
  Phase 0:  Database Initialization
  Phase 1a: EOD Price Ingestion (yfinance → SQLite)
  Phase 1b: Quarterly Fundamental Ingestion (yfinance → SQLite)
  Phase 1c: Macro Factor Ingestion (VIX, 10Y Yield, SPY)
  Phase 2A: Rolling OLS Factor Betas (Return APT)
  Phase 2B: Cross-Sectional Scoring (EV/Sales Z-scores)
  Phase 2C: Dynamic DCF Valuations
  Phase 2D: ML Feature Assembly
  Phase 3a: XGBoost Walk-Forward Optimization
  Phase 3b: Risk APT (Covariance + MCR Scaling)
  Phase 4:  Squeeze Filter + Execution Reconciliation

Run with: python3 main.py
"""

import sys
import os
from datetime import datetime

# Ensure project root is on the path so src imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import (
    db_init,
    data_ingestion,
    macro_ingestion,
    fundamental_ingestion,
    cross_sectional_scoring,
    factor_betas,
    dynamic_dcf,
    ml_feature_assembly,
    xgb_wfo_engine,
    risk_apt,
    squeeze_filter,
    wfo_backtester,
    portfolio_rebalancer,
    execution,
)


def main():
    start_time = datetime.now()

    print()
    print("╔" + "═" * 58 + "╗")
    print("║  LEVEL 3 — NEUROSYMBOLIC POD PIPELINE                   ║")
    print("║  Started: " + start_time.strftime("%Y-%m-%d %H:%M:%S") + " " * 27 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    # Phase 0: Initialize Database
    db_init.init_db()

    # Phase 1a: Ingest EOD prices
    data_ingestion.ingest()

    # Phase 1b: Ingest quarterly fundamentals
    fundamental_ingestion.ingest_fundamentals()

    # Phase 1c: Ingest macro factors (VIX, 10Y Yield, SPY)
    macro_ingestion.ingest_macro_factors()

    # Phase 2A: Compute rolling factor betas (Return APT)
    factor_betas.compute_factor_betas()

    # Phase 2B: Compute cross-sectional EV/Sales Z-scores
    cross_sectional_scoring.compute_cross_sectional_scores()

    # Phase 2C: Compute Dynamic DCF valuations
    dynamic_dcf.compute_dynamic_dcf()

    # Phase 2D: Assemble ML features (merge all scores + labels)
    ml_feature_assembly.assemble_features()

    # Phase 3a: XGBoost Walk-Forward Optimization
    xgb_wfo_engine.run_xgb_wfo()

    # Phase 3b: Risk APT — Variance-constrained weight scaling
    risk_apt.apply_risk_constraints()

    # Phase 4: Squeeze Filter (Bouncer Defense)
    squeeze_filter.apply_squeeze_filter()

    # Phase 3 (Legacy): Walk-Forward Optimization tournament
    wfo_backtester.run_wfo_tournament()

    # Phase 4: Portfolio rebalance → execution
    orders = portfolio_rebalancer.rebalance_portfolio()
    execution.route_orders(orders)

    # Done
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    print()
    print("╔" + "═" * 58 + "╗")
    print("║  PIPELINE COMPLETE                                      ║")
    print("║  Finished: " + end_time.strftime("%Y-%m-%d %H:%M:%S") + " " * 26 + "║")
    print(f"║  Elapsed: {elapsed:.1f}s" + " " * (47 - len(f"{elapsed:.1f}s")) + "║")
    print("╚" + "═" * 58 + "╝")
    print()


if __name__ == "__main__":
    main()
