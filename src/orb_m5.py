"""Research-only NY 5-minute ORB. No broker connection or order placement.

Signals use completed M5 candles; M1 bid bars only approximate execution.
Input timestamps must already be verified UTC. See docs/orb_m5.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

NY = "America/New_York"
FIELDS = ["open", "high", "low", "close", "spread_price"]


@dataclass(frozen=True)
class Settings:
    reward_r: float = 2.0
    slippage_price: float = 0.0
    commission_price: float = 0.0  # round-trip cost in index-price units
    spread_multiplier: float = 1.0

    def __post_init__(self):
        if not all(math.isfinite(v) for v in asdict(self).values()):
            raise ValueError("Settings must be finite")
        if self.reward_r <= 0 or self.spread_multiplier <= 0:
            raise ValueError("Reward and spread multiplier must be positive")
        if self.slippage_price < 0 or self.commission_price < 0:
            raise ValueError("Costs cannot be negative")


def load_bars(path):
    d = pd.read_csv(path)
    if not {"time", *FIELDS}.issubset(d.columns):
        raise ValueError("Required columns: time," + ",".join(FIELDS))
    if pd.api.types.is_numeric_dtype(d.time):
        times = pd.to_datetime(d.time, unit="s", utc=True)
    else:
        times = [pd.Timestamp(v) for v in d.time]
        if any(t.tzinfo is None for t in times):
            raise ValueError("Naive timestamps rejected: supply verified UTC")
        times = pd.to_datetime(times, utc=True)
    d.index = pd.DatetimeIndex(times, name="time")
    d = d[FIELDS].apply(pd.to_numeric, errors="raise").sort_index()
    validate_bars(d)
    return d


def validate_bars(d):
    if d.empty or d.index.tz is None or d.index.hasnans:
        raise ValueError("Nonempty timezone-aware bars required")
    if d.index.has_duplicates or not d.index.is_monotonic_increasing:
        raise ValueError("Bars must be unique and sorted")
    if not (d.index == d.index.floor("min")).all():
        raise ValueError("M1 bar-open timestamps required")
    if not np.isfinite(d[FIELDS].to_numpy()).all():
        raise ValueError("Missing or nonfinite price/spread")
    if (d.spread_price < 0).any() or (d[FIELDS[:4]] <= 0).any().any():
        raise ValueError("Prices must be positive and spreads nonnegative")
    if ((d.high < d[["open", "close", "low"]].max(axis=1)) |
            (d.low > d[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("Invalid OHLC")


def simulate_session(bars, session, cfg):
    """Return (trade, reason). A session is an explicitly approved cash date."""
    start = pd.Timestamp(str(session) + " 09:30", tz=NY).tz_convert("UTC")
    finish = start + pd.Timedelta(minutes=90)
    expected = pd.date_range(start, finish, freq="min")
    # Strict common coverage prevents silently bridging data holes or truncated exits.
    if not expected.isin(bars.index).all():
        return None, "incomplete_0930_1100"
    d = bars.loc[expected].copy()
    opening = d.iloc[:5]
    top, bottom = float(opening.high.max()), float(opening.low.min())
    if top <= bottom:
        return None, "zero_range"
    # Close of 09:35-09:40 is the first eligible signal. Entry < 10:30.
    for minute in range(5, 55, 5):
        close = float(d.close.iloc[minute + 4])
        side = 1 if close > top else -1 if close < bottom else 0
        if not side:
            continue
        entry_i = minute + 5
        first = d.iloc[entry_i]
        spread = float(first.spread_price) * cfg.spread_multiplier
        # Bid-chart levels; buy pays ask, sell enters bid. No fill at signal close.
        entry = float(first.open) + (spread if side == 1 else 0) + side * cfg.slippage_price
        stop = bottom if side == 1 else top
        if (side == 1 and first.open <= stop) or (side == -1 and first.open + spread >= stop):
            return None, "entry_gap_through_stop"
        risk = side * (entry - stop)
        if risk <= 0:
            return None, "invalid_stop"
        target = entry + side * cfg.reward_r * risk
        for j in range(entry_i, 91):
            b = d.iloc[j]
            # Synthetic ask OHLC for short exits; constant spread within each M1 bar.
            quote_shift = float(b.spread_price) * cfg.spread_multiplier if side == -1 else 0
            op, hi, lo = (float(b[k]) + quote_shift for k in ("open", "high", "low"))
            if j == 90:
                fill, reason = op - side * cfg.slippage_price, "TIME"
            elif (side == 1 and op <= stop) or (side == -1 and op >= stop):
                fill, reason = op - side * cfg.slippage_price, "SL_GAP"
            elif (side == 1 and op >= target) or (side == -1 and op <= target):
                fill, reason = target, "TP_GAP"  # no favorable gap improvement
            elif (side == 1 and lo <= stop) or (side == -1 and hi >= stop):
                fill, reason = stop - side * cfg.slippage_price, "SL"
            elif (side == 1 and hi >= target) or (side == -1 and lo <= target):
                fill, reason = target, "TP"
            else:
                continue
            # TP is a resting limit; adverse slippage applies to market/stop orders.
            return {
                "session": str(session), "side": "BUY" if side == 1 else "SELL",
                "range_high": top, "range_low": bottom,
                "signal_close_time": str(d.index[entry_i]),
                "entry_time": str(d.index[entry_i]), "exit_bar_time": str(d.index[j]),
                "entry": entry, "stop": stop, "target": target, "exit": fill,
                "reason": reason, "risk_price": risk,
                "net_r": (side * (fill - entry) - cfg.commission_price) / risk,
            }, "traded"
    return None, "no_breakout"


def backtest(bars, sessions, cfg):
    validate_bars(bars)
    trades, audit = [], []
    for session in sorted(set(sessions)):
        if date.fromisoformat(str(session)).weekday() >= 5:
            raise ValueError("Cash-session list contains a weekend")
        trade, reason = simulate_session(bars, session, cfg)
        audit.append({"session": str(session), "status": reason})
        if trade:
            trades.append(trade)
    return pd.DataFrame(trades), audit


def summarize(trades):
    if trades.empty:
        return {"trades": 0}
    r = trades.sort_values("exit_bar_time").net_r.astype(float)
    equity = pd.Series([0.0, *r.cumsum()])
    gross_loss = float(-r[r < 0].sum())
    return {"trades": len(r), "win_rate": float((r > 0).mean()),
            "net_r": float(r.sum()), "expectancy_r": float(r.mean()),
            "profit_factor": float(r[r > 0].sum()) / gross_loss if gross_loss else None,
            "max_drawdown_r": float((equity - equity.cummax()).min())}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv")
    p.add_argument("--symbol", required=True)
    p.add_argument("--sessions", required=True, help="CSV date column of verified US cash sessions")
    p.add_argument("--slippage-price", type=float, required=True)
    p.add_argument("--commission-price", type=float, required=True)
    p.add_argument("--spread-multiplier", type=float, default=1.0)
    p.add_argument("--reward-r", type=float, default=2.0)
    p.add_argument("--validation-start", type=date.fromisoformat, required=True)
    p.add_argument("--test-start", type=date.fromisoformat, required=True)
    p.add_argument("--out", required=True, help="New output directory; refuses overwrites")
    a = p.parse_args()
    if a.validation_start >= a.test_start:
        p.error("validation-start must precede test-start")
    sessions = [date.fromisoformat(str(s)) for s in pd.read_csv(a.sessions)["date"]]
    if not sessions:
        p.error("Session calendar is empty")
    cfg = Settings(a.reward_r, a.slippage_price, a.commission_price, a.spread_multiplier)
    trades, audit = backtest(load_bars(a.csv), sessions, cfg)
    def partition(s):
        day = date.fromisoformat(str(s))
        return "train" if day < a.validation_start else "validation" if day < a.test_start else "test"
    reports = {}
    if not trades.empty:
        trades["partition"] = trades.session.map(partition)
        trades["symbol"] = a.symbol
    for label in ("train", "validation", "test"):
        part = trades[trades.partition == label] if not trades.empty else trades
        reports[label] = summarize(part)
        reports[label]["sessions_requested"] = sum(partition(s) == label for s in sessions)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    trades.to_csv(out / "trades.csv", index=False)
    pd.DataFrame(audit).to_csv(out / "session_audit.csv", index=False)
    manifest = {"symbol": a.symbol, "settings": asdict(cfg), "reports": reports,
                "validation_start": str(a.validation_start), "test_start": str(a.test_start),
                "data_sha256": hashlib.sha256(Path(a.csv).read_bytes()).hexdigest(),
                "sessions_sha256": hashlib.sha256(Path(a.sessions).read_bytes()).hexdigest(),
                "engine_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "pandas_version": pd.__version__, "numpy_version": np.__version__,
                "status": "research_only; chronological partitions do not prove unseen data"}
    (out / "summary.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(json.dumps(manifest, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
