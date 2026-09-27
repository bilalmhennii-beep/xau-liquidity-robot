from __future__ import annotations
import pandas as pd

def validate(df: pd.DataFrame) -> dict:
    bad_ohlc=((df.high < df.low)|(df.high < df.open)|(df.high < df.close)|(df.low > df.open)|(df.low > df.close)).sum()
    gaps=df.index.to_series().diff().dt.total_seconds().div(60)
    return {
        "rows":len(df),
        "start":str(df.index.min()),
        "end":str(df.index.max()),
        "duplicate_timestamps":int(df.index.duplicated().sum()),
        "bad_ohlc":int(bad_ohlc),
        "median_gap_minutes":float(gaps.median()),
        "large_gaps_over_10m":int((gaps>10).sum()),
    }
