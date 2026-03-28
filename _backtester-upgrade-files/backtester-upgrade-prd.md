Here is a complete, architect-level Product Requirements Document (PRD) and Implementation Masterplan designed specifically for you to hand off to your AI coding agent (e.g., Cursor, Windsurf, Devin).

It bridges your conceptual framework with the exact files, data structures, and Polars/React paradigms of the QuantPrime (Level 5) codebase. You can copy and paste everything below the line directly to your AI.

📜 PRD: Forensic AI Backtest Auditor (QuantPrime Level 5.5)
1. Product Overview
Objective: Build an independent "Glass Box" AI auditing layer that forensically investigates executed trades from Alpha Lab backtests. It will cross-reference discrete trade logs against raw, point-in-time data to verify if a strategy is mathematically sound, physically realistic, and free of lookahead bias.

Core Philosophy: The AI Auditor acts as a Forensic Accountant. By grading backtests into three strict taxonomies, it explicitly tells the developer where the leak is occurring so it can be patched at the correct level of the stack.

2. The Error Taxonomy (Classification Rules)
The LLM acting as the Auditor will evaluate the extracted evidence against these strict definitions and make targeted recommendations:

A. Structural Errors (App-Level Data/Math Issues)
Definition: The underlying pipeline data (market_data.parquet, fundamental.parquet) is corrupted, or the portfolio accounting math is fundamentally broken.

Signatures to look for:

Stock splits/dividends unadjusted (price drops 50% overnight with no split adjustment).

Portfolio total equity calculation ignores cash drag or miscalculates aggregate P/L.

Prices reflect decimal errors or null-propagating infinities.

Resolution Recommendation: Hardcoded patch required in Data Ingestion (src/pipeline/data_sources/) or ECS Alignment (src/ecs/alignment_system.py).

B. Backtest-Unrealistic Errors (Backtester-Level Physics Issues)
Definition: The engine's simulation allowed a trade that violates market reality.

Signatures to look for:

Survivorship Bias: Executing trades on a day the stock had 0 volume, was halted, or the company had gone bankrupt but remained in the dataset.

