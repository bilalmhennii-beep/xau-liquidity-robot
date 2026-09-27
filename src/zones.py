from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass
class Zone:
    created: pd.Timestamp
    tf: str
    side: str
    kind: str
    low: float
    high: float
    key: float
    score: float
    atr: float

TF_DELTA={"30m":pd.Timedelta(minutes=30),"1h":pd.Timedelta(hours=1),"2h":pd.Timedelta(hours=2),
"3h":pd.Timedelta(hours=3),"4h":pd.Timedelta(hours=4),"1D":pd.Timedelta(days=1),"1W":pd.Timedelta(days=7)}

def available_at(label: pd.Timestamp, tf: str)->pd.Timestamp:
    # resampled bars are left-labelled; their information becomes available only after close
    return label+TF_DELTA[tf]

def atr(df: pd.DataFrame,n:int=14)->pd.Series:
    pc=df.close.shift(1)
    tr=pd.concat([(df.high-df.low),(df.high-pc).abs(),(df.low-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n,adjust=False,min_periods=n).mean()

def detect_fvgs(df:pd.DataFrame,tf:str,min_gap_atr=.12,min_disp_atr=.80)->list[Zone]:
    a=atr(df); out=[]
    for i in range(2,len(df)):
        av=float(a.iloc[i]) if np.isfinite(a.iloc[i]) else 0
        if av<=0: continue
        b0,b2=df.iloc[i-2],df.iloc[i]
        body=abs(float(b2.close-b2.open))
        if body<min_disp_atr*av: continue
        if b2.low>b0.high: lo,hi,side=float(b0.high),float(b2.low),"BUY"
        elif b2.high<b0.low: lo,hi,side=float(b2.high),float(b0.low),"SELL"
        else: continue
        gap=hi-lo
        if gap<min_gap_atr*av: continue
        quality=min(20,10*(gap/av))+min(15,8*(body/av))
        out.append(Zone(available_at(df.index[i],tf),tf,side,"FVG",lo,hi,(lo+hi)/2,45+quality,av))
    return out

def confirmed_pivots(df:pd.DataFrame,left=3,right=3):
    highs=[]; lows=[]; h=df.high.to_numpy(); l=df.low.to_numpy()
    for i in range(left,len(df)-right):
        confirm=i+right
        if h[i]>max(h[i-left:i]) and h[i]>=max(h[i+1:i+right+1]): highs.append((df.index[confirm],df.index[i],float(h[i])))
        if l[i]<min(l[i-left:i]) and l[i]<=min(l[i+1:i+right+1]): lows.append((df.index[confirm],df.index[i],float(l[i])))
    return highs,lows

def detect_equal_liquidity(df:pd.DataFrame,tf:str,tolerance_atr=.12)->list[Zone]:
    a=atr(df); highs,lows=confirmed_pivots(df); out=[]
    for pivots,side in ((lows,"BUY"),(highs,"SELL")):
        for j in range(1,len(pivots)):
            confirm_label,pivot_time,px=pivots[j]; _,_,prev=pivots[j-1]
            pos=df.index.get_indexer([pivot_time],method="nearest")[0]
            av=float(a.iloc[pos]) if np.isfinite(a.iloc[pos]) else 0
            if av<=0 or abs(px-prev)>tolerance_atr*av: continue
            key=(px+prev)/2; half=max(.05,tolerance_atr*av/2)
            out.append(Zone(available_at(confirm_label,tf),tf,side,"EQL",key-half,key+half,key,62,av))
    return out
