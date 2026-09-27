from __future__ import annotations
import pandas as pd

REQUIRED = ["time", "open", "high", "low", "close"]

def load_ohlc(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time").drop_duplicates("time").set_index("time")
    for c in ["open", "high", "low", "close", "volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["open", "high", "low", "close"])

def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df.columns:
        agg["volume"] = "sum"
    return df.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open", "high", "low", "close"])

def build_timeframes(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    rules = {
        "1m": "1min", "5m": "5min", "30m": "30min", "1h": "1h",
        "2h": "2h", "3h": "3h", "4h": "4h", "1D": "1D", "1W": "W-MON",
    }
    return {name: resample_ohlc(df, rule) for name, rule in rules.items()}
