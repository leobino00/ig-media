# -*- coding: utf-8 -*-
"""2상태 실험 — 상승 추세면 TQQQ, 아니면 현금. 숏 다리 없음.

3상태 실험(`experiment.py`)에서 SQQQ 다리가 35개 규칙 전부를 악화시켰으므로
숏을 빼고 다시 본다. 질문이 바뀐다:

    「TQQQ를 그냥 들고 있는 것보다 나은가?」 — 수익으로도, 낙폭으로도.

구간 A: 2010-02-19~  실제 TQQQ 가격.          ← 1차 결과
구간 B: 2000-01-07~  일간리셋 시뮬 TQQQ.       ← 닷컴·금융위기 포함, 오차범위 병기

    python3 scripts/qqq_regime/experiment_2state.py
"""

import datetime as dt
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import backtest as BT
import leverage as LV
import prices
import signals as S

DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "출력")

REAL_START = dt.date(2010, 2, 19)
LONG_START = dt.date(2000, 1, 7)
OOS_SPLIT = dt.date(2019, 1, 1)
COST_BPS = 10.0
MAP2 = {S.UP: "TQQQ", S.DOWN: None, S.NEUTRAL: None}

# 시뮬 보수 시나리오 (연 %). 적합값을 가운데 두고 위아래로 벌린다.
FEE_SCENARIOS = [("적합", None), ("보수0%", 0.0), ("보수+1%", 1.0), ("보수+2%", 2.0)]


def mar(cagr, mdd):
    """CAGR ÷ |최대낙폭|. 1을 넘으면 낙폭 1단위당 수익 1단위 이상."""
    return None if (cagr is None or not mdd) else cagr / abs(mdd)


def summarize(r):
    return {"cagr_pct": r.cagr_pct, "mdd_pct": r.mdd_pct, "vol_pct": r.vol_pct,
            "mar": mar(r.cagr_pct, r.mdd_pct), "switches_per_year": r.switches_per_year,
            "weeks_in": dict(r.weeks_in) if r.weeks_in else None, "annual": r.annual,
            "total_pct": r.total_pct}


def run_grid(qd, qc, rets, rc, dates, grid, cost_bps=COST_BPS):
    rows = []
    for name, fn in grid:
        r = BT.run(dates, fn(qd, qc), rets, MAP2, rc, switch_cost_bps=cost_bps)
        d = summarize(r)
        d["rule"] = name
        if r.weeks_in:
            tot = sum(r.weeks_in.values())
            d["pct_in_tqqq"] = 100.0 * r.weeks_in[S.UP] / tot if tot else None
        rows.append(d)
    return rows


def dist(rows, key):
    v = sorted(x[key] for x in rows if x[key] is not None)
    if not v:
        return None
    q = st.quantiles(v, n=4) if len(v) > 3 else [v[0], st.median(v), v[-1]]
    return {"n": len(v), "min": v[0], "p25": q[0], "median": st.median(v),
            "p75": q[2], "max": v[-1], "mean": st.mean(v)}


def bench(dates, rets, sym):
    b = BT.buy_and_hold(dates, rets, sym)
    return {"cagr_pct": b.cagr_pct, "mdd_pct": b.mdd_pct, "vol_pct": b.vol_pct,
            "mar": mar(b.cagr_pct, b.mdd_pct), "total_pct": b.total_pct, "annual": b.annual}


