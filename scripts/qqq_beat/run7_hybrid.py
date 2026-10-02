"""적립식: VT25 · U1 · 반반(적립금 절반씩 각 전략 계좌) 비교 + U1 신호 발생일."""
import pandas as pd, numpy as np, json, sys
from bt import *; from strats import *; from dca import *
df = base(); S = sleeves(df)
A = vt2(df, 0.25, lmax=2.0, lookback=40, weekly=True).ffill(); BH = one(df, "Q", pd.Series(True, index=df.index)).ffill()
def run(d):
    Sd = {k: v.loc[d.index] for k, v in S.items()}
    vb, f = dca_vt(d, Sd, BH.loc[d.index]); va, _ = dca_vt(d, Sd, A.loc[d.index]); vu, _ = dca_u1(d)
    return {"BH": vb, "VT25": va, "U1": vu, "반반": 0.5 * va + 0.5 * vu}, f
def summ(vals, f, d):
    inv = f.cumsum(); o = {}
    for k, v in vals.items():
        o[k] = dict(mult=v.iloc[-1] / inv.iloc[-1], irr=irr(v, f, d.index[0], d.index[-1]), worst=(v / inv - 1)[inv > 0].min(), mdd=(v / v.cummax() - 1).min())
    return o
vals, f = run(df); full = summ(vals, f, df)
print(pd.DataFrame(full).T.round(3).to_string())
ms = df.index.to_series().groupby(df.index.to_period("M")).min().values
rows = []
for s0 in ms[::3]:
    i = df.index.searchsorted(s0 + pd.DateOffset(years=10))
    if i >= len(df): break
    d = df.loc[s0:df.index[i]]; v, ff = run(d); s = summ(v, ff, d)
    rows.append({"start": pd.Timestamp(s0).strftime("%Y-%m"), **{k: s[k]["irr"] for k in s}, **{k + "_w": s[k]["worst"] for k in s}})
R = pd.DataFrame(rows).set_index("start")
ks = ["BH", "VT25", "U1", "반반"]
print(R[ks].describe().round(3).to_string())
print("worst account loss median:", R[[k + "_w" for k in ks]].median().round(3).to_dict(), "min:", R[[k + "_w" for k in ks]].min().round(3).to_dict())
for a, b in [("VT25", "BH"), ("U1", "BH"), ("반반", "BH"), ("VT25", "U1"), ("반반", "U1")]:
    dd = R[a] - R[b]; print(f"{a} vs {b}: 승률 {(dd>0).mean():.0%} 중앙 {dd.median()*100:+.1f}%p 최악 {dd.min()*100:+.1f}%p 최고 {dd.max()*100:+.1f}%p")
# U1 신호일
p3 = (1 + lev(df, 3)).cumprod(); ath = p3.cummax()
print("U1 신호(합성 TQQQ ≤ 전고점×0.5) 첫날들:")
hit = p3 <= ath * 0.5; prev = False
for d, h in hit.items():
    if h and not prev: print(" ", d.date(), "QQQ", round(df.px[d], 2))
    prev = h
if "--json" in sys.argv:
    wk = pd.DatetimeIndex(df.index.to_series().groupby(df.index.to_period("W")).max().values); inv = f.cumsum()
    json.dump({"dca_full": {k: {m: round(float(x), 4) for m, x in v.items()} for k, v in full.items()},
               "dca_roll": {"start": list(R.index), **{k: [round(float(x), 4) for x in R[k]] for k in ks}},
               "dca_dates": [d.strftime("%Y-%m-%d") for d in wk], "dca_inv": [round(float(x), 1) for x in inv[wk]],
               **{"dca_" + k: [round(float(x), 2) for x in vals[k][wk]] for k in ks}},
              open(sys.argv[sys.argv.index("--json") + 1], "w"), ensure_ascii=False, separators=(",", ":"))
