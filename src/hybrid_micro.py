from __future__ import annotations
import os, pandas as pd
from src.data import load_ohlc, build_timeframes
from src.backtest import build_zones

TP=1.0; SL=1.0; SPREAD=0.0; SLIPPAGE=0.05; LOT=1.0; USD_PER_MOVE=100.0
MAX_HOLD=12; MIN_SCORE=80

def confirmed_entry(bars, touch_pos, side):
    # No lookahead: confirmation uses only fully closed bars after the zone touch.
    end=min(touch_pos+6,len(bars)-1)
    for i in range(touch_pos+1,end+1):
        if i<2: continue
        a,b,c=bars.iloc[i-2],bars.iloc[i-1],bars.iloc[i]
        rng=max(c.high-c.low,1e-9)
        body=abs(c.close-c.open)
        if side=="BUY":
            sweep=b.low<a.low and b.close>a.low
            displacement=c.close>c.open and body/rng>=0.55 and c.close>b.high
            micro_fvg=c.low>a.high
            if sweep and displacement: return i, 2 + int(micro_fvg)
        else:
            sweep=b.high>a.high and b.close<a.high
            displacement=c.close<c.open and body/rng>=0.55 and c.close<b.low
            micro_fvg=c.high<a.low
            if sweep and displacement: return i, 2 + int(micro_fvg)
    return None,0

def run(path):
    raw=load_ohlc(path); tfs=build_timeframes(raw); bars=tfs["1m"]; zones=build_zones(tfs)
    rows=[]
    for z in zones:
        if z.score<MIN_SCORE or z.tf=="30m": continue
        future=bars[bars.index>z.created]
        hit=future[(future.low<=z.key)&(future.high>=z.key)]
        if hit.empty: continue
        touch=hit.index[0]; p=bars.index.get_indexer([touch])[0]
        ep,confirm=confirmed_entry(bars,p,z.side)
        if ep is None: continue
        entry_bar=bars.iloc[ep]; entry=float(entry_bar.close)
        # executable-price cost model
        entry += SPREAD/2 if z.side=="BUY" else -SPREAD/2
        tp=entry+TP if z.side=="BUY" else entry-TP
        sl=entry-SL if z.side=="BUY" else entry+SL
        pathbars=bars.iloc[ep+1:min(ep+1+MAX_HOLD,len(bars))]
        outcome=0; exitp=float(pathbars.close.iloc[-1]) if len(pathbars) else entry
        for _,q in pathbars.iterrows():
            if z.side=="BUY":
                if q.low<=sl: outcome=-1; exitp=sl-SLIPPAGE; break
                if q.high>=tp: outcome=1; exitp=tp-SLIPPAGE; break
            else:
                if q.high>=sl: outcome=-1; exitp=sl+SLIPPAGE; break
                if q.low<=tp: outcome=1; exitp=tp+SLIPPAGE; break
        pnl=(exitp-entry)*(1 if z.side=="BUY" else -1)*USD_PER_MOVE*LOT
        rows.append({"time":bars.index[ep],"tf":z.tf,"kind":z.kind,"side":z.side,
                     "score":z.score,"confirmation":confirm,"pnl_usd":pnl,"outcome":outcome})
    out=pd.DataFrame(rows); os.makedirs("results",exist_ok=True); out.to_csv("results/hybrid_trades.csv",index=False)
    if out.empty: print("No hybrid trades"); return out
    closed=out[out.outcome!=0]; wins=closed.pnl_usd[closed.pnl_usd>0].sum(); losses=-closed.pnl_usd[closed.pnl_usd<0].sum()
    eq=out.pnl_usd.cumsum(); dd=eq-eq.cummax()
    print({"trades":len(out),"win_rate":float((closed.pnl_usd>0).mean()) if len(closed) else 0,
           "net_usd":float(out.pnl_usd.sum()),"ending_balance_5k":float(5000+out.pnl_usd.sum()),
           "profit_factor":float(wins/losses) if losses else float("inf"),"max_drawdown_usd":float(dd.min()),
           "tp":TP,"sl":SL,"spread":SPREAD,"slippage":SLIPPAGE})
    return out

if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser(); p.add_argument("csv"); a=p.parse_args(); run(a.csv)
