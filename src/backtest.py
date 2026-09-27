from __future__ import annotations
import pandas as pd
from config import CFG
from src.data import load_ohlc, build_timeframes
from src.zones import detect_fvgs, detect_equal_liquidity
from src.metrics import summarize

TF_WEIGHT={"30m":10,"1h":14,"2h":18,"3h":20,"4h":23,"1D":27,"1W":30}

def build_zones(tfs):
    zones=[]
    for tf in ("30m","1h","2h","3h","4h","1D","1W"):
        d=tfs[tf]
        for z in detect_fvgs(d,tf,CFG.min_fvg_atr,CFG.min_displacement_atr):
            z.score=min(100,z.score+TF_WEIGHT[tf])
            zones.append(z)
        for z in detect_equal_liquidity(d,tf,CFG.equal_liquidity_atr):
            z.score=min(100,z.score+TF_WEIGHT[tf])
            zones.append(z)
    return sorted(zones,key=lambda z:z.created)

def evaluate_first_touch(base5, zones):
    rows=[]
    for z in zones:
        if z.score < CFG.min_score:
            continue
        future=base5.loc[base5.index > z.created]
        touched=future[(future.low <= z.key) & (future.high >= z.key)]
        if touched.empty:
            continue
        touch_time=touched.index[0]
        path=future.loc[touch_time:].iloc[:CFG.max_holding_bars_5m]
        if path.empty:
            continue
        entry=z.key + (CFG.spread_price/2 if z.side=="BUY" else -CFG.spread_price/2)
        buffer=max(CFG.slippage_price,0.15*z.atr)
        stop=(z.low-buffer) if z.side=="BUY" else (z.high+buffer)
        risk=abs(entry-stop)
        if risk <= 0:
            continue
        mfe=mae=0.0
        outcome=None
        exit_r=0.0
        for _,b in path.iterrows():
            if z.side=="BUY":
                mfe=max(mfe,float(b.high-entry)); mae=max(mae,float(entry-b.low))
                stop_hit=b.low <= stop
                # adaptive structural target: 2R baseline; research will later replace with next-liquidity exit
                target=entry+2*risk
                tp_hit=b.high >= target
            else:
                mfe=max(mfe,float(entry-b.low)); mae=max(mae,float(b.high-entry))
                stop_hit=b.high >= stop
                target=entry-2*risk
                tp_hit=b.low <= target
            if stop_hit: # conservative if both occur in same candle
                outcome="LOSS"; exit_r=-1.0; break
            if tp_hit:
                outcome="WIN"; exit_r=2.0; break
        if outcome is None:
            last=float(path.close.iloc[-1])
            pnl=(last-entry) if z.side=="BUY" else (entry-last)
            exit_r=pnl/risk
            outcome="TIME"
        rows.append({"created":z.created,"touch":touch_time,"tf":z.tf,"side":z.side,"kind":z.kind,
                     "score":z.score,"entry":entry,"stop":stop,"r":exit_r,"outcome":outcome,
                     "mfe":mfe,"mae":mae})
    return pd.DataFrame(rows)

def run(csv_path):
    raw=load_ohlc(csv_path)
    tfs=build_timeframes(raw)
    zones=build_zones(tfs)
    trades=evaluate_first_touch(tfs["5m"],zones)
    print(summarize(trades))
    if not trades.empty:
        trades.to_csv("results/trades.csv",index=False)
    return trades

if __name__=="__main__":
    import argparse, os
    p=argparse.ArgumentParser()
    p.add_argument("csv")
    args=p.parse_args()
    os.makedirs("results",exist_ok=True)
    run(args.csv)
