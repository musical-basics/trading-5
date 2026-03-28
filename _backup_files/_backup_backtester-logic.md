instead i want you to make a full PRD because I want another AI to architect this because this is a major upgrade to our app. i believe that a proper backtesting implementation requires the backtester AI to have knowledge of the entire market data, check the exact trades that went into the strategy's backtest and whether the signals were realistic or not. And the AI needs to make a recommendation:



1) If the error is structural (aka the market data is faulty, or the numbers are being miscalculated due to improper financial numbers or P/L calculation of positions), then that's a HARDCODED issue and needs to be fixed on the entire App level.



2) If the error is backtest-unrealistic (aka survivorship bias, the signal didn't actually exist but the trade went through anyway, or at point-in-time there were other companies that have gone bankrupt and should have gotten the trade instead), then that's a BACKTESTER issue and needs to be fixed on the backtester level.



3) Finally, if the error is strategy specific (aka the strategy is pulling in data that doesn't exist, or making calculations based on future data), then that's a STRATEGY ENGINE issue and needs to be fixed on the alpha labs code (with guardrails for the AI, for example)



Makes sense?

Gemini said
This makes complete sense. You are drawing a hard line between Strategy logic, Engine physics, and Data integrity. By having an independent AI auditor that acts as a "Forensic Accountant"—looking only at the physical trade receipts versus the raw data—you catch leaks at the exact level they occur.

This is a phenomenal architectural pattern. Here is the full Product Requirements Document (PRD) formatted for your AI architect to take over and implement.

PRD: Forensic AI Backtest Auditor
1. Product Overview
Objective: Build an independent AI verification layer (The Auditor) that investigates executed trades from Alpha Lab backtests. The Auditor cross-references trade logs against raw, point-in-time market and fundamental data to ensure the backtest engine is not leaking future data, trading unlistable assets, or mathematically hallucinating P/L.

Core Philosophy: If a strategy manages to cheat, it is the engine's fault. The Auditor grades the integrity of the engine and the data, categorizing failures into three distinct buckets for targeted patching.

2. The Three Error Taxonomies (Audit Outcomes)
The AI Auditor must classify any detected anomaly into one of the following exact categories:

A. Structural Errors (App-Level Fixes)
Definition: The foundational market data is faulty, or the math calculating P/L, portfolio equity, or position sizing is fundamentally broken across the board.

Symptoms:

Stock splits or dividends are not adjusted correctly in the raw market_data.

The backtester calculates a 50% return on a stock that only moved 2%.

Prices in the database do not match historical reality (e.g., decimal placement errors).

Resolution: Hardcoded patch required at the Data Ingestion or Core Math level.

B. Backtest-Unrealistic Errors (Engine-Level Fixes)
Definition: The engine's simulation physics are flawed, allowing a trade to execute in a vacuum that ignores market reality.

Symptoms:

Survivorship Bias: Trading a universe of currently successful stocks while ignoring companies that went bankrupt at that point-in-time.

Liquidity Hallucination: Taking a $1M position in a micro-cap stock that only traded 10,000 shares that day.

Trade Teleportation: Executing a trade on a day the stock was halted or delisted.

Resolution: Patch the Backtesting Engine (e.g., lab_backtester.py) to enforce liquidity gates, slippage, and delisting awareness.

C. Strategy-Specific Errors (Alpha Lab Guardrail Fixes)
Definition: The backtest engine works, the data is accurate, but the specific strategy code manipulated Polars functions to peek into the future or access unauthorized data arrays.

Symptoms:

Lookahead Bias: Strategy uses .shift(-1) or .fill_null(strategy="backward") to buy a stock because it "knows" the price goes up tomorrow.

Earnings Leakage: Strategy trades on fundamental data (e.g., EPS) on the exact quarter-end date, rather than the SEC filing date 45 days later.

Resolution: Patch the sandbox_executor.py or the _DEVELOPER_SYS_PROMPT to add stricter Polars API guardrails and AST (Abstract Syntax Tree) validation.

3. System Architecture & Data Flow
To enable the AI Auditor to perform its job, the backend must generate an "Evidence File" for a sampled subset of trades.

Step 1: Trade Extraction
Currently, the backtester aggregates returns without saving a discrete trade log.

Requirement: Modify run_raw_backtest() in lab_backtester.py to extract a ledger of discrete position changes (e.g., Date, Ticker, Weight_Delta, Execution_Price).

Sampling: Select the top 5 most profitable trades and the 5 highest-weighted trades from the strategy run to minimize token context limits.

Step 2: Evidence File Generation
For each sampled trade on Date T, query DuckDB to build a local context window:

Market Data: Extract T−5 to T+5 rows for the specific ticker from market_data.parquet.

Fundamental Data: Extract the most recent filing_date prior to T from fundamental.parquet.

Step 3: LLM Forensic Analysis
Pass the Trade Log and Evidence File to Claude (Opus or Sonnet) via a strict system prompt instructing it to act as a Forensic Quant Auditor.

Requirement: The LLM must output a structured JSON response detailing Pass/Fail status, the specific Error_Category (1, 2, or 3), and a clear Recommendation.

4. Frontend Implementation
Create a new dedicated workspace for the Auditor.

Navigation: Add a new navItem in dashboard-shell.tsx called "Forensic Auditor" (using a magnifying glass or shield icon).

Component (forensic-auditor.tsx):

Experiment Selector: Dropdown to select any "Passed" strategy from the Alpha Lab.

Audit Trigger: A button to dispatch the Evidence File to the LLM.

Results Dashboard: A visual breakdown categorizing the results into the three taxomonies (Structural, Engine, Strategy).

Trade Inspector: An expandable table showing the specific sampled trades and why the AI flagged them (e.g., "Flagged: Volume on 2023-04-12 was only 500 shares, trade impossible").

