import pandas as pd, numpy as np, bt
from bt import *
from strats import *
pd.set_option("display.width", 250)
df = base(); S = sleeves(df)
bh = stats(sim(df, one(df, "Q", pd.Series(True, index=df.index)), S)[0], df.rf)
print("BH CAGR %.3f Sharpe %.3f MDD %.3f" % (bh["CAGR"], bh["Sharpe"], bh["MDD"]))
print("\n[grid] CAGR / Sharpe / MDD, weekly rebalance, max leverage by column")
for lmax in (1.5, 2.0, 3.0):
    rows = {}
    for tv in (0.15, 0.20, 0.25, 0.30, 0.35):
        row = {}
        for lb in (10, 20, 40, 60, 90):
            s = stats(sim(df, vt2(df, tv, lmax=lmax, lookback=lb, weekly=True), S)[0], df.rf)
            row[f"lb{lb}"] = f"{s['CAGR']*100:4.1f}/{s['Sharpe']:.2f}/{s['MDD']*100:3.0f}"
        rows[f"tv{int(tv*100)}"] = row
    print(f"-- lmax {lmax}"); print(pd.DataFrame(rows).T.to_string())
print("\n[cost stress] VT25 wk lb20 max2x / max3x")
for cost, spread in [(0.001, 0.005), (0.003, 0.005), (0.001, 0.015), (0.003, 0.015)]:
    bt.SPREAD = spread
    S2 = sleeves(df)
    out = []
    for lmax in (2.0, 3.0):
        r, tu = sim(df, vt2(df, 0.25, lmax=lmax, weekly=True), S2, cost=cost)
        s = stats(r, df.rf); out.append(f"max{lmax}: {s['CAGR']*100:.1f}% Sh {s['Sharpe']:.2f}")
    print(f"cost {cost*100:.1f}% spread {spread*100:.1f}%:", " | ".join(out))
bt.SPREAD = 0.005
# 평균 레버리지·현금 비중
t = vt2(df, 0.25, lmax=2.0, weekly=True).ffill()
L = t.Q3 * 3
print("\nVT25 wk max2x: 평균 레버리지 %.2f, 0배(현금) 비중 %.1f%%, 2배 비중 %.1f%%" % (L.mean(), (L == 0).mean() * 100, (L >= 2).mean() * 100))
print(L.resample("YE").mean().round(2).to_string())
