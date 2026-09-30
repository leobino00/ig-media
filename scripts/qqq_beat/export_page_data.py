"""웹 페이지(차트)용 JSON 추출. 출력: stdout JSON."""
import json, pandas as pd, numpy as np
from bt import *
from strats import *
df = base(); S = sleeves(df)
BH = one(df, "Q", pd.Series(True, index=df.index))
A = vt2(df, 0.25, lmax=2.0, lookback=40, weekly=True)
L = A.ffill().Q3 * 3
w = pd.DataFrame(0.0, index=df.index, columns=["Q", "Q2", "Q3"]); w["Q3"] = (0.5 + 0.5 * L) / 3
rets = {"bh": sim(df, BH, S)[0], "a": sim(df, A, S)[0], "b": sim(df, emit(df, w), S)[0], "u1": u1(df)}
eq = {k: (1 + r).cumprod() for k, r in rets.items()}
wk = df.index.to_series().groupby(df.index.to_period("W")).max().values
wk = pd.DatetimeIndex(wk)
out = {"dates": [d.strftime("%Y-%m-%d") for d in wk]}
for k, e in eq.items():
    out["eq_" + k] = [round(float(v), 4) for v in e[wk]]
    out["dd_" + k] = [round(float(v), 4) for v in (e / e.cummax() - 1)[wk]]
out["lev"] = [float(v) for v in L[wk]]
ya = eq["a"].resample("YE").last(); yb = eq["bh"].resample("YE").last()
first = pd.Series([1.0], index=[df.index[0]])
ya = pd.concat([first, ya]).pct_change().dropna(); yb = pd.concat([first, yb]).pct_change().dropna()
out["years"] = [int(d.year) for d in ya.index]
out["yr_a"] = [round(float(v), 4) for v in ya]; out["yr_bh"] = [round(float(v), 4) for v in yb]
ms = df.index.to_series().groupby(df.index.to_period("M")).min().values
roll = {"start": [], "a": [], "b": []}
for s0 in ms:
    i = df.index.searchsorted(s0 + pd.DateOffset(years=10))
    if i >= len(df): break
    s1 = df.index[i]; c = lambda x: (x[s1] / x[s0]) ** 0.1 - 1
    roll["start"].append(pd.Timestamp(s0).strftime("%Y-%m"))
    roll["a"].append(round(c(eq["a"]) - c(eq["bh"]), 4)); roll["b"].append(round(c(eq["b"]) - c(eq["bh"]), 4))
out["roll10"] = roll
grid = []
for tv in (0.15, 0.20, 0.25, 0.30, 0.35):
    row = []
    for lb in (10, 20, 40, 60, 90):
        s = stats(sim(df, vt2(df, tv, lmax=2.0, lookback=lb, weekly=True), S)[0], df.rf)
        row.append([round(s["CAGR"], 4), round(s["Sharpe"], 3), round(s["MDD"], 3)])
    grid.append(row)
out["grid"] = {"tv": [15, 20, 25, 30, 35], "lb": [10, 20, 40, 60, 90], "cells": grid}
rv = df.r.rolling(40).std() * np.sqrt(252)
out["now"] = {"date": df.index[-1].strftime("%Y-%m-%d"), "vol": round(float(rv.iloc[-1]), 4), "lev": float(L.iloc[-1])}
print(json.dumps(out, separators=(",", ":")))
