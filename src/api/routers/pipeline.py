"""
pipeline.py — Pipeline Trigger API Router

Provides endpoints to trigger data ingestion phases from the UI.
Runs pipeline phases in background threads to avoid blocking the API.
"""

import threading
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline"])

# Track running state to prevent duplicate runs
_pipeline_status = {"running": False, "phase": None, "error": None}


def _run_in_background(phase: str, func):
    """Run a pipeline phase in a background thread."""
    global _pipeline_status
    _pipeline_status = {"running": True, "phase": phase, "error": None}
    try:
        func()
        _pipeline_status = {"running": False, "phase": phase, "error": None}
        logger.info(f"✅ Pipeline phase '{phase}' completed")
    except Exception as e:
        _pipeline_status = {"running": False, "phase": phase, "error": str(e)}
        logger.error(f"❌ Pipeline phase '{phase}' failed: {e}")


@router.get("/status")
def pipeline_status():
    """Get current pipeline run status."""
    return _pipeline_status


@router.post("/run/ingest")
def run_ingest():
    """Phase 1: Ingest market data, fundamentals, and macro factors."""
    if _pipeline_status["running"]:
        return {"ok": False, "error": f"Pipeline already running: {_pipeline_status['phase']}"}

    def _ingest():
        from src.pipeline.data_sources.data_ingestion import ingest
        from src.pipeline.data_sources.macro_ingestion import ingest_macro_factors
        from src.pipeline.data_sources.yfinance.fundamentals import ingest_fundamentals
        ingest()
        ingest_fundamentals()
        ingest_macro_factors()

    thread = threading.Thread(target=_run_in_background, args=("ingest", _ingest))
    thread.daemon = True
    thread.start()

    return {"ok": True, "message": "Ingestion started (market data + fundamentals + macro)"}


@router.post("/run/pipeline")
def run_pipeline():
    """Phases 2-4: Scoring, features, ML, risk."""
    if _pipeline_status["running"]:
        return {"ok": False, "error": f"Pipeline already running: {_pipeline_status['phase']}"}

    def _pipeline():
        from src.pipeline.scoring.factor_betas import compute_factor_betas
        from src.pipeline.scoring.cross_sectional_scoring import compute_cross_sectional_scores
        from src.pipeline.scoring.dynamic_dcf import compute_dynamic_dcf
        from src.pipeline.scoring.ml_feature_assembly import assemble_features
        from src.pipeline.scoring.risk_apt import apply_risk_constraints

        compute_factor_betas()
        compute_cross_sectional_scores()
        compute_dynamic_dcf()
        assemble_features()
        apply_risk_constraints()

    thread = threading.Thread(target=_run_in_background, args=("pipeline", _pipeline))
    thread.daemon = True
    thread.start()

    return {"ok": True, "message": "ECS pipeline started (scoring + features + risk)"}


@router.post("/run/full")
def run_full():
    """Run the complete pipeline: ingest + scoring + ML + risk."""
    if _pipeline_status["running"]:
        return {"ok": False, "error": f"Pipeline already running: {_pipeline_status['phase']}"}

    def _full():
        from src.pipeline.data_sources.data_ingestion import ingest
        from src.pipeline.data_sources.macro_ingestion import ingest_macro_factors
        from src.pipeline.data_sources.yfinance.fundamentals import ingest_fundamentals
        from src.pipeline.scoring.factor_betas import compute_factor_betas
        from src.pipeline.scoring.cross_sectional_scoring import compute_cross_sectional_scores
        from src.pipeline.scoring.dynamic_dcf import compute_dynamic_dcf
        from src.pipeline.scoring.ml_feature_assembly import assemble_features
        from src.pipeline.scoring.risk_apt import apply_risk_constraints

        ingest()
        ingest_fundamentals()
        ingest_macro_factors()
        compute_factor_betas()
        compute_cross_sectional_scores()
        compute_dynamic_dcf()
        assemble_features()
        apply_risk_constraints()

    thread = threading.Thread(target=_run_in_background, args=("full", _full))
    thread.daemon = True
    thread.start()

    return {"ok": True, "message": "Full pipeline started"}
