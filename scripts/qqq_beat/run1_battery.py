import pandas as pd, numpy as np
from bt import *
from strats import *
pd.set_option("display.width", 250)
df = base(); S = sleeves(df)
# 합성 TQQQ 검증: 2021-11-19 ~ 2022-12-28 낙폭 (실제 약 -81.7%)
p3 = (1 + lev(df, 3)).cumprod()
print("synthetic TQQQ 2021-11-19→2022-12-28:", round(p3["2022-12-28"] / p3["2021-11-19"] - 1, 3))
print("synthetic TQQQ 2020-02-19→2020-03-16:", round(p3["2020-03-16"] / p3["2020-02-19"] - 1, 3), "(실제 약 -0.70)")
print("synthetic TQQQ 2010-02-11→2026-09-29 mult:", round(p3.iloc[-1] / p3["2010-02-11"], 1), "(실제 TQQQ 상장 이후 대략 x250~300 수준)")
res = {}
def add(name, t=None, ret=None, tax=0.0):
    if ret is None:
        ret, turn = sim(df, t, S, tax=tax)
    else:
        turn = None
    res[name] = (ret, turn)
Q = lambda col: one(df, col, pd.Series(True, index=df.index))
add("BH QQQ", Q("Q")); add("BH QLD 2x", Q("Q2")); add("BH TQQQ 3x", Q("Q3"))
for n in (100, 200):
    sig = sma_signal(df.px, n)
    add(f"SMA{n} QQQ/cash", one(df, "Q", sig))
    add(f"SMA{n} 2x/cash", one(df, "Q2", sig))
    add(f"SMA{n} 3x/cash", one(df, "Q3", sig))
sigb = sma_signal(df.px, 200, 0.03)
add("SMA200±3% 2x/cash", one(df, "Q2", sigb)); add("SMA200±3% 3x/cash", one(df, "Q3", sigb))
add("SMA200±3% 3x/1x off", one(df, "Q3", sigb, "Q"))
for tv in (0.20, 0.25, 0.30):
    add(f"VolTgt {int(tv*100)}% max3x", vol_target(df, tv))
    add(f"VolTgt {int(tv*100)}% max3x +SMA200", vol_target(df, tv, trend=sma_signal(df.px, 200)))
add("U1 (-50% TQQQ half)", ret=u1(df))
rows = [stats(r, df.rf, tu, n) for n, (r, tu) in res.items()]
print(pd.DataFrame(rows).set_index("name").round(3).to_string())