Liquidity Hallucination: Taking a position where target_shares > volume * 0.01 (trading more than the day's actual volume).

Frictionless Vacuum: Achieving high Sharpe through micro-trades without paying the SLIPPAGE_BPS penalty.

Resolution Recommendation: Patch the Backtesting Engine (src/alpha_lab/lab_backtester.py) to enforce liquidity gates, delisting awareness, and strict slippage.

C. Strategy-Specific Errors (Alpha Lab / Strategy Engine Issues)
Definition: The backtest engine and data are fine, but the specific Polars strategy code cheated or hallucinated.

Signatures to look for:

Lookahead Bias: Strategy uses .shift(-1) or strategy="backward" in .fill_null() to "peek" into the future.

Earnings Leakage: Strategy trades on fundamental data (e.g., revenue) on the exact quarter-end date, rather than the SEC filing_date (45 days later).

Hallucinated Data: Pulling in columns or data sources that simply don't exist in the data dictionary.

Resolution Recommendation: Reject the strategy, update the LLM System Prompts (src/alpha_lab/swarm_generator.py), and add stricter Polars AST guardrails to the sandbox (src/alpha_lab/sandbox_executor.py).

3. Backend Engineering Plan (Python / FastAPI / Polars)
Step 3.1: Trade Ledger Extraction
Currently, run_raw_backtest in src/alpha_lab/lab_backtester.py calculates portfolio equity but discards the exact ticker-level positions entered into.

Action: Modify the Polars pipeline in run_raw_backtest() to calculate weight_delta (current day's normalized weight minus previous day's weight per ticker).

Python
# After calculating `_norm_weight` per entity:
# weight_delta = _norm_weight - _norm_weight.shift(1).over("entity_id")
Action: Extract rows where abs(weight_delta) > 0.001. Join this with market_data (adj_close, volume) and entity_map.parquet (ticker) to produce a discrete trade_ledger.

Storage: Update src/alpha_lab/alpha_lab_store.py to save this trade ledger as trades_{experiment_id}.parquet alongside the existing equity curves.

Step 3.2: Evidence Compiler
Create a new module: src/alpha_lab/forensic_auditor.py.

Action: Write a function generate_evidence_file(experiment_id).

Sampling: To fit LLM context limits, sort the trade_ledger and sample the Top 5 most profitable trades (highest PnL contribution) and Top 5 largest allocation changes (highest absolute weight_delta).

Context Assembly: For each sampled trade on Date T for Ticker X, query DuckDB to build a local context window:

Market Context: Extract T−5 to T+5 rows for Ticker X from market_data.parquet (proves price continuity and volume existence).

Fundamental Context: Extract the most recent row prior to T from fundamental.parquet (proves no earnings lookahead).

Step 3.3: LLM Forensic Integration
In src/alpha_lab/forensic_auditor.py, write run_forensic_audit(experiment_id).

Action: Use anthropic.Anthropic to call claude-3-5-sonnet-latest (or Opus).

Prompt: Supply the taxonomy definitions from Section 2, the Strategy Code, the Sampled Trades, and the Evidence File.

Output: Force structured JSON output from the LLM:

JSON
{
  "status": "PASS" | "FAIL" | "WARNING",
  "error_category": "STRUCTURAL" | "BACKTEST" | "STRATEGY" | "NONE",
  "confidence": 0.95,
  "flagged_trades": [{"ticker": "AAPL", "date": "2023-01-05", "reason": "Traded 500% of daily volume. Liquidity hallucination."}],
  "recommendation": "Implement ADV liquidity gating in lab_backtester.py"
}
Step 3.4: Database & API Updates
Action: Update src/core/models.py (AlphaLabExperiment) and src/scripts/supabase_schema.sql. Add:

audit_status (VARCHAR)

audit_report_json (TEXT)

Action: Update src/alpha_lab/alpha_lab_store.py to save/retrieve these new fields.

Action: In src/api/routers/alpha_lab.py, add a new endpoint: POST /api/alpha-lab/{experiment_id}/audit. This triggers run_forensic_audit and saves/returns the JSON report. Add GET /api/alpha-lab/{experiment_id}/trades to return the raw ledger for the UI.

4. Frontend Engineering Plan (Next.js / React)
Step 4.1: Navigation & Routing
Action: In frontend/components/dashboard-shell.tsx, add a new navItem:

TypeScript
{
  id: "forensic-auditor",
  label: "Forensic Auditor",
  icon: ShieldAlert, // from lucide-react
  description: "AI Strategy Verification",
  badge: "Audit"
}
Step 4.2: Build forensic-auditor.tsx
Create frontend/components/forensic-auditor.tsx. It requires 4 main sections:

Experiment Selector: A dropdown populating from fetchAlphaExperiments() filtering for status === "passed".

Audit Trigger Bar: A prominent button "Run Forensic Audit 🔎". Shows a loading spinner while the LLM processes the evidence.

Verdict Dashboard (The Taxonomy):

Create three distinct visual cards for Structural, Backtest, and Strategy.

If the audit fails, highlight the specific category card in Red/Amber and display the LLM's recommendation alert box.

Trade Inspector (The Receipts): A shadcn/ui <Table> displaying the sampled trades.

Columns: Date, Ticker, Action (BUY/SELL), Weight Delta, Price, Volume, AI Flag.

Highlight rows that the AI flagged in its flagged_trades JSON array. Add an expandable accordion to show the T−5 to T+5 market evidence so the human user can visually verify the AI's claim.

Step 4.3: Update API Client
Action: In frontend/lib/api.ts, add the corresponding typings for AuditReport and the fetcher functions: runForensicAudit(experimentId: string) and fetchExperimentTrades(experimentId: string).

5. Execution Directives for the AI Agent
(Copy and paste these exact instructions to your coding agent)

System Prompt / Task Directives:
You are upgrading the QuantPrime trading platform to Level 5.5. Read the PRD for the Forensic AI Backtest Auditor. We need to implement this strictly following the 4 technical phases below. Do not alter the core financial matrix math (risk_apt.py, dynamic_dcf.py)—you are building a read-only audit layer on top of the existing pipeline.

Phase 1: Database & Storage

Update src/core/models.py and src/scripts/supabase_schema.sql with audit_status (String) and audit_report_json (Text).

Update src/alpha_lab/alpha_lab_store.py to support saving and retrieving trades_{experiment_id}.parquet alongside equity curves.

Phase 2: Trade Extraction

Modify src/alpha_lab/lab_backtester.py (run_raw_backtest). After _norm_weight is calculated, compute the weight_delta using Polars .shift(1).over("entity_id"). Extract the unaggregated positions (filtering out < 0.001 deltas) and join the ticker from entity_map.parquet and adj_close/volume from market_data.parquet. Save this ledger via the store. Ensure this does not break the existing _compute_metrics portfolio aggregation.

Phase 3: The Auditor Engine

Create src/alpha_lab/forensic_auditor.py. Write the sampling logic (top 10 trades), the DuckDB evidence compiler (T−5 to T+5), and the Anthropic Claude API call enforcing the JSON schema and the 3 error taxonomies defined in the PRD.

Add the POST /{experiment_id}/audit and GET /{experiment_id}/trades endpoints in src/api/routers/alpha_lab.py.

Phase 4: Frontend

Update frontend/lib/api.ts with the new endpoints and TypeScript types.

Build frontend/components/forensic-auditor.tsx matching the UI specs, and add it to dashboard-shell.tsx.