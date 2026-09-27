from __future__ import annotations
import pandas as pd

def load_ohlc(path: str) -> pd.DataFrame:
    df=pd.read_csv(path)
    df.columns=[str(c).strip().lower() for c in df.columns]
    aliases={"timestamp":"time","date":"time","datetime":"time","tickvol":"volume","tick_volume":"volume"}
    df=df.rename(columns={k:v for k,v in aliases.items() if k in df.columns and v not in df.columns})
    required=["time","open","high","low","close"]
    missing=[c for c in required if c not in df.columns]
    if missing: raise ValueError(f"Missing columns: {missing}")
    raw=df["time"]
    if pd.api.types.is_numeric_dtype(raw):
        m=float(raw.dropna().abs().median())
        unit="ms" if m>1e11 else "s"
        df["time"]=pd.to_datetime(raw,unit=unit,utc=True,errors="coerce")
    else:
        df["time"]=pd.to_datetime(raw,utc=True,errors="coerce")
    for c in ["open","high","low","close","volume"]:
        if c in df.columns: df[c]=pd.to_numeric(df[c],errors="coerce")
    df=df.dropna(subset=required).sort_values("time").drop_duplicates("time").set_index("time")
    return df

def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg={"open":"first","high":"max","low":"min","close":"last"}
    if "volume" in df.columns: agg["volume"]="sum"
    return df.resample(rule,label="left",closed="left").agg(agg).dropna(subset=["open","high","low","close"])

def build_timeframes(df: pd.DataFrame) -> dict[str,pd.DataFrame]:
    rules={"1m":"1min","5m":"5min","30m":"30min","1h":"1h","2h":"2h","3h":"3h","4h":"4h","1D":"1D","1W":"W-MON"}
    return {k:resample_ohlc(df,v) for k,v in rules.items()}
