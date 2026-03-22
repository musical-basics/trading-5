"""
strategy_generator.py — LLM-powered strategy hypothesis generation using Anthropic Claude.

Generates Polars-based strategy code that follows the StrategyFn signature:
    def strategy_name(df: pl.DataFrame) -> pl.DataFrame

Supports three model tiers with cost tracking:
    - haiku:  claude-3-5-haiku-latest  (fast, cheap)
    - sonnet: claude-sonnet-4-20250514   (balanced)
    - opus:   claude-3-opus-latest    (highest quality)
"""

import os
import re
from dataclasses import dataclass

import anthropic

from src.config import PROJECT_ROOT

# ── Model Configuration ─────────────────────────────────────
MODEL_TIERS = {
    "haiku": {
        "model_id": "claude-haiku-4-5-20251001",
        "label": "Haiku (Fast)",
        "input_cost_per_mtok": 1.00,    # $/M input tokens
        "output_cost_per_mtok": 5.00,   # $/M output tokens
    },
    "sonnet": {
        "model_id": "claude-sonnet-4-20250514",
        "label": "Sonnet (Balanced)",
        "input_cost_per_mtok": 3.00,
        "output_cost_per_mtok": 15.00,
    },
    "opus": {
        "model_id": "claude-opus-4-6",
        "label": "Opus (Premium)",
        "input_cost_per_mtok": 15.00,
        "output_cost_per_mtok": 75.00,
    },
}


@dataclass
class StrategyHypothesis:
    name: str
    rationale: str
    code: str
    model_tier: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


SYSTEM_PROMPT = """You are a quantitative strategist generating trading strategies for a backtesting platform.

You must generate a Python function that follows this EXACT signature:

```python
def strategy_name(df: pl.DataFrame) -> pl.DataFrame:
    # Your logic here
    return df.with_columns(...)
```

RULES:
1. The function takes a Polars DataFrame with these available columns:
   - entity_id (int): unique stock identifier
   - ticker (str): stock ticker symbol (e.g. "AAPL", "MSFT", "SPY")
   - date (date): trading date
   - adj_close (float): adjusted close price
   - volume (int): trading volume
   - ev_sales_zscore (float): enterprise value / sales z-score
   - beta_spy (float): beta vs S&P 500
   - beta_tnx (float): beta vs 10Y yield
   - beta_vix (float): beta vs VIX
   - dcf_npv_gap (float): DCF intrinsic value gap (positive = undervalued)
   - total_debt (float): total debt
   - cash (float): cash on balance sheet
   - shares_out (float): shares outstanding
   - revenue (float): quarterly revenue
   - vix (float): VIX index value
   - tnx (float): 10Y Treasury yield

   Available tickers: AAPL, ABBV, ADBE, AMD, AMZN, AVGO, BAC, BRK-B, CMCSA, COST,
   CRM, CSCO, CVX, DHR, DIS, GOOG, GS, HD, INTC, JNJ, JPM, KO, LIN, LLY, LOW,
   MA, MCD, META, MRK, MSFT, NEE, NFLX, NKE, NVDA, ORCL, PEP, PFE, PG, PM, QCOM,
   RTX, SBUX, SPY, TMO, TMUS, TSLA, TXN, UNH, V, VZ, WFC, WMT, XOM

   You can use ticker for ticker-specific strategies, e.g.:
   pl.when(pl.col("ticker") == "AAPL").then(1.0).otherwise(0.0)

2. The function MUST add exactly ONE new column named `raw_weight_{strategy_id}` where strategy_id is a snake_case name
3. Weights should be float values. Positive = long, negative = short, 0 = no position
4. Only use `polars` (imported as `pl`) and `numpy` (imported as `np`) — no other imports
5. The function name must match the strategy_id in the column name
6. The function MUST return the FULL original DataFrame with the weight column ADDED (do NOT select a subset of columns)

CRITICAL POLARS API RULES (you MUST follow these exactly):
- `.fill_null(0)` or `.fill_null(value)` — use literal values, NOT pl.FillNullStrategy
- `.fill_null(strategy="forward")` — use string, NOT pl.FillNullStrategy.FORWARD
- For rolling operations per entity: `pl.col("x").rolling_mean(window_size=60).over("entity_id")` — rolling FIRST, then .over()
- For cross-sectional ranking: `pl.col("x").rank("ordinal").over("date").cast(pl.Float64)` — ALWAYS .cast(pl.Float64) after .rank()
- `.rank()` returns u32 (unsigned int) which CANNOT be negated or subtracted. You MUST cast to Float64 immediately after rank()
- `.count()` also returns u32. Cast to Float64 if using in arithmetic.
- Do NOT use `.over()` BEFORE rolling operations — always chain rolling FIRST, then .over()
- Use `pl.when(...).then(...).otherwise(...)` for conditionals
- Do NOT use `pl.FillNullStrategy` — it does not exist
- `.clip(lower, upper)` uses POSITIONAL args, NOT min_value/max_value kwargs. Example: `.clip(-3.0, 3.0)`
- Avoid `.select()` at the end — return the full df with the weight column added via `.with_columns()`
- NEVER divide by a value that could be zero or near-zero. Always clip the divisor: `/ pl.col("x").clip(0.01, None)` instead of `/ (pl.col("x") + 1e-6)`
- Use `.fill_null(0.0)` BEFORE arithmetic operations on columns that may have nulls

RESPOND in this exact format:
STRATEGY_NAME: snake_case_name
RATIONALE: 1-2 sentence explanation of the hypothesis
CODE:
```python
def snake_case_name(df: pl.DataFrame) -> pl.DataFrame:
    ...
```"""

