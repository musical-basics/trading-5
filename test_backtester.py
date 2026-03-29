import sys
sys.path.append('_backup_files')
import polars as pl
from src.alpha_lab.lab_backtester import _load_aligned_data
from vix_regime_value_timing import vix_regime_value_timing

def run():
    print("Loading data...")
    df = _load_aligned_data()
    print("Columns available:", df.columns)
    print("Running strategy...")
    result = vix_regime_value_timing(df)
    
    w_cols = [c for c in result.columns if "raw_weight" in c]
    print("Weights returned:", w_cols)
    print(result.select(w_cols).head(5))

if __name__ == "__main__":
    run()
