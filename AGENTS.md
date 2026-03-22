# AGENTS.md — QuantPrime Development Protocol

## Overview

This project uses a **role-based development workflow** inspired by specialized
agent teams. Rather than treating the AI as a generic code generator, each phase
of development is approached through a distinct role with specific responsibilities.

All workflows are defined in `.agents/workflows/`.

---

## Roles

| Role | Phase | Responsibility |
|---|---|---|
| **Neo** | Vision | Interpret requirements, write product specs |
| **Morpheus** | Planning | Sprint breakdown, task ordering, risk identification |
| **Architect** | Design | Domain modeling, pattern consistency, reuse |
| **Tank** | Backend | API endpoints, data pipelines, business logic |
| **Switch** | Frontend | Components, styling, navigation, UX |
| **Oracle** | Data/AI | Pipeline validation, numerical sanity, bias checks |
| **Mouse** | Testing | Build verification, endpoint testing, edge cases |
| **Merovingian** | Impact | Dependency analysis, breaking change detection |
| **Niobe** | Security | Secrets management, input validation, CORS |
| **Agent Smith** | Review | Code quality enforcement, checklist compliance |

---

## Workflows

### `/feature-development`
The primary workflow for building new features. Runs through all 10 phases
sequentially: Vision → Planning → Design → Implementation → Data Validation →
Testing → Impact Analysis → Security → Code Review → Wrap-up.

**Trigger**: Any feature request or significant change.

---

## Project Conventions

### Tech Stack
- **Backend**: Python + FastAPI + Polars + DuckDB (parquet-based ECS)
- **Frontend**: Next.js + TypeScript + shadcn/ui + Recharts
- **Data**: Parquet files in `data/components/`, entity-mapped via `entity_map.parquet`
- **Dev server**: `bash start.sh` (runs API + frontend concurrently)

### File Structure
```
src/
├── api/routers/          # FastAPI route handlers
├── core/                 # DuckDB store, migrations, entity map
├── ecs/                  # ECS systems (alignment, tournament, strategies)
├── pipeline/             # Data ingestion and scoring
│   ├── data_sources/     # Provider-specific ingestion (yfinance, EDGAR, etc.)
│   └── scoring/          # Cross-sectional scoring, DCF, factor betas
├── scripts/              # One-off scripts (backfill, migration)
frontend/
├── components/           # React components (one per page/feature)
├── lib/                  # API functions, types, utilities
```

### Rules
1. Always use `pnpm` (not npm) for frontend commands.
2. Push to git after every successful change.
3. Kill dev servers after verification so user can run manually.
4. API keys go in `.env.local` — never hardcode.
5. Never run database migrations without user approval.
6. Document bugs that take 3+ prompts to fix in `/docs/`.
7. When doing a repomix, export `.xml` with a `repomix.config` file.

### Data Flow
```
Market Data (yfinance) → market_data.parquet
Fundamentals (yfinance/EDGAR) → fundamental.parquet
Macro Factors (^VIX, ^TNX, SPY) → macro.parquet
        ↓
Alignment Pipeline (System 2)
  → Z-scores, Betas, DCF → feature.parquet
        ↓
XGBoost WFO (System 3a)
  → Strategy weights → action_intent.parquet
        ↓
Risk APT (System 3b)
  → MCR-adjusted weights → target_portfolio.parquet
```
