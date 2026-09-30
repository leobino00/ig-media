import pandas as pd, numpy as np, sys
from bt import *
from strats import *
pd.set_option("display.width", 250)
df = base(); S = sleeves(df)
sig = sma_signal(df.px, 200); sigb = sma_signal(df.px, 200, 0.03)
Q = lambda col: one(df, col, pd.Series(True, index=df.index))
C = {
 "BH QQQ": Q("Q"),
 "SMA200±3% 3x/1x": one(df, "Q3", sigb, "Q"),
 "SMA200±3% 2x/1x": one(df, "Q2", sigb, "Q"),
 "VT25": vt2(df, 0.25),
 "VT25 band.5": vt2(df, 0.25, band=0.5),
 "VT25 wk": vt2(df, 0.25, weekly=True),
 "VT25 lb60": vt2(df, 0.25, lookback=60),
 "VT25 ewm30": vt2(df, 0.25, lookback=30, ewm=True),
 "VT25 +trend off1x": vt2(df, 0.25, trend=sigb, off_cap=1.0),
 "VT25 +trend off.5x": vt2(df, 0.25, trend=sigb, off_cap=0.5),
 "VT30 +trend off1x": vt2(df, 0.30, trend=sigb, off_cap=1.0),
 "VT20 max2x": vt2(df, 0.20, lmax=2.0),
 "VT25 max2x": vt2(df, 0.25, lmax=2.0),
}
R = {}
for k, t in C.items():
    R[k] = sim(df, t, S)
    R[k + " [tax22]"] = sim(df, t, S, tax=0.22)
R["U1"] = (u1(df), None)
rows = [stats(r, df.rf, tu, n) for n, (r, tu) in R.items()]
print(pd.DataFrame(rows).set_index("name").round(3).to_string())

def sub(a, b):
    out = {}
    for n, (r, tu) in R.items():
        if "tax" in n: continue
        rr = r[a:b]; out[n] = stats(rr, df.rf[a:b], None, n)
    return pd.DataFrame(out).T[["CAGR", "MDD", "Sharpe"]].astype(float).round(3)
for a, b in [("1999-03", "2009-12"), ("2002-10-10", "2026-09"), ("2010-01", "2026-09"), ("2020-01", "2026-09")]:
    print(f"\n== {a} ~ {b}"); print(sub(a, b).to_string())

# 롤링 10년·5년 창: 매월 시작, BH 대비 CAGR 차이
eqs = {n: (1 + r).cumprod() for n, (r, tu) in R.items() if "tax" not in n}
ms = df.index.to_series().groupby(df.index.to_period("M")).min().values
for yrs in (5, 10):
    print(f"\n== rolling {yrs}y windows (monthly starts): win% vs BH, median/worst CAGR gap")
    res = {}
    for n, e in eqs.items():
        diffs = []
        for s0 in ms:
            e_idx = df.index.searchsorted(s0 + pd.DateOffset(years=yrs))
            if e_idx >= len(df): break
            s1 = df.index[e_idx]
            c = lambda x: (x[s1] / x[s0]) ** (1 / yrs) - 1
            diffs.append(c(e) - c(eqs["BH QQQ"]))
        d = np.array(diffs)
        res[n] = dict(win=(d > 0).mean(), med=np.median(d), worst=d.min(), best=d.max(), n=len(d))
    print(pd.DataFrame(res).T.round(3).to_string())
