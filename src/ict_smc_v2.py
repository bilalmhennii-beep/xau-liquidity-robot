from __future__ import annotations
import os, pandas as pd
from src.data import load_ohlc, build_timeframes

TP=1.0; SL=1.0; SLIPPAGE=.05; USD_PER_MOVE=100.0; START=5000.0
SWING=3; MAX_HOLD=15

def pivots(d):
    h=d.high; l=d.low
    ph=(h.shift(SWING)<h)&(h.shift(-SWING)<h)
    pl=(l.shift(SWING)>l)&(l.shift(-SWING)>l)
    return ph.fillna(False),pl.fillna(False)

def signals(d):
    ph,pl=pivots(d); out=[]
    last_hi=last_lo=None
    # pivot is usable only SWING bars after its center -> avoids lookahead
    for i in range(2*SWING+2,len(d)-MAX_HOLD-1):
        confirmed=i-SWING
        if ph.iloc[confirmed]: last_hi=float(d.high.iloc[confirmed])
        if pl.iloc[confirmed]: last_lo=float(d.low.iloc[confirmed])
        if last_hi is None or last_lo is None: continue
        a,b,c=d.iloc[i-2],d.iloc[i-1],d.iloc[i]
        rng=max(float(c.high-c.low),1e-9); body=abs(float(c.close-c.open))
        disp=body/rng>=.60
        mid=(last_hi+last_lo)/2
        # ICT/SMC: external liquidity sweep + reclaim + displacement/MSS proxy + premium/discount
        long_sweep=b.low<last_lo and b.close>last_lo
        short_sweep=b.high>last_hi and b.close<last_hi
        long_mss=c.close>b.high and c.close>c.open and disp
        short_mss=c.close<b.low and c.close<c.open and disp
        long_fvg=c.low>a.high
        short_fvg=c.high<a.low
        if long_sweep and long_mss and c.close<=mid:
            out.append((i,"BUY",3+int(long_fvg)))
        elif short_sweep and short_mss and c.close>=mid:
            out.append((i,"SELL",3+int(short_fvg)))
    return out

def run(path):
    raw=load_ohlc(path); d=build_timeframes(raw)["1m"]; rows=[]
    for i,side,score in signals(d):
        entry=float(d.close.iloc[i]); tp=entry+TP if side=="BUY" else entry-TP; sl=entry-SL if side=="BUY" else entry+SL
        exitp=entry; outcome=0
        for _,q in d.iloc[i+1:i+1+MAX_HOLD].iterrows():
            if side=="BUY":
                if q.low<=sl: exitp=sl-SLIPPAGE; outcome=-1; break
                if q.high>=tp: exitp=tp-SLIPPAGE; outcome=1; break
            else:
                if q.high>=sl: exitp=sl+SLIPPAGE; outcome=-1; break
                if q.low<=tp: exitp=tp+SLIPPAGE; outcome=1; break
        if outcome==0:
            q=d.iloc[min(i+MAX_HOLD,len(d)-1)]; exitp=float(q.close)
        pnl=(exitp-entry)*(1 if side=="BUY" else -1)*USD_PER_MOVE
        rows.append({"time":d.index[i],"side":side,"score":score,"pnl_usd":pnl,"outcome":outcome})
    x=pd.DataFrame(rows); os.makedirs("results",exist_ok=True); x.to_csv("results/ict_smc_v2.csv",index=False)
    if x.empty: print("No ICT/SMC trades"); return x
    closed=x[x.outcome!=0]; wins=closed[closed.pnl_usd>0].pnl_usd.sum(); losses=-closed[closed.pnl_usd<0].pnl_usd.sum()
    eq=START+x.pnl_usd.cumsum(); peak=eq.cummax(); dd=eq-peak
    print({"trades":len(x),"win_rate":float((closed.pnl_usd>0).mean()) if len(closed) else 0,
      "net_usd":float(x.pnl_usd.sum()),"ending_balance":float(START+x.pnl_usd.sum()),
      "profit_factor":float(wins/losses) if losses else float("inf"),"max_dd_usd":float(dd.min()),
      "model":"ICT_SMC_V2","tp":TP,"sl":SL,"slippage":SLIPPAGE})
    return x

if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser(); p.add_argument("csv"); a=p.parse_args(); run(a.csv)
