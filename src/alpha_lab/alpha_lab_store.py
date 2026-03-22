"""
alpha_lab_store.py — Alpha Lab experiment storage via SQLAlchemy (Supabase/Postgres).

Level 5: Migrated from local Parquet files to Supabase Postgres for
persistent, cloud-backed storage of all experiments, metrics, and equity curves.

Equity curves remain in local Parquet (too large for transactional DB rows),
but all experiment metadata lives in postgres.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

import polars as pl

from src.core.database import SessionLocal
from src.core.models import AlphaLabExperiment
from src.config import PROJECT_ROOT
import os

# Equity curves stay local (large columnar data)
EQUITY_CURVES_DIR = os.path.join(PROJECT_ROOT, "data", "alpha_lab", "equity_curves")


def _ensure_dirs():
    os.makedirs(EQUITY_CURVES_DIR, exist_ok=True)


def _experiment_to_dict(exp: AlphaLabExperiment) -> dict:
    """Convert an ORM experiment to a dict matching the old Parquet schema."""
    return {
        "experiment_id": exp.experiment_id,
        "hypothesis": exp.hypothesis,
        "strategy_code": exp.strategy_code,
        "strategy_name": exp.strategy_name,
        "model_tier": exp.model_tier,
        "status": exp.status,
        "created_at": exp.created_at.isoformat() if exp.created_at else None,
        "metrics_json": exp.metrics_json,
        "cost_input_tokens": exp.cost_input_tokens,
        "cost_output_tokens": exp.cost_output_tokens,
        "cost_usd": exp.cost_usd,
        "rationale": exp.rationale,
        "promoted": exp.promoted,
    }


def save_experiment(
    hypothesis: str,
    strategy_code: str,
    strategy_name: str,
    model_tier: str,
    rationale: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
) -> str:
    """Create a new experiment record. Returns experiment_id."""
    eid = str(uuid.uuid4())[:8]

    session = SessionLocal()
    try:
        exp = AlphaLabExperiment(
            experiment_id=eid,
            hypothesis=hypothesis,
            strategy_code=strategy_code,
            strategy_name=strategy_name,
            model_tier=model_tier,
            status="generated",
            rationale=rationale,
            cost_input_tokens=input_tokens,
            cost_output_tokens=output_tokens,
            cost_usd=cost_usd,
        )
        session.add(exp)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return eid


def update_experiment_status(
    experiment_id: str,
    status: str,
    metrics: Optional[dict] = None,
):
    """Update status and optionally metrics for an experiment."""
    session = SessionLocal()
    try:
        exp = session.query(AlphaLabExperiment).filter(
            AlphaLabExperiment.experiment_id == experiment_id
        ).first()
        if exp is None:
            return

        exp.status = status
        if metrics is not None:
            exp.metrics_json = json.dumps(metrics)
        exp.updated_at = datetime.utcnow()

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def list_experiments() -> list[dict]:
    """Return all experiments as a list of dicts, newest first."""
    session = SessionLocal()
    try:
        experiments = (
            session.query(AlphaLabExperiment)
            .order_by(AlphaLabExperiment.created_at.desc())
            .all()
        )
        return [_experiment_to_dict(e) for e in experiments]
    finally:
        session.close()


def get_experiment(experiment_id: str) -> Optional[dict]:
    """Get a single experiment by ID."""
    session = SessionLocal()
    try:
        exp = session.query(AlphaLabExperiment).filter(
            AlphaLabExperiment.experiment_id == experiment_id
        ).first()
        if exp is None:
            return None
        return _experiment_to_dict(exp)
    finally:
        session.close()


def delete_experiment(experiment_id: str) -> bool:
    """Delete an experiment and its equity curve."""
    session = SessionLocal()
    try:
        exp = session.query(AlphaLabExperiment).filter(
            AlphaLabExperiment.experiment_id == experiment_id
        ).first()
        if exp is None:
            return False

        session.delete(exp)
        session.commit()

        # Clean up local equity curve file
        ec_path = os.path.join(EQUITY_CURVES_DIR, f"{experiment_id}.parquet")
        if os.path.exists(ec_path):
            os.remove(ec_path)

        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_experiment_code(experiment_id: str, strategy_code: str):
    """Update the strategy code for an experiment (for human edits or self-healing)."""
    session = SessionLocal()
    try:
        exp = session.query(AlphaLabExperiment).filter(
            AlphaLabExperiment.experiment_id == experiment_id
        ).first()
        if exp is None:
            return

        exp.strategy_code = strategy_code
        exp.status = "generated"
        exp.updated_at = datetime.utcnow()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def save_equity_curve(experiment_id: str, equity_df: pl.DataFrame):
    """Save equity curve data for an experiment (stays local — too large for Postgres rows)."""
    _ensure_dirs()
    path = os.path.join(EQUITY_CURVES_DIR, f"{experiment_id}.parquet")
    equity_df.write_parquet(path)


def get_equity_curve(experiment_id: str) -> Optional[pl.DataFrame]:
    """Load equity curve for an experiment."""
    path = os.path.join(EQUITY_CURVES_DIR, f"{experiment_id}.parquet")
    if not os.path.exists(path):
        return None
    return pl.read_parquet(path)
