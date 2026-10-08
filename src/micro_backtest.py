from __future__ import annotations
import os
import pandas as pd
from src.data import load_ohlc, build_timeframes
from src.backtest import build_zones

TP_PRICE=1.00
SL_PRICE=1.00
SPREAD_PRICE=0.00
SLIPPAGE_PRICE=0.05
LOT=1.0
USD_PER_1_MOVE_PER_LOT=100.0
MAX_HOLD_BARS=12

def run_micro(path):
    raw=load_ohlc(path); tfs=build_timeframes(raw); bars=tfs["1m"]
    zones=build_zones(tfs)
    rows=[]
    for z in zones:
        if z.score < 70: continue
        available=z.created
        future=bars[bars.index>=available]
        if future.empty: continue
        key=float(z.key)
        side=z.side
        touched=future[(future.low<=key)&(future.high>=key)]
        if touched.empty: continue
        ts=touched.index[0]; pos=bars.index.get_indexer([ts])[0]
        window=bars.iloc[pos+1:min(pos+1+MAX_HOLD_BARS,len(bars))]
        if window.empty: continue
        # Executable entry: buy pays ask; sell hits bid. Spread is explicitly charged once at entry.
        entry=key + SPREAD_PRICE/2 if side=="BUY" else key-SPREAD_PRICE/2
        tp=entry+TP_PRICE if side=="BUY" else entry-TP_PRICE
        sl=entry-SL_PRICE if side=="BUY" else entry+SL_PRICE
        outcome=0
        exit_price=float(window.close.iloc[-1])
        for _,b in window.iterrows():
            # Conservative ambiguity: SL first when both occur in same M1 bar.
            if side=="BUY":
                if b.low<=sl: outcome=-1; exit_price=sl-SLIPPAGE_PRICE; break
                if b.high>=tp: outcome=1; exit_price=tp-SLIPPAGE_PRICE; break
            else:
                if b.high>=sl: outcome=-1; exit_price=sl+SLIPPAGE_PRICE; break
                if b.low<=tp: outcome=1; exit_price=tp+SLIPPAGE_PRICE; break
        pnl=(exit_price-entry)*(1 if side=="BUY" else -1)*USD_PER_1_MOVE_PER_LOT*LOT
        rows.append({"touch":ts,"tf":z.tf,"kind":z.kind,"side":side,"score":z.score,
                     "entry":entry,"tp":tp,"sl":sl,"outcome":outcome,"pnl_usd":pnl})
    out=pd.DataFrame(rows)
    os.makedirs("results",exist_ok=True); out.to_csv("results/micro_trades.csv",index=False)
    if out.empty: print("No micro trades"); return out
    closed=out  # include time-based exits in all metrics
    gross_win=closed.loc[closed.pnl_usd>0,"pnl_usd"].sum()
    gross_loss=-closed.loc[closed.pnl_usd<0,"pnl_usd"].sum()
    eq=pd.concat([pd.Series([0.0]),out.pnl_usd.cumsum().reset_index(drop=True)],ignore_index=True); dd=eq-eq.cummax()
    print({"trades":len(out),"closed":len(closed),"win_rate":float((closed.pnl_usd>0).mean()),
           "net_usd":float(out.pnl_usd.sum()),"avg_usd":float(out.pnl_usd.mean()),
           "profit_factor":float(gross_win/gross_loss) if gross_loss else float("inf"),
           "max_drawdown_usd":float(dd.min()),"tp_price":TP_PRICE,"sl_price":SL_PRICE,
           "spread_price":SPREAD_PRICE,"slippage_price":SLIPPAGE_PRICE,"lot":LOT})
    return out

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(); p.add_argument("csv"); a=p.parse_args(); run_micro(a.csv)