# ── Style-specific addons ────────────────────────────────────
STYLE_ADDONS = {
    "academic": """

STRATEGY STYLE: Academic / Market-Neutral
- Build diversified, market-neutral long/short strategies
- Use cross-sectional ranking across the entire universe
- Assign weights to all stocks proportional to their signal strength
- Balance long and short sides for dollar neutrality
- Focus on Sharpe ratio and risk-adjusted returns over raw performance
""",
    "hedge_fund": """

STRATEGY STYLE: Hedge Fund / Concentrated Alpha
You MUST follow these hedge fund heuristics:

1. EXTREME CONCENTRATION: Do NOT assign weights to the entire universe.
   Rank stocks by your signal, but ONLY assign positive weights to the Top 10%
   (top decile). Set weight = 0 for everything else. Use:
   `pl.col("signal").rank("ordinal").over("date").cast(pl.Float64)` to get ranks,
   then `pl.col("signal").count().over("date").cast(pl.Float64)` for total count,
   and only assign weight when `rank >= count * 0.9` (top 10%).

2. REGIME-AWARE SHORTING: Do NOT build market-neutral long/short by default.
   Only allow negative weights (shorts) when a macro regime filter is triggered,
   such as SPY closing below its 200-day moving average:
   `pl.col("adj_close").filter(pl.col("ticker")=="SPY").rolling_mean(200).over("date")`.
   If SPY is above its 200-day MA, the strategy must be LONG-ONLY (weights 0.0 to 1.0).

3. MOMENTUM PRESERVATION: Do NOT trim winners just because their valuation
   gets expensive. If a stock has positive 60-day momentum AND is in the top decile,
   keep it. Only exit when momentum turns negative.

4. Weights should range from 0.0 to 1.0 in bull regimes (long-only),
   and can include shorts (-1.0 to 1.0) only in bear regimes.
""",
}


def generate_strategy(
    prompt: str = "",
    model_tier: str = "sonnet",
    strategy_style: str = "academic",
) -> StrategyHypothesis:
    """Generate a strategy hypothesis using Anthropic Claude.

    Args:
        prompt: Optional user guidance for the strategy idea
        model_tier: One of 'haiku', 'sonnet', 'opus'

    Returns:
        StrategyHypothesis with code, rationale, and cost info
    """
    if model_tier not in MODEL_TIERS:
        raise ValueError(f"Unknown model tier: {model_tier}. Use: {list(MODEL_TIERS.keys())}")
    if strategy_style not in STYLE_ADDONS:
        strategy_style = "academic"

    tier = MODEL_TIERS[model_tier]
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in .env.local")

    client = anthropic.Anthropic(api_key=api_key)

    user_msg = prompt if prompt else (
        "Generate an innovative trading strategy that combines at least two different "
        "signals (technical, fundamental, or statistical) in a novel way. "
        "Focus on strategies with clear economic intuition."
    )

    # Compose system prompt with style addon
    full_system_prompt = SYSTEM_PROMPT + STYLE_ADDONS.get(strategy_style, STYLE_ADDONS["academic"])

    response = client.messages.create(
        model=tier["model_id"],
        max_tokens=2000,
        system=full_system_prompt,
        messages=[{"role": "user", "content": user_msg}],
    )

    # Extract response text
    text = response.content[0].text

    # Calculate cost
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_usd = (
        (input_tokens / 1_000_000) * tier["input_cost_per_mtok"]
        + (output_tokens / 1_000_000) * tier["output_cost_per_mtok"]
    )

    # Parse response
    name, rationale, code = _parse_response(text)

    return StrategyHypothesis(
        name=name,
        rationale=rationale,
        code=code,
        model_tier=model_tier,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost_usd, 6),
    )


def _parse_response(text: str) -> tuple[str, str, str]:
    """Parse the structured LLM response into (name, rationale, code)."""
    name = "unnamed_strategy"
    rationale = ""
    code = ""

    # Extract strategy name
    name_match = re.search(r"STRATEGY_NAME:\s*(.+)", text)
    if name_match:
        name = name_match.group(1).strip().lower().replace(" ", "_")

    # Extract rationale
    rationale_match = re.search(r"RATIONALE:\s*(.+?)(?=CODE:|```)", text, re.DOTALL)
    if rationale_match:
        rationale = rationale_match.group(1).strip()

    # Extract code block — try multiple fenced patterns
    for pattern in [
        r"```python\s*\n(.*?)```",    # ```python
        r"```py\s*\n(.*?)```",        # ```py
        r"```\s*\n(.*?)```",          # bare ```
    ]:
        code_match = re.search(pattern, text, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
            break

    # Fallback: find raw function definition (no code fences)
    if not code:
        func_match = re.search(
            r"(def\s+\w+\s*\(df:\s*pl\.DataFrame\).*?)(?=\n\S|\Z)",
            text,
            re.DOTALL,
        )
        if func_match:
            code = func_match.group(1).strip()

    # If still no code, raise so the user gets a clear error
    if not code:
        raise ValueError(
            f"LLM did not return valid strategy code. Raw response:\n{text[:500]}"
        )

    return name, rationale, code


def get_tier_info() -> dict:
    """Return model tier info for the frontend."""
    return {
        tier_id: {
            "label": tier["label"],
            "input_cost_per_mtok": tier["input_cost_per_mtok"],
            "output_cost_per_mtok": tier["output_cost_per_mtok"],
        }
        for tier_id, tier in MODEL_TIERS.items()
    }
