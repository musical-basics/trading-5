import polars as pl
from src.alpha_lab.sandbox_executor import execute_strategy

code = """
import polars as pl
import numpy as np

def strategy_test(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(pl.lit(1.0).alias("raw_weight_test"))
"""

df = pl.DataFrame({"entity_id": [1], "date": ["2020-01-01"]})
res, err = execute_strategy(code, df)
if err:
    print("FAILED:", err)
else:
    print("SUCCESS", res.columns)
