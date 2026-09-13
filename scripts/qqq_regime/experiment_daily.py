# -*- coding: utf-8 -*-
"""일간 전환 실험 — 2상태(TQQQ/현금)를 매일 갈아탄다.

2상태 주간 실험에서 닷컴 구간 전략 손실이 −54.23%였다. 주간 종가로만 전환하므로
급락을 며칠씩 맞고 나가기 때문이다. **일간 전환이 그것을 줄이는가, 비용이 그 이득을 먹는가.**

규칙 60개는 주간 그리드와 **길이가 1:1로 짝지어져 있다** (1주 = 5거래일).
같은 달력 길이·같은 구간·같은 비용에서 전환 주기만 바꿔 비교한다.

    python3 scripts/qqq_regime/experiment_daily.py
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
COSTS = (0.0, 5.0, 10.0, 20.0, 50.0)
MAP2 = {S.UP: "TQQQ", S.DOWN: None, S.NEUTRAL: None}
DPY = 252   # 일간 연율화 주기
WPY = 52


def mar(c, m):
    return None if (c is None or not m) else c / abs(m)


def row_of(r, name):
    d = {"rule": name, "cagr_pct": r.cagr_pct, "mdd_pct": r.mdd_pct, "vol_pct": r.vol_pct,
         "mar": mar(r.cagr_pct, r.mdd_pct), "switches_per_year": r.switches_per_year,
         "annual": r.annual}
    if r.weeks_in:
        tot = sum(r.weeks_in.values())
        d["pct_in_tqqq"] = 100.0 * r.weeks_in[S.UP] / tot if tot else None
    return d


def grid_run(dates, sig_dates, sig_closes, grid, rets, rc, cost, ppy):
    return [row_of(BT.run(dates, fn(sig_dates, sig_closes), rets, MAP2, rc,
                          switch_cost_bps=cost, periods_per_year=ppy), name)
            for name, fn in grid]


def dist(rows, key):
    v = sorted(x[key] for x in rows if x.get(key) is not None)
    if not v:
        return None
    q = st.quantiles(v, n=4) if len(v) > 3 else [v[0], st.median(v), v[-1]]
    return {"n": len(v), "min": v[0], "p25": q[0], "median": st.median(v),
            "p75": q[2], "max": v[-1], "mean": st.mean(v)}


def bench(dates, rets, sym, ppy):
    b = BT.buy_and_hold(dates, rets, sym, periods_per_year=ppy)
    return {"cagr_pct": b.cagr_pct, "mdd_pct": b.mdd_pct, "vol_pct": b.vol_pct,
            "mar": mar(b.cagr_pct, b.mdd_pct), "total_pct": b.total_pct}


def main():
    # ----------------------------------------------------------------- 데이터
    qw = prices.load_series(os.path.join(DATA, "qqq_weekly_adj.csv"))
    tw = prices.load_series(os.path.join(DATA, "tqqq_weekly_adj.csv"))
    rc = prices.RateCurve(os.path.join(DATA, "ffr_weekly.csv"))

    q_tr = prices.build_daily_total_return(
        prices.load_series(os.path.join(DATA, "qqq_daily.csv"), "close"),
        prices.load_weekly_factor(os.path.join(DATA, "qqq_weekly_factor.csv")))
    t_tr = prices.build_daily_total_return(
        prices.load_series(os.path.join(DATA, "tqqq_daily.csv"), "close"),
        prices.load_weekly_factor(os.path.join(DATA, "tqqq_weekly_factor.csv")))
    q_px = prices.load_series(os.path.join(DATA, "qqq_daily.csv"), "close")

    dd = [d for d, _ in q_tr]
    dc = [v for _, v in q_tr]
    wd = [d for d, _ in qw]
    wc = [v for _, v in qw]
    gd, gw = S.build_grid_daily(), S.build_grid_wide()

    rep = {"generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "n_rules": len(gd), "cost_bps": COST_BPS}

    # ------------------------------------------------- 구간 A (실제 TQQQ)
    rets_d = {"QQQ": prices.to_returns(q_tr), "TQQQ": prices.to_returns(t_tr)}
    rets_w = {"QQQ": prices.to_returns(qw), "TQQQ": prices.to_returns(tw)}
    dA = [d for d in dd if d >= REAL_START and (d in rets_d["TQQQ"] or d == REAL_START)]
    wA = [d for d in wd if d >= REAL_START and (d in rets_w["TQQQ"] or d == REAL_START)]

    rows_d = grid_run(dA, dd, dc, gd, rets_d, rc, COST_BPS, DPY)
    rows_w = grid_run(wA, wd, wc, gw, rets_w, rc, COST_BPS, WPY)
    bt = bench(dA, rets_d, "TQQQ", DPY)
    rep["A"] = {
        "period_daily": [dA[0].isoformat(), dA[-1].isoformat(), len(dA)],
        "period_weekly": [wA[0].isoformat(), wA[-1].isoformat(), len(wA)],
        "daily": {"rows": rows_d, "cagr": dist(rows_d, "cagr_pct"), "mdd": dist(rows_d, "mdd_pct"),
                  "mar": dist(rows_d, "mar"), "sw": dist(rows_d, "switches_per_year")},
        "weekly": {"rows": rows_w, "cagr": dist(rows_w, "cagr_pct"), "mdd": dist(rows_w, "mdd_pct"),
                   "mar": dist(rows_w, "mar"), "sw": dist(rows_w, "switches_per_year")},
        "bench_tqqq": bt, "bench_qqq": bench(dA, rets_d, "QQQ", DPY),
        "beat_tqqq_cagr_daily": sum(1 for x in rows_d if x["cagr_pct"] > bt["cagr_pct"]),
        "beat_tqqq_mar_daily": sum(1 for x in rows_d if x["mar"] > bt["mar"]),
    }

    # 짝 비교
    md, mw = {x["rule"]: x for x in rows_d}, {x["rule"]: x for x in rows_w}
    pairs = []
    for w, d in S.pair_weekly_daily():
        pairs.append({"weekly": w, "daily": d,
                      "cagr_w": mw[w]["cagr_pct"], "cagr_d": md[d]["cagr_pct"],
                      "d_cagr": md[d]["cagr_pct"] - mw[w]["cagr_pct"],
                      "mdd_w": mw[w]["mdd_pct"], "mdd_d": md[d]["mdd_pct"],
                      "d_mdd": abs(mw[w]["mdd_pct"]) - abs(md[d]["mdd_pct"]),
                      "mar_w": mw[w]["mar"], "mar_d": md[d]["mar"],
                      "sw_w": mw[w]["switches_per_year"], "sw_d": md[d]["switches_per_year"]})
    rep["A"]["pairs"] = pairs
    rep["A"]["pair_summary"] = {
        "daily_better_cagr": sum(1 for p in pairs if p["d_cagr"] > 0),
        "daily_better_mdd": sum(1 for p in pairs if p["d_mdd"] > 0),
        "daily_better_mar": sum(1 for p in pairs if p["mar_d"] > p["mar_w"]),
        "median_d_cagr": st.median([p["d_cagr"] for p in pairs]),
        "median_d_mdd": st.median([p["d_mdd"] for p in pairs]),
        "median_sw_w": st.median([p["sw_w"] for p in pairs]),
        "median_sw_d": st.median([p["sw_d"] for p in pairs]),
        "n": len(pairs),
    }

    # 비용 민감도 — 일간 vs 주간
    rep["A"]["cost"] = {}
    for c in COSTS:
        rd = grid_run(dA, dd, dc, gd, rets_d, rc, c, DPY)
        rw = grid_run(wA, wd, wc, gw, rets_w, rc, c, WPY)
        rep["A"]["cost"]["%.0fbp" % c] = {
            "daily_median": dist(rd, "cagr_pct")["median"], "daily_max": dist(rd, "cagr_pct")["max"],
            "weekly_median": dist(rw, "cagr_pct")["median"], "weekly_max": dist(rw, "cagr_pct")["max"],
        }

    # 표본내/표본외 (일간)
    isd = [d for d in dA if d <= OOS_SPLIT]
    ood = [d for d in dA if d >= OOS_SPLIT]
    ri = grid_run(isd, dd, dc, gd, rets_d, rc, COST_BPS, DPY)
    ro = grid_run(ood, dd, dc, gd, rets_d, rc, COST_BPS, DPY)
    rob = {x["rule"]: x for x in ro}
    names = [x["rule"] for x in ri]
    ib = {x["rule"]: x for x in ri}
    rk_i = {n: i for i, n in enumerate(sorted(names, key=lambda n: -ib[n]["cagr_pct"]))}
    rk_o = {n: i for i, n in enumerate(sorted(names, key=lambda n: -rob[n]["cagr_pct"]))}
    best = max(ri, key=lambda x: x["cagr_pct"])
    top5 = sorted(names, key=lambda n: -ib[n]["cagr_pct"])[:5]
    rep["A"]["split"] = {
        "is_period": [isd[0].isoformat(), isd[-1].isoformat()],
        "oos_period": [ood[0].isoformat(), ood[-1].isoformat()],
        "best_is_rule": best["rule"], "best_is_cagr": best["cagr_pct"],
        "oos_cagr_of_that": rob[best["rule"]]["cagr_pct"],
        "oos_rank_of_that": rk_o[best["rule"]] + 1,
        "rank_corr": st.correlation([rk_i[n] for n in names], [rk_o[n] for n in names]),
        "top5_still_top10": sum(1 for n in top5 if rk_o[n] < 10),
        "top5_oos_ranks": [(n, rk_o[n] + 1) for n in top5],
        "is_median": dist(ri, "cagr_pct")["median"], "oos_median": dist(ro, "cagr_pct")["median"],
        "oos_bench_tqqq": bench(ood, rets_d, "TQQQ", DPY)["cagr_pct"],
    }

    # ------------------------------------------------- 구간 B (시뮬 TQQQ)
    px_d = [d for d, _ in q_px if d <= dA[-1]]
    px_c = [v for d, v in q_px if d <= dA[-1]]
    fee = LV.fit_fee([d for d in px_d if d >= REAL_START],
                     [v for d, v in zip(px_d, px_c) if d >= REAL_START], 3.0, rc, bt["cagr_pct"])
    sim = LV.simulate_daily(px_d, px_c, 3.0, rc, fee)
    rets_bd = {"QQQ": prices.to_returns(q_tr), "TQQQ": prices.to_returns(sim)}
    simw = LV.to_weekly(sim, wd)
    rets_bw = {"QQQ": prices.to_returns(qw), "TQQQ": prices.to_returns(simw)}
    dB = [d for d in dd if d >= LONG_START and (d in rets_bd["TQQQ"] or d == LONG_START)]
    wB = [d for d in wd if d >= LONG_START and (d in rets_bw["TQQQ"] or d == LONG_START)]
    rbd = grid_run(dB, dd, dc, gd, rets_bd, rc, COST_BPS, DPY)
    rbw = grid_run(wB, wd, wc, gw, rets_bw, rc, COST_BPS, WPY)
    rep["B"] = {
        "fee_annual_pct": fee,
        "period": [dB[0].isoformat(), dB[-1].isoformat(), len(dB)],
        "daily": {"cagr": dist(rbd, "cagr_pct"), "mdd": dist(rbd, "mdd_pct"),
                  "mar": dist(rbd, "mar"), "sw": dist(rbd, "switches_per_year"), "rows": rbd},
        "weekly": {"cagr": dist(rbw, "cagr_pct"), "mdd": dist(rbw, "mdd_pct"),
                   "mar": dist(rbw, "mar"), "sw": dist(rbw, "switches_per_year")},
        "bench_tqqq": bench(dB, rets_bd, "TQQQ", DPY),
        "bench_qqq": bench(dB, rets_bd, "QQQ", DPY),
    }
    rep["B"]["cost"] = {}
    for c in COSTS:
        rd = grid_run(dB, dd, dc, gd, rets_bd, rc, c, DPY)
        rw = grid_run(wB, wd, wc, gw, rets_bw, rc, c, WPY)
        rep["B"]["cost"]["%.0fbp" % c] = {
            "daily_median": dist(rd, "cagr_pct")["median"], "weekly_median": dist(rw, "cagr_pct")["median"],
            "daily_mdd_median": dist(rd, "mdd_pct")["median"], "weekly_mdd_median": dist(rw, "mdd_pct")["median"]}

    # 구간 B 짝 비교 — 전환 주기 효과만 분리한다
    mbd, mbw = {x["rule"]: x for x in rbd}, {x["rule"]: x for x in rbw}
    pb = [{"weekly": w, "daily": d, "cagr_w": mbw[w]["cagr_pct"], "cagr_d": mbd[d]["cagr_pct"],
           "d_cagr": mbd[d]["cagr_pct"] - mbw[w]["cagr_pct"],
           "mdd_w": mbw[w]["mdd_pct"], "mdd_d": mbd[d]["mdd_pct"],
           "d_mdd": abs(mbw[w]["mdd_pct"]) - abs(mbd[d]["mdd_pct"])}
          for w, d in S.pair_weekly_daily()]
    rep["B"]["pairs"] = pb
    rep["B"]["pair_summary"] = {
        "n": len(pb),
        "daily_better_cagr": sum(1 for x in pb if x["d_cagr"] > 0),
        "daily_better_mdd": sum(1 for x in pb if x["d_mdd"] > 0),
        "median_d_cagr": st.median([x["d_cagr"] for x in pb]),
        "median_d_mdd": st.median([x["d_mdd"] for x in pb])}

    # 위기 구간 — **짝지은 규칙**으로만 비교한다.
    # 서로 다른 규칙끼리 비교하면 「전환 주기 효과」와 「규칙 효과」가 섞여 결론이 오염된다.
    pair_map = dict(S.pair_weekly_daily())
    med_w = sorted(rbw, key=lambda x: x["cagr_pct"])[len(gw) // 2]["rule"]
    probes = [("중앙값 규칙", med_w, pair_map[med_w]),
              ("고전 200일선", "sma40_b0", pair_map["sma40_b0"])]
    gdm, gwm = dict(gd), dict(gw)
    rep["crisis"] = {"probes": [], "windows_def": []}
    for label, wr, dr in probes:
        entry = {"label": label, "weekly_rule": wr, "daily_rule": dr, "windows": []}
        for nm, lo, hi in (("닷컴 2000-03~2002-10", dt.date(2000, 3, 1), dt.date(2002, 10, 31)),
                           ("금융위기 2007-11~2009-03", dt.date(2007, 11, 1), dt.date(2009, 3, 31)),
                           ("2020 코로나 2~4월", dt.date(2020, 2, 1), dt.date(2020, 4, 30)),
                           ("2022 약세장", dt.date(2021, 11, 1), dt.date(2022, 12, 31))):
            w1 = [d for d in dB if lo <= d <= hi]
            w2 = [d for d in wB if lo <= d <= hi]
            if len(w1) < 20 or len(w2) < 5:
                continue
            rdd = BT.run(w1, gdm[dr](dd, dc), rets_bd, MAP2, rc, switch_cost_bps=COST_BPS, periods_per_year=DPY)
            rww = BT.run(w2, gwm[wr](wd, wc), rets_bw, MAP2, rc, switch_cost_bps=COST_BPS, periods_per_year=WPY)
            entry["windows"].append({
                "name": nm,
                "daily_total_pct": rdd.total_pct, "daily_mdd_pct": rdd.mdd_pct, "daily_switches": rdd.switches,
                "weekly_total_pct": rww.total_pct, "weekly_mdd_pct": rww.mdd_pct, "weekly_switches": rww.switches,
                "tqqq_total_pct": bench(w1, rets_bd, "TQQQ", DPY)["total_pct"],
                "qqq_total_pct": bench(w1, rets_bd, "QQQ", DPY)["total_pct"]})
        rep["crisis"]["probes"].append(entry)

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "experiment_daily.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2, sort_keys=True, default=str)

    A, B, ps = rep["A"], rep["B"], rep["A"]["pair_summary"]
    print("[구간 A] 일간 %s~%s (%d일) · 주간 %d주 · 규칙 %d쌍" % (
        A["period_daily"][0], A["period_daily"][1], A["period_daily"][2], A["period_weekly"][2], ps["n"]))
    print("  TQQQ 바이앤홀드 CAGR %+.2f%% MDD %.2f%% MAR %.3f" % (
        A["bench_tqqq"]["cagr_pct"], A["bench_tqqq"]["mdd_pct"], A["bench_tqqq"]["mar"]))
    for k in ("daily", "weekly"):
        g = A[k]
        print("  %-6s CAGR 중앙 %+7.2f%% (범위 %+7.2f~%+7.2f) | MDD 중앙 %7.2f%% | MAR 중앙 %.3f | 전환 중앙 %.1f회/년"
              % (k, g["cagr"]["median"], g["cagr"]["min"], g["cagr"]["max"],
                 g["mdd"]["median"], g["mar"]["median"], g["sw"]["median"]))
    print("  짝 비교 (%d쌍): 일간이 CAGR 우세 %d · 낙폭 우세 %d · MAR 우세 %d" % (
        ps["n"], ps["daily_better_cagr"], ps["daily_better_mdd"], ps["daily_better_mar"]))
    print("          CAGR 차 중앙 %+.2f%%p · 낙폭 개선 중앙 %+.2f%%p · 전환 %.1f→%.1f회/년" % (
        ps["median_d_cagr"], ps["median_d_mdd"], ps["median_sw_w"], ps["median_sw_d"]))
    print("  TQQQ 보유보다 나은 일간 규칙: CAGR %d/%d · MAR %d/%d" % (
        A["beat_tqqq_cagr_daily"], rep["n_rules"], A["beat_tqqq_mar_daily"], rep["n_rules"]))
    print("\n[비용 민감도 — 구간 A, CAGR 중앙값]")
    for c in COSTS:
        v = A["cost"]["%.0fbp" % c]
        print("  %-5s 일간 %+7.2f%%  주간 %+7.2f%%  (차 %+6.2f%%p)" % (
            "%.0fbp" % c, v["daily_median"], v["weekly_median"], v["daily_median"] - v["weekly_median"]))
    sp = A["split"]
    print("\n[표본외 — 일간] 순위상관 %+.3f · top5 중 top10 잔류 %d/5 · 표본내 최고 %s(%+.2f%%)→표본외 %+.2f%%(%d위)"
          % (sp["rank_corr"], sp["top5_still_top10"], sp["best_is_rule"], sp["best_is_cagr"],
             sp["oos_cagr_of_that"], sp["oos_rank_of_that"]))
    print("\n[구간 B — 시뮬 TQQQ %s~%s, 보수 %.2f%%]" % (B["period"][0], B["period"][1], B["fee_annual_pct"]))
    print("  TQQQ 바이앤홀드 CAGR %+.2f%% MDD %.2f%% | QQQ %+.2f%% MDD %.2f%%" % (
        B["bench_tqqq"]["cagr_pct"], B["bench_tqqq"]["mdd_pct"],
        B["bench_qqq"]["cagr_pct"], B["bench_qqq"]["mdd_pct"]))
    for k in ("daily", "weekly"):
        g = B[k]
        print("  %-6s CAGR 중앙 %+7.2f%% | MDD 중앙 %7.2f%% | MAR 중앙 %.3f | 전환 중앙 %.1f회/년" % (
            k, g["cagr"]["median"], g["mdd"]["median"], g["mar"]["median"], g["sw"]["median"]))
    print("\n[비용 민감도 — 구간 B, CAGR 중앙값]")
    for c in COSTS:
        v = B["cost"]["%.0fbp" % c]
        print("  %-5s 일간 %+7.2f%% (MDD %7.2f%%)  주간 %+7.2f%% (MDD %7.2f%%)" % (
            "%.0fbp" % c, v["daily_median"], v["daily_mdd_median"], v["weekly_median"], v["weekly_mdd_median"]))
    pbs = B["pair_summary"]
    print("  짝 비교 (%d쌍): 일간 CAGR 우세 %d · 낙폭 우세 %d | CAGR 차 중앙 %+.2f%%p · 낙폭 개선 중앙 %+.2f%%p"
          % (pbs["n"], pbs["daily_better_cagr"], pbs["daily_better_mdd"],
             pbs["median_d_cagr"], pbs["median_d_mdd"]))
    print("\n[위기 구간 — 짝지은 규칙으로만 비교]")
    for pr in rep["crisis"]["probes"]:
        print("  · %s: 주간 `%s` ↔ 일간 `%s`" % (pr["label"], pr["weekly_rule"], pr["daily_rule"]))
        for w in pr["windows"]:
            print("      %-24s 일간 %+9.2f%% (MDD %7.2f%%, 전환 %3d) | 주간 %+9.2f%% (MDD %7.2f%%, 전환 %2d) | TQQQ %+10.2f%%"
                  % (w["name"], w["daily_total_pct"], w["daily_mdd_pct"], w["daily_switches"],
                     w["weekly_total_pct"], w["weekly_mdd_pct"], w["weekly_switches"], w["tqqq_total_pct"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
