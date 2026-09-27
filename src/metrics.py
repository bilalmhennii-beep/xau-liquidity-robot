from __future__ import annotations
import numpy as np
import pandas as pd

def summarize(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0}
    r = trades["r"].astype(float)
    wins = r[r > 0]
    losses = r[r < 0]
    gross_win = wins.sum()
    gross_loss = abs(losses.sum())
    eq = r.cumsum()
    dd = eq - eq.cummax()
    return {
        "trades": int(len(r)),
        "win_rate": float((r > 0).mean()),
        "net_r": float(r.sum()),
        "expectancy_r": float(r.mean()),
        "profit_factor": float(gross_win/gross_loss) if gross_loss else float("inf"),
        "max_drawdown_r": float(dd.min()),
        "median_r": float(r.median()),
        "avg_mfe": float(trades["mfe"].mean()) if "mfe" in trades else np.nan,
        "avg_mae": float(trades["mae"].mean()) if "mae" in trades else np.nan,
    }