def main():
    q = prices.load_series(os.path.join(DATA, "qqq_weekly_adj.csv"))
    t = prices.load_series(os.path.join(DATA, "tqqq_weekly_adj.csv"))
    qdaily = prices.load_series(os.path.join(DATA, "qqq_daily.csv"), "close")
    rc = prices.RateCurve(os.path.join(DATA, "ffr_weekly.csv"))

    qd = [d for d, _ in q]
    qc = [v for _, v in q]
    grid = S.build_grid_wide()
    rep = {"generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "n_rules": len(grid), "cost_bps": COST_BPS}

    # ---------------------------------------------------------- 구간 A: 실제 TQQQ
    rets_a = {"QQQ": prices.to_returns(q), "TQQQ": prices.to_returns(t)}
    dates_a = [d for d in qd if d >= REAL_START and (d in rets_a["TQQQ"] or d == REAL_START)]
    rows_a = run_grid(qd, qc, rets_a, rc, dates_a, grid)
    rep["A"] = {
        "label": "실제 TQQQ",
        "period": [dates_a[0].isoformat(), dates_a[-1].isoformat(), len(dates_a)],
        "rows": rows_a,
        "cagr": dist(rows_a, "cagr_pct"), "mdd": dist(rows_a, "mdd_pct"),
        "mar": dist(rows_a, "mar"), "pct_in": dist(rows_a, "pct_in_tqqq"),
        "bench": {"TQQQ": bench(dates_a, rets_a, "TQQQ"), "QQQ": bench(dates_a, rets_a, "QQQ")},
    }
    beat_c = sum(1 for x in rows_a if x["cagr_pct"] > rep["A"]["bench"]["TQQQ"]["cagr_pct"])
    beat_m = sum(1 for x in rows_a if x["mar"] > rep["A"]["bench"]["TQQQ"]["mar"])
    rep["A"]["beat_tqqq_cagr"] = beat_c
    rep["A"]["beat_tqqq_mar"] = beat_m

    # 표본내/표본외
    is_d = [d for d in dates_a if d <= OOS_SPLIT]
    oos_d = [d for d in dates_a if d >= OOS_SPLIT]
    is_rows = run_grid(qd, qc, rets_a, rc, is_d, grid)
    oos_rows = run_grid(qd, qc, rets_a, rc, oos_d, grid)
    oos_by = {x["rule"]: x for x in oos_rows}
    best_is = max(is_rows, key=lambda x: x["cagr_pct"])
    oos_sorted = sorted(oos_rows, key=lambda x: -x["cagr_pct"])
    rep["A"]["split"] = {
        "is_period": [is_d[0].isoformat(), is_d[-1].isoformat()],
        "oos_period": [oos_d[0].isoformat(), oos_d[-1].isoformat()],
        "best_is_rule": best_is["rule"], "best_is_cagr": best_is["cagr_pct"],
        "oos_cagr_of_that": oos_by[best_is["rule"]]["cagr_pct"],
        "oos_rank_of_that": oos_sorted.index(oos_by[best_is["rule"]]) + 1,
        "is_median": dist(is_rows, "cagr_pct")["median"],
        "oos_median": dist(oos_rows, "cagr_pct")["median"],
        "oos_bench_tqqq": bench(oos_d, rets_a, "TQQQ")["cagr_pct"],
        "is_bench_tqqq": bench(is_d, rets_a, "TQQQ")["cagr_pct"],
    }
    # 규칙 하나의 표본외 성적은 우연일 수 있다. 규칙 **전체 순위**가 유지되는지를 본다.
    is_by = {x["rule"]: x for x in is_rows}
    names = [x["rule"] for x in is_rows]
    ri = {n: i for i, n in enumerate(sorted(names, key=lambda n: -is_by[n]["cagr_pct"]))}
    ro = {n: i for i, n in enumerate(sorted(names, key=lambda n: -oos_by[n]["cagr_pct"]))}
    rep["A"]["split"]["rank_corr_is_oos"] = st.correlation([ri[n] for n in names], [ro[n] for n in names])
    top5 = sorted(names, key=lambda n: -is_by[n]["cagr_pct"])[:5]
    rep["A"]["split"]["is_top5_still_top10_oos"] = sum(1 for n in top5 if ro[n] < 10)
    rep["A"]["split"]["is_top5_oos_ranks"] = [(n, ro[n] + 1) for n in top5]

    # ---------------------------------------------------------- 시뮬 검증
    dd = [d for d, _ in qdaily if REAL_START <= d <= dates_a[-1]]
    dc = [v for d, v in qdaily if REAL_START <= d <= dates_a[-1]]
    real_cagr = rep["A"]["bench"]["TQQQ"]["cagr_pct"]
    fee_fit = LV.fit_fee(dd, dc, 3.0, rc, real_cagr)
    sim_chk = LV.to_weekly(LV.simulate_daily(dd, dc, 3.0, rc, 0.0), [d for d, _ in t])
    rr, sr = prices.to_returns(t), prices.to_returns(sim_chk)
    com = sorted(set(rr) & set(sr))
    rep["sim_validation"] = {
        "fitted_fee_annual_pct": fee_fit,
        "stated_expense_ratio_pct": 0.84,
        "sim_cagr_fee0_pct": LV.cagr_pct(sim_chk),
        "real_cagr_pct": real_cagr,
        "err_fee0_pp": LV.cagr_pct(sim_chk) - real_cagr,
        "weekly_corr": st.correlation([rr[d] for d in com], [sr[d] for d in com]),
        "weekly_mean_abs_diff_pp": st.mean([abs(rr[d] - sr[d]) * 100 for d in com]),
    }

    # ---------------------------------------------------------- 구간 B: 시뮬 TQQQ
    dd2 = [d for d, _ in qdaily if d <= dates_a[-1]]
    dc2 = [v for d, v in qdaily if d <= dates_a[-1]]
    dates_b = [d for d in qd if d >= LONG_START]
    rep["B"] = {"label": "시뮬 TQQQ (일간리셋)", "scenarios": {},
                "period": [dates_b[0].isoformat(), dates_b[-1].isoformat(), len(dates_b)]}
    for label, fee in FEE_SCENARIOS:
        f = fee_fit if fee is None else fee
        sim_w = LV.to_weekly(LV.simulate_daily(dd2, dc2, 3.0, rc, f), dates_b)
        rets_b = {"QQQ": prices.to_returns(q), "TQQQ": prices.to_returns(sim_w)}
        d_b = [d for d in dates_b if d in rets_b["TQQQ"] or d == dates_b[0]]
        rows_b = run_grid(qd, qc, rets_b, rc, d_b, grid)
        rep["B"]["scenarios"][label] = {
            "fee_annual_pct": f,
            "cagr": dist(rows_b, "cagr_pct"), "mdd": dist(rows_b, "mdd_pct"), "mar": dist(rows_b, "mar"),
            "bench_tqqq": bench(d_b, rets_b, "TQQQ"), "bench_qqq": bench(d_b, rets_b, "QQQ"),
            "rows": rows_b if label == "적합" else None,
        }

    # 위기 구간 상세 (적합 시나리오)
    sim_w = LV.to_weekly(LV.simulate_daily(dd2, dc2, 3.0, rc, fee_fit), dates_b)
    rets_b = {"QQQ": prices.to_returns(q), "TQQQ": prices.to_returns(sim_w)}
    crises = [("닷컴 2000-03~2002-10", dt.date(2000, 3, 1), dt.date(2002, 10, 31)),
              ("금융위기 2007-11~2009-03", dt.date(2007, 11, 1), dt.date(2009, 3, 31)),
              ("2022 약세장", dt.date(2021, 11, 1), dt.date(2022, 12, 31))]
    med_rule = sorted(rep["B"]["scenarios"]["적합"]["rows"], key=lambda x: x["cagr_pct"])[len(grid) // 2]
    rep["crisis"] = {"median_rule": med_rule["rule"], "windows": []}
    gmap = dict(grid)
    for nm, lo, hi in crises:
        w = [d for d in dates_b if lo <= d <= hi]
        if len(w) < 10:
            continue
        r = BT.run(w, gmap[med_rule["rule"]](qd, qc), rets_b, MAP2, rc, switch_cost_bps=COST_BPS)
        rep["crisis"]["windows"].append({
            "name": nm, "strategy_total_pct": r.total_pct, "strategy_mdd_pct": r.mdd_pct,
            "tqqq_total_pct": bench(w, rets_b, "TQQQ")["total_pct"],
            "tqqq_mdd_pct": bench(w, rets_b, "TQQQ")["mdd_pct"],
            "qqq_total_pct": bench(w, rets_b, "QQQ")["total_pct"],
        })

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "experiment_2state.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2, sort_keys=True, default=str)

    A = rep["A"]
    print("[구간 A — 실제 TQQQ] %s ~ %s (%d주), 규칙 %d개" % tuple(A["period"] + [rep["n_rules"]]))
    print("  TQQQ 바이앤홀드  CAGR %+7.2f%%  MDD %7.2f%%  MAR %.3f" % (
        A["bench"]["TQQQ"]["cagr_pct"], A["bench"]["TQQQ"]["mdd_pct"], A["bench"]["TQQQ"]["mar"]))
    print("  QQQ  바이앤홀드  CAGR %+7.2f%%  MDD %7.2f%%  MAR %.3f" % (
        A["bench"]["QQQ"]["cagr_pct"], A["bench"]["QQQ"]["mdd_pct"], A["bench"]["QQQ"]["mar"]))
    for k, lbl in (("cagr", "CAGR"), ("mdd", "MDD "), ("mar", "MAR ")):
        d = A[k]
        print("  규칙 %s  최저 %+8.3f | 25%% %+8.3f | 중앙 %+8.3f | 75%% %+8.3f | 최고 %+8.3f" % (
            lbl, d["min"], d["p25"], d["median"], d["p75"], d["max"]))
    print("  TQQQ 보유보다 CAGR 높은 규칙 %d/%d,  MAR 높은 규칙 %d/%d" % (
        A["beat_tqqq_cagr"], rep["n_rules"], A["beat_tqqq_mar"], rep["n_rules"]))
    sp = A["split"]
    print("  표본내·표본외 순위상관 %+.3f  ·  표본내 top5 중 표본외 top10 잔류 %d/5  %s" % (
        sp["rank_corr_is_oos"], sp["is_top5_still_top10_oos"],
        ", ".join("%s→%d위" % (n, r) for n, r in sp["is_top5_oos_ranks"])))
    print("  표본내 최고 %s (%+.2f%%) → 표본외 %+.2f%% (%d/%d위). 표본외 TQQQ 보유 %+.2f%%" % (
        sp["best_is_rule"], sp["best_is_cagr"], sp["oos_cagr_of_that"],
        sp["oos_rank_of_that"], rep["n_rules"], sp["oos_bench_tqqq"]))
    sv = rep["sim_validation"]
    print("\n[시뮬 검증] 보수0%% 시뮬 %+.2f%% vs 실제 %+.2f%% (차 %+.2f%%p) · 주간상관 %.4f · 적합보수 %.2f%%" % (
        sv["sim_cagr_fee0_pct"], sv["real_cagr_pct"], sv["err_fee0_pp"], sv["weekly_corr"],
        sv["fitted_fee_annual_pct"]))
    print("\n[구간 B — 시뮬 TQQQ] %s ~ %s (%d주)" % tuple(rep["B"]["period"]))
    for label, sc in rep["B"]["scenarios"].items():
        print("  %-7s(보수 %+5.2f%%)  TQQQ보유 CAGR %+8.2f%% MDD %7.2f%% | 규칙 중앙 CAGR %+7.2f%% MDD %7.2f%% MAR %.3f" % (
            label, sc["fee_annual_pct"], sc["bench_tqqq"]["cagr_pct"], sc["bench_tqqq"]["mdd_pct"],
            sc["cagr"]["median"], sc["mdd"]["median"], sc["mar"]["median"]))
    print("\n[위기 구간 — 중앙값 규칙 %s]" % rep["crisis"]["median_rule"])
    for w in rep["crisis"]["windows"]:
        print("  %-24s 전략 %+9.2f%% (MDD %7.2f%%) | TQQQ %+10.2f%% (MDD %7.2f%%) | QQQ %+8.2f%%" % (
            w["name"], w["strategy_total_pct"], w["strategy_mdd_pct"],
            w["tqqq_total_pct"], w["tqqq_mdd_pct"], w["qqq_total_pct"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
