from __future__ import annotations
import pandas as pd
from src.metrics import summarize

def chronological_split(trades: pd.DataFrame, train=.60, validation=.20):
    x=trades.sort_values("touch").reset_index(drop=True)
    n=len(x); a=int(n*train); b=int(n*(train+validation))
    return {"train":x.iloc[:a],"validation":x.iloc[a:b],"test":x.iloc[b:]}

def report_splits(trades,min_score=85,allowed_tf=("2h","3h","4h","1D","1W")):
    x=trades[(trades.score>=min_score)&trades.tf.isin(allowed_tf)]
    return {name:summarize(part) for name,part in chronological_split(x).items()}
