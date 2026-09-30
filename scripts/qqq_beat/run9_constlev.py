"""레버리지 효과 분리: VT25와 평균 레버리지가 같은 고정 레버리지(주간 리밸런싱)를 구간별로 비교."""
import pandas as pd, numpy as np
from bt import *; from strats import *
df = base(); S = sleeves(df)
A = vt2(df, 0.25, lmax=2.0, lookback=40, weekly=True)
Lbar = float((A.ffill().Q3 * 3).mean())
fri = df.index.to_series().groupby(df.index.to_period("W")).max().values
def const(L):
    t = pd.DataFrame(np.nan, index=df.index, columns=["Q", "Q2", "Q3"])
    t.loc[df.index.isin(fri), :] = [0.0, 0.0, L / 3]
    t.iloc[0] = [0.0, 0.0, L / 3]
    return t
C = {"BH 1x": one(df, "Q", pd.Series(True, index=df.index)), "VT25": A, f"고정 {Lbar:.2f}x": const(Lbar), "고정 1.5x": const(1.5)}
R = {k: sim(df, t, S)[0] for k, t in C.items()}
for a, b in [("1999-03", "2026-09"), ("1999-03", "2012-12"), ("2013-01", "2026-09"), ("2010-01", "2026-09")]:
    print(f"== {a}~{b}")
    print(pd.DataFrame([stats(r[a:b], df.rf[a:b], None, k) for k, r in R.items()]).set_index("name")[["CAGR", "Vol", "MDD", "Sharpe"]].round(3).to_string())
