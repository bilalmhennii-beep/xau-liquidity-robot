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

    # Equity must start at zero R, and realized P&L must be ordered by
    # trade EXIT time, not by when the signal/zone was discovered.
    # Trades exiting at the same timestamp form one account equity event.
    if "exit" in trades.columns:
        realized = (trades.assign(_realized_r=r)
                    .groupby("exit", sort=True)["_realized_r"].sum())
    else:
        realized = r.reset_index(drop=True)
    equity = pd.concat(
        [pd.Series([0.0]), realized.cumsum().reset_index(drop=True)],
        ignore_index=True,
    )
    dd = equity - equity.cummax()
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
