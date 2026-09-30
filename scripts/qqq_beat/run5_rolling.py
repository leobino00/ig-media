import pandas as pd, numpy as np
from bt import *
from strats import *
df = base(); S = sleeves(df)
A = vt2(df, 0.25, lmax=2.0, lookback=40, weekly=True)
t = A.ffill(); L = t.Q3*3
w = pd.DataFrame(0.0, index=df.index, columns=["Q","Q2","Q3"]); w["Q3"] = (0.5+0.5*L)/3
E = {"BH": (1+sim(df, one(df,"Q",pd.Series(True,index=df.index)), S)[0]).cumprod(),
     "A": (1+sim(df, A, S)[0]).cumprod(), "B": (1+sim(df, emit(df,w), S)[0]).cumprod(),
     "A_tax": (1+sim(df, A, S, tax=.22)[0]).cumprod(), "BH_tax": (1+sim(df, one(df,"Q",pd.Series(True,index=df.index)), S, tax=.22)[0]).cumprod()}
ms = df.index.to_series().groupby(df.index.to_period("M")).min().values
for yrs in (3,5,10):
    for n, base_ in (("A","BH"),("B","BH")):
        d=[]
        for s0 in ms:
            i=df.index.searchsorted(s0+pd.DateOffset(years=yrs))
            if i>=len(df): break
            s1=df.index[i]; c=lambda x:(x[s1]/x[s0])**(1/yrs)-1
            d.append(c(E[n])-c(E[base_]))
        d=np.array(d); print(f"{yrs}y {n} vs {base_}: win {d.mean()*0+ (d>0).mean():.0%} med {np.median(d)*100:+.1f}%p worst {d.min()*100:+.1f}%p n={len(d)}")
print("연도별 A-BH (%p):"); ya=E["A"].resample("YE").last().pct_change(); yb=E["BH"].resample("YE").last().pct_change()
print(((ya-yb)*100).round(1).dropna().to_string())
