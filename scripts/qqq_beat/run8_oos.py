"""표본 외 검증: 1999-03~2012-12에서 격자 최적 파라미터를 고르고 2013-01~2026-09에 그대로 적용.
+ 파라미터를 25%·40일로 고정했을 때 두 구간 각각의 성과."""
import pandas as pd, numpy as np
from bt import *; from strats import *
df = base(); S = sleeves(df)
IS, OOS = ("1999-03", "2012-12"), ("2013-01", "2026-09")
bh = sim(df, one(df, "Q", pd.Series(True, index=df.index)), S)[0]
def seg(r, p): return stats(r[p[0]:p[1]], df.rf[p[0]:p[1]])
res = []
for tv in (0.15, 0.20, 0.25, 0.30, 0.35):
    for lb in (10, 20, 40, 60, 90):
        r = sim(df, vt2(df, tv, lmax=2.0, lookback=lb, weekly=True), S)[0]
        a, b = seg(r, IS), seg(r, OOS)
        res.append(dict(tv=tv, lb=lb, is_cagr=a["CAGR"], is_sh=a["Sharpe"], oos_cagr=b["CAGR"], oos_sh=b["Sharpe"], oos_mdd=b["MDD"]))
R = pd.DataFrame(res)
b_is, b_oos = seg(bh, IS), seg(bh, OOS)
print(f"BH  IS CAGR {b_is['CAGR']:.3f} Sh {b_is['Sharpe']:.2f} | OOS CAGR {b_oos['CAGR']:.3f} Sh {b_oos['Sharpe']:.2f} MDD {b_oos['MDD']:.3f}")
best = R.sort_values("is_sh", ascending=False).iloc[0]
print("IS 샤프 최적:", best.round(3).to_dict())
print("고정 25%/40일:", R[(R.tv == 0.25) & (R.lb == 40)].round(3).to_dict("records"))
print(f"OOS에서 BH CAGR 넘은 칸 {(R.oos_cagr > b_oos['CAGR']).sum()}/25, 샤프 넘은 칸 {(R.oos_sh > b_oos['Sharpe']).sum()}/25")
print("IS 샤프 상위5의 OOS:"); print(R.sort_values("is_sh", ascending=False).head(5).round(3).to_string(index=False))
