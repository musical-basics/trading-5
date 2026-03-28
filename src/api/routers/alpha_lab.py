"""
alpha_lab.py — API endpoints for the Alpha Lab autonomous strategy discovery.

All endpoints are prefixed with /api/alpha-lab/.
Fully isolated from production strategy/portfolio/trader endpoints.
Level 5 additions: /promote endpoint for one-click production promotion.
"""

import json
import math
from datetime import date, datetime
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from src.alpha_lab.strategy_generator import generate_strategy, get_tier_info, combine_strategies
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


@router.get("/aligned-profile")
async def get_aligned_profile():
    """Serves the semantic dictionary and statistical distribution of the feature store.

    Returns {total_rows, features: {col: {dtype, category, description, stats}}}
    from the joined aligned dataset — same data the backtester operates on.
    """
    try:
        from src.alpha_lab.stats_engine import generate_aligned_data_profile
        profile_data = generate_aligned_data_profile()
        if "error" in profile_data:
            return _safe_response({"error": profile_data["error"]})
        return _safe_response(profile_data)
    except Exception as e:
        return _safe_response({"error": f"Failed to generate profile: {e}"})


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
    """Generate a new strategy hypothesis using a single LLM call (1-shot)."""
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


@router.post("/generate-swarm")
async def generate_swarm_strategy(
    prompt: str = "",
    model_tier: str = "sonnet",
    strategy_style: str = "academic",
):
    """Generate a strategy using the 3-agent swarm pipeline:
       Researcher → Risk Manager → Quantitative Developer.
    """
    try:
        from src.alpha_lab.swarm_generator import generate_strategy_swarm
        hypothesis = generate_strategy_swarm(prompt=prompt, model_tier=model_tier, strategy_style=strategy_style)

        experiment_id = save_experiment(
            hypothesis=prompt or "(swarm-generated)",
            strategy_code=hypothesis.code,
            strategy_name=hypothesis.name,
            model_tier=f"swarm/{model_tier}",
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
            "model_tier": f"swarm/{model_tier}",
            "input_tokens": hypothesis.input_tokens,
            "output_tokens": hypothesis.output_tokens,
            "cost_usd": hypothesis.cost_usd,
        })
    except ValueError as e:
        return _safe_response({"error": str(e)})
    except Exception as e:
        return _safe_response({"error": f"Swarm generation failed: {type(e).__name__}: {e}"})

