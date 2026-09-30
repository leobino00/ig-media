import pandas as pd, numpy as np
from bt import *
from strats import *
pd.set_option("display.width", 250)
df = base(); S = sleeves(df)
def blend(t, core=0.5):
    t = t.ffill(); L = t.Q3 * 3
    w = pd.DataFrame(0.0, index=df.index, columns=["Q", "Q2", "Q3"]); w["Q3"] = (core + (1 - core) * L) / 3
    return emit(df, w)
A = vt2(df, 0.25, lmax=2.0, lookback=40, weekly=True)
C = {"BH QQQ": one(df, "Q", pd.Series(True, index=df.index)),
     "A: VT25·40d·주간·max2x": A,
     "B: 50 QQQ + 50 A": blend(A, 0.5),
     "A3: VT25·40d·주간·max3x": vt2(df, 0.25, lmax=3.0, lookback=40, weekly=True)}
R = {}
for k, t in C.items():
    R[k] = sim(df, t, S); R[k + " [세후22%]"] = sim(df, t, S, tax=0.22)
R["U1 (기존)"] = (u1(df), None)
print(pd.DataFrame([stats(r, df.rf, tu, n) for n, (r, tu) in R.items()]).set_index("name").round(3).to_string())
print("\n위기 구간 낙폭 (고점→저점 수익률)")
eps = {"닷컴 2000-03~2002-10": ("2000-03-24", "2002-10-09"), "금융위기 2007-10~2009-03": ("2007-10-31", "2009-03-09"),
       "코로나 2020-02~03": ("2020-02-19", "2020-03-16"), "2022 긴축": ("2021-11-19", "2022-12-28"),
       "2025 관세": ("2025-02-19", "2025-04-08")}
tab = {}
for n, (r, _) in R.items():
    if "세후" in n: continue
    e = (1 + r).cumprod(); tab[n] = {k: e[b] / e[a] - 1 for k, (a, b) in eps.items()}
    tab[n]["회복: 2002-10~2007-10"] = e["2007-10-31"] / e["2002-10-09"] - 1
print(pd.DataFrame(tab).round(3).to_string())
rv = df.r.rolling(40).std() * np.sqrt(252)
print("\n현재(2026-09-29) 40일 실현변동성 %.1f%% → 목표 레버리지 %.2f → 0.5단위 %.1f배" % (rv.iloc[-1]*100, min(2, .25/rv.iloc[-1]), round(min(2, .25/rv.iloc[-1])*2)/2))
print("최근 8주 목표 레버리지:", (A.ffill().Q3*3).resample("W-FRI").last().tail(8).round(2).to_dict())
