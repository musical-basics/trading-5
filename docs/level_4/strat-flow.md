# Level 4 Strategy Sandbox: Modular Polars WFO

## 1. The Strategy Registry
Testing 12 strategies at once in Pandas takes minutes. The Level 4 architecture treats every strategy as a standalone plug-and-play Polars module (a "Pod"). A strategy is no longer a massive Python class; it is a declarative Polars expression.

```python
# Example: EV/Sales Strategy Definition
def ev_sales_expr() -> pl.Expr:
    return (
        pl.when(pl.col("ev_sales_zscore") < -1.0)
        .then(1.0 / pl.count("entity_id").over("date"))
        .otherwise(0.0)
    ).alias("raw_weight_ev_sales")
```

## 2. Dynamic FastAPI Tournament
To run a tournament of 3 strategies, the UI sends a POST request: `{"strategies": ["ev_sales", "xgboost", "momentum"]}`.
The backtester loads the Polars LazyFrame ONCE. It evaluates all 3 strategy expressions in parallel as new columns. Because of Polars' SIMD vectorization, running 12 strategies takes virtually the same amount of time as running 1.

## 3. Vectorized Friction
Slippage and commissions are no longer calculated by simulating a portfolio day-by-day in a python for loop.

```python
portfolio = portfolio.with_columns([
    pl.col("target_weight").diff().abs().alias("weight_change"),
    (pl.col("weight_change") * SLIPPAGE_BPS).alias("slippage_cost"),
    (pl.col("gross_return") - pl.col("slippage_cost")).alias("net_return")
])
```
This reduces backtest friction calculation from seconds to microseconds.
