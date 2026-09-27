from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass
class Zone:
    created: pd.Timestamp
    tf: str
    side: str
    kind: str
    low: float
    high: float
    key: float
    score: float
    atr: float

def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df.close.shift(1)
    tr = pd.concat([(df.high-df.low), (df.high-pc).abs(), (df.low-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False, min_periods=n).mean()

def detect_fvgs(df: pd.DataFrame, tf: str, min_gap_atr=.12, min_disp_atr=.80) -> list[Zone]:
    a = atr(df)
    out: list[Zone] = []
    for i in range(2, len(df)):
        if not np.isfinite(a.iloc[i]) or a.iloc[i] <= 0:
            continue
        b0, b2 = df.iloc[i-2], df.iloc[i]
        body = abs(b2.close-b2.open)
        if body < min_disp_atr*a.iloc[i]:
            continue
        if b2.low > b0.high:
            lo, hi, side = float(b0.high), float(b2.low), "BUY"
        elif b2.high < b0.low:
            lo, hi, side = float(b2.high), float(b0.low), "SELL"
        else:
            continue
        gap = hi-lo
        if gap < min_gap_atr*a.iloc[i]:
            continue
        quality = min(20.0, 10.0*(gap/a.iloc[i])) + min(15.0, 8.0*(body/a.iloc[i]))
        out.append(Zone(df.index[i], tf, side, "FVG", lo, hi, (lo+hi)/2, 45+quality, float(a.iloc[i])))
    return out

def confirmed_pivots(df: pd.DataFrame, left=3, right=3):
    highs, lows = [], []
    h, l = df.high.to_numpy(), df.low.to_numpy()
    for i in range(left, len(df)-right):
        if h[i] > max(h[i-left:i]) and h[i] >= max(h[i+1:i+right+1]):
            highs.append((df.index[i+right], df.index[i], float(h[i])))
        if l[i] < min(l[i-left:i]) and l[i] <= min(l[i+1:i+right+1]):
            lows.append((df.index[i+right], df.index[i], float(l[i])))
    return highs, lows

def detect_equal_liquidity(df: pd.DataFrame, tf: str, tolerance_atr=.12) -> list[Zone]:
    a = atr(df)
    highs, lows = confirmed_pivots(df)
    out: list[Zone] = []
    for pivots, side in ((lows, "BUY"), (highs, "SELL")):
        for j in range(1, len(pivots)):
            confirm, pivot_time, px = pivots[j]
            _, _, prev = pivots[j-1]
            pos = df.index.get_indexer([pivot_time], method="nearest")[0]
            av = float(a.iloc[pos]) if np.isfinite(a.iloc[pos]) else 0.0
            if av <= 0 or abs(px-prev) > tolerance_atr*av:
                continue
            key=(px+prev)/2
            half=max(0.05, tolerance_atr*av/2)
            out.append(Zone(confirm, tf, side, "EQL", key-half, key+half, key, 62.0, av))
    return out
