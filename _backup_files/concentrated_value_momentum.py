def concentrated_value_momentum(df: pl.DataFrame) -> pl.DataFrame:
    """
    Concentrated Value Momentum Strategy
    - Combines DCF NPV gap (60%) + 20-day momentum (40%)
    - Top 10% decile long in bull regime, top 10% long + bottom 10% short in bear regime
    - Volatility governors and regime-aware positioning
    """
    
    return (
        df
        # Step 0: Calculate daily return from adj_close since it's not provided
        .with_columns([
            pl.col("adj_close").pct_change().alias("daily_return")
        ])
        # Step 1: Fill nulls in key columns to avoid propagation issues
        .with_columns([
            pl.col("dcf_npv_gap").fill_null(0.0),
            pl.col("daily_return").fill_null(0.0),
            pl.col("spy").fill_null(strategy="forward").fill_null(strategy="backward"),
            pl.col("vix").fill_null(0.0),
            pl.col("vix3m").fill_null(0.0),
        ])
        # Step 2: Calculate 20-day rolling return (momentum component)
        .with_columns([
            pl.col("daily_return")
            .rolling_sum(window_size=20)
            .over("entity_id")
            .alias("return_20d")
            .fill_null(0.0)
        ])
        # Step 3: Calculate SPY 200-day MA for regime detection
        .with_columns([
            pl.col("spy")
            .rolling_mean(window_size=200)
            .over("date")
            .alias("spy_200ma")
            .fill_null(0.0)
        ])
        # Step 4: Determine bull/bear regime
        .with_columns([
            pl.when(pl.col("spy") > pl.col("spy_200ma"))
            .then(1)
            .otherwise(0)
            .alias("bull_regime")
        ])
        # Step 5: Calculate combined score (DCF 60% + momentum 40%)
        .with_columns([
            (pl.col("dcf_npv_gap") * 0.6 + pl.col("return_20d") * 0.4)
            .alias("combined_score")
            .fill_null(0.0)
        ])
        # Step 6: Rank by combined score within each date (for decile assignment)
        .with_columns([
            pl.col("combined_score")
            .rank("ordinal")
            .over("date")
            .cast(pl.Float64)
            .alias("score_rank")
        ])
        # Step 7: Count universe size per date
        .with_columns([
            pl.col("score_rank")
            .max()
            .over("date")
            .cast(pl.Float64)
            .alias("universe_size")
        ])
        # Step 8: Identify top 10% (top decile) and bottom 10% (bottom decile)
        .with_columns([
            pl.col("score_rank").alias("rank_ascending"),
            (pl.col("universe_size") - pl.col("score_rank") + 1.0)
            .alias("rank_descending")
        ])
        .with_columns([
            pl.when(pl.col("rank_descending") <= pl.col("universe_size") * 0.1)
            .then(1)
            .otherwise(0)
            .alias("is_top_decile"),
            pl.when(pl.col("rank_ascending") <= pl.col("universe_size") * 0.1)
            .then(1)
            .otherwise(0)
            .alias("is_bottom_decile")
        ])
        # Step 9: Calculate 20-day rolling volatility for position sizing
        .with_columns([
            pl.col("daily_return")
            .rolling_std(window_size=20)
            .over("entity_id")
            .alias("vol_20d")
            .fill_null(0.01)
        ])
        # Step 10: Apply volatility scaling (reduce size in high-vol names)
        .with_columns([
            (pl.lit(0.12) / pl.col("vol_20d").clip(0.01, None))
            .clip(0.0, 1.0)
            .alias("vol_scalar")
        ])
        # Step 11: Apply VIX regime filters
        .with_columns([
            pl.when(pl.col("vix") > pl.col("vix3m"))
            .then(0.0)  # Backwardation: go to cash
            .when(pl.col("vix") > 30.0)
            .then(0.5)  # VIX > 30: cut positions 50%
            .otherwise(1.0)
            .alias("vix_scalar")
        ])
        # Step 12: Construct base weights per regime
        .with_columns([
            pl.when(pl.col("bull_regime") == 1)
            # BULL REGIME: Long top decile only, equal weight
            .then(
                pl.when(pl.col("is_top_decile") == 1)
                .then(1.0 / (pl.col("universe_size") * 0.1).clip(1.0, None))
                .otherwise(0.0)
            )
            # BEAR REGIME: Long top decile, short bottom decile
            .otherwise(
                pl.when(pl.col("is_top_decile") == 1)
                .then(1.0 / (pl.col("universe_size") * 0.1).clip(1.0, None))
                .when(pl.col("is_bottom_decile") == 1)
                .then(-1.0 / (pl.col("universe_size") * 0.1).clip(1.0, None))
                .otherwise(0.0)
            )
            .alias("base_weight")
        ])
        # Step 13: Apply entry filters (momentum + valuation in bull regime)
        .with_columns([
            pl.when(pl.col("bull_regime") == 1)
            # Bull regime: require dcf_npv_gap > 0.20 AND 20-day return > 0
            .then(
                pl.when((pl.col("dcf_npv_gap") > 0.20) & (pl.col("return_20d") > 0.0))
                .then(pl.col("base_weight"))
                .otherwise(0.0)
            )
            # Bear regime: no additional filters, rely on relative strength
            .otherwise(pl.col("base_weight"))
            .alias("entry_filtered_weight")
        ])
        # Step 14: Apply volatility and VIX scalars to final weight
        .with_columns([
            (pl.col("entry_filtered_weight") * pl.col("vol_scalar") * pl.col("vix_scalar"))
            .alias("raw_weight_concentrated_value_momentum")
        ])
    )