@router.get("/generate-swarm-stream")
async def generate_swarm_strategy_stream(
    prompt: str = "",
    strategy_style: str = "academic",
    agent_tiers: str = "{}", # JSON string
    agent_notes: str = "{}"  # JSON string
):
    """SSE stream for the 3-agent swarm. Yields JSON events per agent step.

    The frontend connects via EventSource or fetch+ReadableStream.
    Closing the connection (Kill button) aborts the generator naturally.
    """
    import asyncio
    import json as _json
    import concurrent.futures
    from src.alpha_lab.swarm_generator import generate_strategy_swarm_stream

    parsed_tiers = _json.loads(agent_tiers)
    parsed_notes = _json.loads(agent_notes)

    gen = generate_strategy_swarm_stream(
        prompt=prompt,
        strategy_style=strategy_style,
        agent_tiers=parsed_tiers,
        agent_notes=parsed_notes,
    )

    async def _async_stream():
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            while True:
                try:
                    chunk = await loop.run_in_executor(executor, next, gen)
                    yield chunk
                except StopIteration:
                    break
        finally:
            executor.shutdown(wait=False)

    return StreamingResponse(
        _async_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/generate-swarm-save")
async def save_swarm_result(
    name: str,
    hypothesis: str,
    rationale: str,
    code: str,
    model_tier: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
):
    """Save a completed swarm result. Called by the frontend after result event."""
    experiment_id = save_experiment(
        hypothesis=hypothesis or "(swarm-generated)",
        strategy_code=code,
        strategy_name=name,
        model_tier=f"swarm/{model_tier}",
        rationale=rationale,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )
    return _safe_response({"experiment_id": experiment_id, "strategy_name": name})


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


# ═══════════════════════════════════════════════════════════════
# LEVEL 5: One-Click Production Promotion
# ═══════════════════════════════════════════════════════════════

CUSTOM_STRATEGIES_DIR = Path("src/ecs/strategies/custom")


@router.post("/{experiment_id}/promote")
async def promote_to_production(experiment_id: str):
    """Promote a passed experiment to production.

    1. Extract successful Python code from the store.
    2. Write it to src/ecs/strategies/custom/generated_{id}.py
    3. The strategy registry auto-discovers it on next startup.
    4. Mark the experiment as promoted.
    """
    exp = get_experiment(experiment_id)
    if not exp:
        return _safe_response({"error": f"Experiment {experiment_id} not found"})
    if exp.get("status") != "passed":
        return _safe_response({"error": "Only passed experiments can be promoted"})

    # Ensure custom directory exists
    CUSTOM_STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)

    # Write the strategy file
    strategy_name = exp.get("strategy_name", f"strategy_{experiment_id}")
    safe_id = experiment_id.replace("-", "_")
    filename = f"generated_{safe_id}.py"
    filepath = CUSTOM_STRATEGIES_DIR / filename

    # Parse metrics for the docstring
    metrics_str = "N/A"
    if exp.get("metrics_json"):
        try:
            metrics = json.loads(exp["metrics_json"]) if isinstance(exp["metrics_json"], str) else exp["metrics_json"]
            metrics_str = f"Sharpe: {metrics.get('sharpe', 'N/A')}"
        except (json.JSONDecodeError, TypeError):
            pass

    strategy_module = (
        f'"""\n'
        f'Auto-generated strategy from Alpha Lab experiment #{experiment_id}.\n'
        f'Experiment: {strategy_name}\n'
        f'Metrics: {metrics_str}\n'
        f'"""\n\n'
        f'import polars as pl\n'
        f'import numpy as np\n\n'
        f'STRATEGY_ID = "alphalab_{safe_id}"\n'
        f'STRATEGY_NAME = "{strategy_name}"\n\n'
        f'{exp["strategy_code"]}\n'
    )

    filepath.write_text(strategy_module)

    # Publish promotion event via Redis (for WebSocket broadcast)
    try:
        import redis as _redis
        from src.config import REDIS_URL
        r = _redis.from_url(REDIS_URL)
        r.publish("system_events", json.dumps({
            "event_type": "strategy_promoted",
            "payload": {
                "experiment_id": experiment_id,
                "strategy_id": f"alphalab_{safe_id}",
                "strategy_name": strategy_name,
            },
        }))
    except Exception:
        pass  # Redis not available — non-critical

    return _safe_response({
        "status": "promoted",
        "strategy_id": f"alphalab_{safe_id}",
        "file": str(filepath),
    })


# ═══════════════════════════════════════════════════════════════
# LEVEL 5: Combine / Evolve Strategies (Manual Genetic Prompting)
# ═══════════════════════════════════════════════════════════════

@router.post("/combine")
async def combine_experiments(
    experiment_ids: str,
    model_tier: str = "sonnet",
    guidance: str = "",
):
    """Combine multiple passed strategies into a new evolved strategy.

    experiment_ids: comma-separated experiment IDs to combine
    model_tier: LLM tier to use
    guidance: optional user guidance for the combination
    """
    ids = [eid.strip() for eid in experiment_ids.split(",") if eid.strip()]

    if len(ids) < 2:
        return _safe_response({"error": "Select at least 2 strategies to combine"})
    if len(ids) > 5:
        return _safe_response({"error": "Maximum 5 strategies can be combined"})

    # Fetch experiments and validate they're all passed
    strategy_codes = []
    strategy_names = []
    for eid in ids:
        exp = get_experiment(eid)
        if not exp:
            return _safe_response({"error": f"Experiment {eid} not found"})
        if exp.get("status") != "passed":
            return _safe_response({"error": f"Experiment '{exp.get('strategy_name', eid)}' has not passed backtesting"})
        strategy_codes.append(exp["strategy_code"])
        strategy_names.append(exp.get("strategy_name", eid))

    try:
        hypothesis = combine_strategies(
            strategy_codes=strategy_codes,
            strategy_names=strategy_names,
            model_tier=model_tier,
            user_guidance=guidance,
        )

        experiment_id = save_experiment(
            hypothesis=f"Combined from: {', '.join(strategy_names)}",
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
            "parent_strategies": strategy_names,
            "input_tokens": hypothesis.input_tokens,
            "output_tokens": hypothesis.output_tokens,
            "cost_usd": hypothesis.cost_usd,
        })
    except ValueError as e:
        return _safe_response({"error": str(e)})
    except Exception as e:
        return _safe_response({"error": f"Combine failed: {type(e).__name__}: {e}"})
