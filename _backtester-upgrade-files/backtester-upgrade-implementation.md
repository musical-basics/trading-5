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