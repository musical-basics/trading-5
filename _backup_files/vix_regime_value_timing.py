import polars as pl

def vix_regime_value_timing(df: pl.DataFrame) -> pl.DataFrame:
    # STEP 1: Compute SPY 200-day MA and regime
    # SPY is a macro column (same for all stocks on a given date), but we compute from the data
    df = df.with_columns(
        pl.col("spy").rolling_mean(window_size=200).over("entity_id").alias("spy_200d_ma")
    )
    df = df.with_columns(
        (pl.col("spy") >= pl.col("spy_200d_ma")).fill_null(True).alias("bull_regime")
    )

    # STEP 2: VIX term spread and gross exposure scalar
    df = df.with_columns(
        (pl.col("vix3m").fill_null(0.0) - pl.col("vix").fill_null(0.0)).alias("vix_term_spread")
    )

    # Detect backwardation-to-contango transition in last 5 days
    # vix_term_spread was negative, now positive
    df = df.with_columns(
        pl.col("vix_term_spread").shift(1).over("entity_id").alias("vts_lag1"),
        pl.col("vix_term_spread").shift(2).over("entity_id").alias("vts_lag2"),
        pl.col("vix_term_spread").shift(3).over("entity_id").alias("vts_lag3"),
        pl.col("vix_term_spread").shift(4).over("entity_id").alias("vts_lag4"),
        pl.col("vix_term_spread").shift(5).over("entity_id").alias("vts_lag5"),
    )
    df = df.with_columns(
        (
            (pl.col("vix_term_spread") > 0.0) &
            (
                (pl.col("vts_lag1").fill_null(0.0) < 0.0) |
                (pl.col("vts_lag2").fill_null(0.0) < 0.0) |
                (pl.col("vts_lag3").fill_null(0.0) < 0.0) |
                (pl.col("vts_lag4").fill_null(0.0) < 0.0) |
                (pl.col("vts_lag5").fill_null(0.0) < 0.0)
            )
        ).alias("backwardation_flip")
    )

    vix_col = pl.col("vix").fill_null(20.0)
    vts_col = pl.col("vix_term_spread")

    df = df.with_columns(
        pl.when(vix_col > 40.0).then(0.0)
        .when(vix_col > 30.0).then(0.25)
        .when(vix_col > 25.0).then(0.40)
        .when(vix_col > 20.0).then(0.70)
        .when((vix_col <= 20.0) & (vts_col > 0.0)).then(1.00)
        .otherwise(0.70)  # vix <= 20 but term spread <= 0
        .alias("gross_scalar_raw")
    )

    # Apply backwardation flip bonus: multiply by 1.2, cap at 1.0
    df = df.with_columns(
        pl.when(pl.col("backwardation_flip"))
        .then(pl.col("gross_scalar_raw") * 1.20)
        .otherwise(pl.col("gross_scalar_raw"))
        .clip(0.0, 1.0)
        .alias("gross_scalar")
    )

    # STEP 3: Composite Alpha Signal

    # Sub-Signal A: Fundamental Mispricing (40%)
    dcf = pl.col("dcf_npv_gap").fill_null(0.0)
    evz = pl.col("ev_sales_zscore").fill_null(0.0)

    # Enforce fundamental data staleness logic (max 540 days / 18 months)
    stale_mask = (
        pl.col("filing_date").is_null() | 
        ((pl.col("date") - pl.col("filing_date").cast(pl.Date)).dt.total_days() > 540)
    )

    df = df.with_columns(
        pl.when(stale_mask)
        .then(0.0)
        .when((dcf > 0.50) & (evz < -0.50))
        .then(
            (dcf / 4.0 + evz.abs() / 3.0).clip(0.0, 1.0)
        )
        .otherwise(0.0)
        .alias("fundamental_score")
    )

    # Sub-Signal B: Volatility Regime Alignment (30%)
    df = df.with_columns(
        pl.when(pl.col("backwardation_flip"))
        .then(1.0)
        .when(pl.col("vix_term_spread") > 0.0)
        .then((pl.col("vix_term_spread") / 5.0).clip(0.0, 1.0))
        .otherwise(0.0)
        .alias("vol_score")
    )

    # Sub-Signal C: Rate & Quality Filter (20%)
    tnx_col = pl.col("tnx").fill_null(3.0)
    beta_tnx_col = pl.col("beta_tnx").fill_null(0.0)
    ddr = pl.col("dynamic_discount_rate").fill_null(0.15)
    beta_spy_col = pl.col("beta_spy").fill_null(1.0)

    quality_fail = (
        ((tnx_col > 4.0) & (beta_tnx_col <= 0.0)) |
        (ddr > 0.15) |
        (beta_spy_col < 0.5) |
        (beta_spy_col > 1.3)
    )

    df = df.with_columns(
        pl.when(quality_fail)
        .then(0.0)
        .otherwise(
            ((pl.lit(0.15) - ddr) / 0.15).clip(0.0, 1.0)
        )
        .alias("quality_score")
    )

    # Sub-Signal D: Flow Confirmation (10%)
    # 20-day rolling average volume
    df = df.with_columns(
        pl.col("volume").cast(pl.Float64).rolling_mean(window_size=20).over("entity_id").alias("vol_20d_avg")
    )

    # 60-day momentum (price return)
    df = df.with_columns(
        pl.col("adj_close").pct_change(60).over("entity_id").alias("momentum_60d")
    )

    df = df.with_columns(
        pl.when(
            (pl.col("volume").cast(pl.Float64) > 1.5 * pl.col("vol_20d_avg").fill_null(1.0)) &
            (pl.col("momentum_60d").fill_null(0.0) > 0.0)
        )
        .then(1.0)
        .otherwise(0.0)
        .alias("flow_score")
    )

    # Composite alpha = 0.4*A + 0.3*B + 0.2*C + 0.1*D
    df = df.with_columns(
        (
            0.4 * pl.col("fundamental_score") +
            0.3 * pl.col("vol_score") +
            0.2 * pl.col("quality_score") +
            0.1 * pl.col("flow_score")
        ).alias("composite_alpha")
    )

    # STEP 4: Momentum Preservation — top decile stocks with positive 60d momentum are never exited on valuation
    # This is embedded: we rank on composite_alpha but preserve positions with positive momentum
    # Boost composite for stocks with strong positive momentum to prevent exits
    df = df.with_columns(
        pl.when(
            (pl.col("momentum_60d").fill_null(0.0) > 0.0) &
            (pl.col("composite_alpha") > 0.0)
        )
        .then(pl.col("composite_alpha") + 0.01)  # tiny boost to preserve momentum stocks in ranking
        .otherwise(pl.col("composite_alpha"))
        .alias("composite_alpha_adj")
    )

    # STEP 5: Cross-sectional ranking — top decile only
    df = df.with_columns(
        pl.col("composite_alpha_adj").rank("ordinal").over("date").cast(pl.Float64).alias("alpha_rank"),
        pl.col("composite_alpha_adj").count().over("date").cast(pl.Float64).alias("stock_count")
    )

    # Top decile threshold: rank >= count * 0.9
    df = df.with_columns(
        (pl.col("alpha_rank") >= pl.col("stock_count") * 0.9).alias("top_decile")
    )

    # STEP 6: Volatility-adjusted stop loss proxy
    # Calculate daily_return from adj_close if not present
    df = df.with_columns(
        pl.col("adj_close").pct_change(1).over("entity_id").fill_null(0.0).alias("daily_return_calc")
    )

    # 20-day realized volatility
    df = df.with_columns(
        pl.col("daily_return_calc").cast(pl.Float64).rolling_std(window_size=20).over("entity_id").alias("realized_vol_20d")
    )

    # Trailing high over 60 days as proxy for "since entry"
    df = df.with_columns(
        pl.col("adj_close").rolling_max(window_size=60).over("entity_id").alias("trailing_high_60d")
    )

    # Drawdown from trailing high
    df = df.with_columns(
        (
            (pl.col("trailing_high_60d").fill_null(0.0) - pl.col("adj_close").fill_null(0.0))
            / pl.col("trailing_high_60d").fill_null(0.0).clip(0.01, None)
        ).alias("drawdown_from_high")
    )

    # Stop triggered if drawdown > 2.5 * 20-day realized vol
    df = df.with_columns(
        (
            pl.col("drawdown_from_high") > 2.5 * pl.col("realized_vol_20d").fill_null(0.05)
        ).alias("stop_triggered")
    )

    # STEP 7: Assign weights
    # Top decile gets equal weight, scaled by gross_scalar
    # In bear regime, bottom decile can be shorted
    df = df.with_columns(
        (pl.col("alpha_rank") <= pl.col("stock_count") * 0.1).alias("bottom_decile")
    )

    # Count top decile stocks per date for equal weighting
    df = df.with_columns(
        pl.col("top_decile").cast(pl.Float64).sum().over("date").alias("n_top_decile")
    )
    df = df.with_columns(
        pl.col("bottom_decile").cast(pl.Float64).sum().over("date").alias("n_bottom_decile")
    )

    # Equal weight among top decile (long), bottom decile (short in bear)
    # Long weight per stock = 1.0 / n_top_decile (then scaled by gross_scalar)
    # Short weight per stock = -1.0 / n_bottom_decile (then scaled by gross_scalar, bear only)

    long_weight_per = pl.lit(1.0) / pl.col("n_top_decile").clip(1.0, None)
    short_weight_per = pl.lit(-1.0) / pl.col("n_bottom_decile").clip(1.0, None)

    # Apply stop loss: if stop triggered, zero weight
    # Apply momentum preservation: in top decile, if momentum_60d > 0, keep even if fundamental_score is low
    # (already handled by composite_alpha_adj boosting)

    df = df.with_columns(
        pl.when(pl.col("stop_triggered"))
        .then(0.0)
        .when(pl.col("top_decile") & (pl.col("composite_alpha_adj") > 0.0))
        .then(long_weight_per * pl.col("gross_scalar"))
        .when(
            (~pl.col("bull_regime")) &  # bear regime
            pl.col("bottom_decile") &
            (pl.col("composite_alpha_adj") <= 0.0)  # truly weak stocks
        )
        .then(short_weight_per * pl.col("gross_scalar"))
        .otherwise(0.0)
        .alias("raw_weight_vix_regime_value_timing")
    )

    # Clip final weights: bull = [0, 1], bear = [-1, 1]
    df = df.with_columns(
        pl.when(pl.col("bull_regime"))
        .then(pl.col("raw_weight_vix_regime_value_timing").clip(0.0, 1.0))
        .otherwise(pl.col("raw_weight_vix_regime_value_timing").clip(-1.0, 1.0))
        .alias("raw_weight_vix_regime_value_timing")
    )

    # Drop intermediate columns
    drop_cols = [
        "spy_200d_ma", "bull_regime", "vix_term_spread",
        "vts_lag1", "vts_lag2", "vts_lag3", "vts_lag4", "vts_lag5",
        "backwardation_flip", "gross_scalar_raw", "gross_scalar",
        "fundamental_score", "vol_score", "quality_score",
        "vol_20d_avg", "momentum_60d", "flow_score",
        "composite_alpha", "composite_alpha_adj",
        "alpha_rank", "stock_count", "top_decile",
        "realized_vol_20d", "trailing_high_60d", "drawdown_from_high",
        "stop_triggered", "bottom_decile", "n_top_decile", "n_bottom_decile",
        "daily_return_calc"
    ]
    df = df.drop(drop_cols)

    return df