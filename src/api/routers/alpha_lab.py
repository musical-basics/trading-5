"""
alpha_lab.py — API endpoints for the Alpha Lab autonomous strategy discovery.

All endpoints are prefixed with /api/alpha-lab/.
Fully isolated from production strategy/portfolio/trader endpoints.
"""

import json
import math
from datetime import date, datetime
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.alpha_lab.strategy_generator import generate_strategy, get_tier_info
from src.alpha_lab.alpha_lab_store import (
    save_experiment,
    list_experiments,
    get_experiment,
    delete_experiment,
    get_equity_curve,
    update_experiment_code,
)
from src.alpha_lab.lab_backtester import run_lab_backtest

router = APIRouter(prefix="/api/alpha-lab", tags=["alpha-lab"])


def _sanitize(obj):
    """Recursively make any object JSON-safe.

    Handles: NaN, Inf, datetime.date, datetime.datetime, numpy scalars.
    """
    if obj is None:
        return None
    # Handle date/datetime → ISO string
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    # Handle floats (including numpy float64)
    if isinstance(obj, (int, bool)):
        return obj
    try:
        # Works for float, np.float64, np.float32, etc.
        if isinstance(obj, float) or hasattr(obj, '__float__'):
            fval = float(obj)
            if math.isnan(fval) or math.isinf(fval):
                return None
            return fval
    except (TypeError, ValueError):
        pass
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, str):
        return obj
    # Fallback: convert to string
    try:
        return str(obj)
    except Exception:
        return None


def _safe_response(data):
    """Return a JSONResponse with all values sanitized for JSON."""
    return JSONResponse(content=_sanitize(data))


@router.get("/tiers")
async def get_model_tiers():
    """Return available model tiers and their pricing."""
    return get_tier_info()


@router.post("/generate")
async def generate_new_strategy(
    prompt: str = "",
    model_tier: str = "sonnet",
    strategy_style: str = "academic",
):
    """Generate a new strategy hypothesis using the LLM.

    Returns the generated experiment details including code, rationale, and cost.
    """
    try:
        hypothesis = generate_strategy(prompt=prompt, model_tier=model_tier, strategy_style=strategy_style)

        # Save to store
        experiment_id = save_experiment(
            hypothesis=prompt or "(auto-generated)",
            strategy_code=hypothesis.code,
            strategy_name=hypothesis.name,
            model_tier=model_tier,
            rationale=hypothesis.rationale,
            input_tokens=hypothesis.input_tokens,
            output_tokens=hypothesis.output_tokens,
            cost_usd=hypothesis.cost_usd,
        )

        return _safe_response({
            "experiment_id": experiment_id,
            "strategy_name": hypothesis.name,
            "rationale": hypothesis.rationale,
            "code": hypothesis.code,
            "model_tier": model_tier,
            "input_tokens": hypothesis.input_tokens,
            "output_tokens": hypothesis.output_tokens,
            "cost_usd": hypothesis.cost_usd,
        })
    except ValueError as e:
        return _safe_response({"error": str(e)})
    except Exception as e:
        return _safe_response({"error": f"Generation failed: {type(e).__name__}: {e}"})


@router.patch("/{experiment_id}/code")
async def update_code(experiment_id: str, code: str):
    """Update the strategy code for an experiment (human edits)."""
    exp = get_experiment(experiment_id)
    if not exp:
        return _safe_response({"error": f"Experiment {experiment_id} not found"})
    update_experiment_code(experiment_id, code)
    return _safe_response({"ok": True, "experiment_id": experiment_id})


@router.post("/{experiment_id}/backtest")
async def backtest_experiment(experiment_id: str):
    """Run a backtest for an existing experiment (works on any status)."""
    exp = get_experiment(experiment_id)
    if not exp:
        return _safe_response({"error": f"Experiment {experiment_id} not found"})

    result = run_lab_backtest(
        experiment_id=experiment_id,
        strategy_code=exp["strategy_code"],
    )

    return _safe_response(result)


@router.get("/experiments")
async def list_all_experiments():
    """List all experiments, newest first."""
    experiments = list_experiments()
    # Parse metrics_json for each experiment
    for exp in experiments:
        if exp.get("metrics_json"):
            try:
                exp["metrics"] = json.loads(exp["metrics_json"])
            except (json.JSONDecodeError, TypeError):
                exp["metrics"] = None
        else:
            exp["metrics"] = None
    return _safe_response(experiments)


@router.get("/{experiment_id}")
async def get_experiment_detail(experiment_id: str):
    """Get full experiment details including equity curve."""
    exp = get_experiment(experiment_id)
    if not exp:
        return _safe_response({"error": f"Experiment {experiment_id} not found"})

    # Parse metrics
    if exp.get("metrics_json"):
        try:
            exp["metrics"] = json.loads(exp["metrics_json"])
        except (json.JSONDecodeError, TypeError):
            exp["metrics"] = None
    else:
        exp["metrics"] = None

    # Load equity curve if available
    ec = get_equity_curve(experiment_id)
    if ec is not None:
        exp["equity_curve"] = ec.select(["date", "daily_return", "equity"]).to_dicts()
    else:
        exp["equity_curve"] = None

    return _safe_response(exp)


@router.delete("/{experiment_id}")
async def delete_experiment_endpoint(experiment_id: str):
    """Delete an experiment and its data."""
    success = delete_experiment(experiment_id)
    return _safe_response({"deleted": success})
