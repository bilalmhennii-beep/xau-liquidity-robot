from __future__ import annotations
import itertools, json
import pandas as pd
from src.data import load_ohlc, build_timeframes
from src.backtest import build_zones, evaluate_first_touch
from src.metrics import summarize

def score_subset(trades, min_score, allowed_tf):
    x=trades[(trades.score>=min_score)&(trades.tf.isin(allowed_tf))].copy()
    m=summarize(x)
    m.update({"min_score":min_score,"timeframes":",".join(allowed_tf)})
    return m

def run(path):
    raw=load_ohlc(path); tfs=build_timeframes(raw)
    zones=build_zones(tfs); trades=evaluate_first_touch(tfs["5m"],zones)
    rows=[]
    tf_sets=[
      ("30m","1h","2h","3h","4h","1D","1W"),
      ("1h","2h","3h","4h","1D","1W"),
      ("2h","3h","4h","1D","1W"),
      ("3h","4h","1D","1W"),
      ("4h","1D","1W"),
    ]
    for s,tf in itertools.product(range(70,96,5),tf_sets):
        m=score_subset(trades,s,tf)
        if m.get("trades",0)>=5: rows.append(m)
    out=pd.DataFrame(rows)
    if out.empty: return out
    out["robust_score"]=out["expectancy_r"]*out["trades"].pow(.5)-abs(out["max_drawdown_r"])*.05
    out=out.sort_values(["robust_score","profit_factor"],ascending=False)
    out.to_csv("results/sweep.csv",index=False)
    print(out.head(20).to_string(index=False))
    return out

if __name__=="__main__":
    import argparse,os
    p=argparse.ArgumentParser(); p.add_argument("csv"); a=p.parse_args()
    os.makedirs("results",exist_ok=True); run(a.csv)
