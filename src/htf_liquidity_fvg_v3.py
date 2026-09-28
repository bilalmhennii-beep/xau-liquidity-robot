from __future__ import annotations
import os, pandas as pd, numpy as np
from src.data import load_ohlc, build_timeframes

START=10000.0; LOT=.5; USD_PER_MOVE_PER_LOT=100.0
SLIPPAGE=.05; TARGETS=(1.0,1.5,2.0); SL_MOVE=1.0; MAX_HOLD=48
HTFS=("1h","2h","3h","4h")

def atr(d,n=14):
    pc=d.close.shift(1); tr=pd.concat([(d.high-d.low),(d.high-pc).abs(),(d.low-pc).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

def build_context(tfs, base):
    ctx=pd.DataFrame(index=base.index)
    score=pd.Series(0,index=base.index,dtype=float); direction=pd.Series(0,index=base.index,dtype=float)
    for tf in HTFS:
        h=tfs[tf].copy(); h["atr"]=atr(h)
        # confirmed 3-candle HTF FVGs
        bull=(h.low>h.high.shift(2)) & ((h.low-h.high.shift(2))>=.10*h.atr)
        bear=(h.high<h.low.shift(2)) & ((h.low.shift(2)-h.high)>=.10*h.atr)
        # external liquidity sweep/reclaim proxy on completed HTF candles
        prior_hi=h.high.shift(1).rolling(10).max(); prior_lo=h.low.shift(1).rolling(10).min()
        sweep_up=(h.high>prior_hi)&(h.close<prior_hi)
        sweep_dn=(h.low<prior_lo)&(h.close>prior_lo)
        sig=pd.Series(0,index=h.index,dtype=float)
        sig[bull|sweep_dn]=1; sig[bear|sweep_up]=-1
        # only make HTF state available after candle closes
        delta=pd.to_timedelta(tf)
        avail=pd.DataFrame({"sig":sig.values},index=h.index+delta)
        aligned=avail.reindex(base.index,method="ffill").sig.fillna(0)
        direction+=aligned
        score+=(aligned!=0).astype(float)
    ctx["dir"]=np.sign(direction); ctx["confluence"]=score
    return ctx

def run(path):
    raw=load_ohlc(path); tfs=build_timeframes(raw); d=tfs["1m"].copy(); c=build_context(tfs,d)
    rows=[]; last_trade=-999
    # 1m execution only when >=2 HTFs agree; liquidity sweep + displacement/MSS
    hi20=d.high.shift(1).rolling(20).max(); lo20=d.low.shift(1).rolling(20).min()
    for i in range(25,len(d)-MAX_HOLD-1):
        if i-last_trade<5 or c.confluence.iloc[i]<2 or c.dir.iloc[i]==0: continue
        b=d.iloc[i-1]; q=d.iloc[i]; rng=max(float(q.high-q.low),1e-9); body=abs(float(q.close-q.open))
        if body/rng<.55: continue
        side=None
        if c.dir.iloc[i]>0 and b.low<lo20.iloc[i-1] and b.close>lo20.iloc[i-1] and q.close>b.high and q.close>q.open: side="BUY"
        if c.dir.iloc[i]<0 and b.high>hi20.iloc[i-1] and b.close<hi20.iloc[i-1] and q.close<b.low and q.close<q.open: side="SELL"
        if not side: continue
        entry=float(q.close); last_trade=i
        # test 100/150/200 pips as $1/$1.5/$2 price moves under existing gold convention
        for target in TARGETS:
            tp=entry+target if side=="BUY" else entry-target; sl=entry-SL_MOVE if side=="BUY" else entry+SL_MOVE
            exitp=float(d.close.iloc[i+MAX_HOLD]); result="TIME"
            for _,x in d.iloc[i+1:i+1+MAX_HOLD].iterrows():
                if side=="BUY":
                    if x.low<=sl: exitp=sl-SLIPPAGE; result="SL"; break
                    if x.high>=tp: exitp=tp-SLIPPAGE; result="TP"; break
                else:
                    if x.high>=sl: exitp=sl+SLIPPAGE; result="SL"; break
                    if x.low<=tp: exitp=tp+SLIPPAGE; result="TP"; break
            pnl=(exitp-entry)*(1 if side=="BUY" else -1)*USD_PER_MOVE_PER_LOT*LOT
            rows.append({"time":d.index[i],"side":side,"target":target,"result":result,"pnl_usd":pnl,"htf_confluence":c.confluence.iloc[i]})
    x=pd.DataFrame(rows); os.makedirs("results",exist_ok=True); x.to_csv("results/htf_liquidity_fvg_v3.csv",index=False)
    if x.empty: print("No V3 trades"); return
    for target,g in x.groupby("target"):
        wins=(g.pnl_usd>0); pos=g.loc[g.pnl_usd>0,"pnl_usd"].sum(); neg=-g.loc[g.pnl_usd<0,"pnl_usd"].sum()
        eq=START+g.pnl_usd.cumsum(); dd=eq-eq.cummax()
        print({"model":"HTF_LIQ_FVG_V3","target_move":float(target),"trades":len(g),"win_rate":float(wins.mean()),"net_usd":float(g.pnl_usd.sum()),"ending_balance":float(START+g.pnl_usd.sum()),"profit_factor":float(pos/neg) if neg else float("inf"),"max_dd_usd":float(dd.min()),"lot":LOT,"start":START})
if __name__=="__main__":
 import argparse; p=argparse.ArgumentParser(); p.add_argument("csv"); a=p.parse_args(); run(a.csv)
