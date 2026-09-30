import pandas as pd, numpy as np
from bt import *; from strats import *; from dca import *
df = base(); S = sleeves(df)
A = vt2(df, 0.25, lmax=2.0, lookback=40, weekly=True)
BH = one(df, "Q", pd.Series(True, index=df.index))
def window(s0, s1):
    d = df[s0:s1]; Sd = {k: v[s0:s1] for k, v in S.items()}
    res = {}
    for name, fn in [("BH", lambda: dca_vt(d, Sd, BH.ffill().loc[d.index])), ("VT25", lambda: dca_vt(d, Sd, A.ffill().loc[d.index])),
                     ("U1", lambda: dca_u1(d)), ("U1 30%", lambda: dca_u1(d, ratio=0.3))]:
        v, f = fn(); inv = f.cumsum()
        res[name] = dict(mult=v.iloc[-1] / inv.iloc[-1], irr=irr(v, f, d.index[0], d.index[-1]),
                         worst=(v / inv - 1)[inv > 0].min(), mdd=(v / v.cummax() - 1).min())
    return res
full = window("1999-03", "2026-09-29")
print("전체 1999-03~2026-09 적립"); print(pd.DataFrame(full).T.round(3).to_string())
ms = df.index.to_series().groupby(df.index.to_period("M")).min().values
rows = []
for s0 in ms[::3]:
    i = df.index.searchsorted(s0 + pd.DateOffset(years=10))
    if i >= len(df): break
    w = window(s0, df.index[i]); rows.append({"start": pd.Timestamp(s0).strftime("%Y-%m"), **{k: v["irr"] for k, v in w.items()}})
R = pd.DataFrame(rows).set_index("start")
print("\n10년 적립 창 (분기 시작) IRR 요약"); print(R.describe().round(3).to_string())
for c in ["VT25", "U1", "U1 30%"]:
    d = R[c] - R["BH"]; print(f"{c} vs BH: 승률 {(d>0).mean():.0%} 중앙 {d.median()*100:+.1f}%p 최악 {d.min()*100:+.1f}%p")
d = R["VT25"] - R["U1"]; print(f"VT25 vs U1: 승률 {(d>0).mean():.0%} 중앙 {d.median()*100:+.1f}%p 최악 {d.min()*100:+.1f}%p")
R.to_csv("/tmp/claude-0/-home-user-ig-media/e6f85915-940d-5fa1-b9be-39953ea47c0c/scratchpad/dca_roll.csv")
for a, b in [("2000-03-01", "2010-03-01"), ("2016-09-01", "2026-09-29"), ("2007-10-01", "2017-10-01")]:
    print(f"\n{a}~{b}"); print(pd.DataFrame(window(a, b)).T.round(3).to_string())
