# -*- coding: utf-8 -*-
"""변동성 게이트 실험 — 추세 신호에 「조용할 때만 들어간다」를 얹는다.

앞선 두 실험에서 기각된 것:
    · SQQQ 숏 다리  → 35개 규칙 전부 악화
    · 일간 전환      → 톱질로 두 구간 모두 악화

남은 가설: **가격만 보는 추세 신호가 톱질에 약하다면, 변동성을 게이트로 쓰면 어떤가.**
근거는 적합이 아니라 이론이다 — 일간리셋 L배 상품의 변동성 끌림은 대략 (L²−L)/2·σ² 이고
L=3 이면 3σ² 다. 3배 위험프리미엄(연 15~18%)을 끌림이 넘어서는 지점이 σ≈22% 이므로
절대 임계는 20~35%를 훑고, 시대에 따른 수준 변화를 흡수하는 백분위 게이트도 함께 본다.

세 가지를 서로 다른 축으로 잰다:
    1. 추세 + 게이트   (60개 추세 규칙 × 게이트 14개 — **짝 비교로 게이트 효과만 분리**)
    2. 게이트 단독     (추세 없이 변동성만)
    3. 변동성 타게팅   (0/1 이 아니라 연속 비중)

    python3 scripts/qqq_regime/experiment_vol.py
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
VOL_TARGETS = (10.0, 15.0, 20.0, 25.0)


def mar(c, m):
    return None if (c is None or not m) else c / abs(m)


def summ(r, name):
    return {"rule": name, "cagr_pct": r.cagr_pct, "mdd_pct": r.mdd_pct, "vol_pct": r.vol_pct,
            "mar": mar(r.cagr_pct, r.mdd_pct), "turnover_per_year": r.switches_per_year,
            "mean_weight": getattr(r, "mean_weight", None), "annual": r.annual}


def dist(rows, key):
    v = sorted(x[key] for x in rows if x.get(key) is not None)
    if not v:
        return None
    q = st.quantiles(v, n=4) if len(v) > 3 else [v[0], st.median(v), v[-1]]
    return {"n": len(v), "min": v[0], "p25": q[0], "median": st.median(v),
            "p75": q[2], "max": v[-1], "mean": st.mean(v)}


def build_gates(wd, wc):
    """{게이트명: {date: bool}}"""
    out = {}
    for name, n, (kind, a, lb) in S.build_vol_configs():
        v = S.realized_vol(wd, wc, n)
        out[name] = S.vol_gate_abs(v, a) if kind == "abs" else S.vol_gate_pct(v, wd, a, lb)
    return out


def main():
    qw = prices.load_series(os.path.join(DATA, "qqq_weekly_adj.csv"))
    tw = prices.load_series(os.path.join(DATA, "tqqq_weekly_adj.csv"))
    q_px = prices.load_series(os.path.join(DATA, "qqq_daily.csv"), "close")
    rc = prices.RateCurve(os.path.join(DATA, "ffr_weekly.csv"))

    wd = [d for d, _ in qw]
    wc = [v for _, v in qw]
    grid = S.build_grid_wide()
    gates = build_gates(wd, wc)
    vol13 = S.realized_vol(wd, wc, 13)
    vol26 = S.realized_vol(wd, wc, 26)

    rep = {"generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "n_trend_rules": len(grid), "n_gates": len(gates), "cost_bps": COST_BPS,
           "vol_summary": {"median_13w": st.median(list(vol13.values())),
                           "p75_13w": st.quantiles(sorted(vol13.values()), n=4)[2],
                           "max_13w": max(vol13.values())}}

    # 구간 A: 실제 TQQQ / 구간 B: 시뮬 TQQQ
    rets_a = {"QQQ": prices.to_returns(qw), "TQQQ": prices.to_returns(tw)}
    dA = [d for d in wd if d >= REAL_START and (d in rets_a["TQQQ"] or d == REAL_START)]
    bt_a = BT.buy_and_hold(dA, rets_a, "TQQQ")

    px_d = [d for d, _ in q_px if d <= dA[-1]]
    px_c = [v for d, v in q_px if d <= dA[-1]]
    fee = LV.fit_fee([d for d in px_d if d >= REAL_START],
                     [v for d, v in zip(px_d, px_c) if d >= REAL_START], 3.0, rc, bt_a.cagr_pct)
    simw = LV.to_weekly(LV.simulate_daily(px_d, px_c, 3.0, rc, fee), wd)
    rets_b = {"QQQ": prices.to_returns(qw), "TQQQ": prices.to_returns(simw)}
    dB = [d for d in wd if d >= LONG_START and (d in rets_b["TQQQ"] or d == LONG_START)]

    periods = {"A": (dA, rets_a), "B": (dB, rets_b)}
    rep["fee_annual_pct"] = fee

    for key, (dates, rets) in periods.items():
        base = [summ(BT.run(dates, fn(wd, wc), rets, MAP2, rc, switch_cost_bps=COST_BPS), nm)
                for nm, fn in grid]
        bmap = {x["rule"]: x for x in base}
        bench_t = BT.buy_and_hold(dates, rets, "TQQQ")
        bench_q = BT.buy_and_hold(dates, rets, "QQQ")

        # 1. 추세 + 게이트 (짝 비교)
        gated = {}
        for gname, g in gates.items():
            rows = []
            for nm, fn in grid:
                r = BT.run(dates, S.gate_states(fn(wd, wc), g), rets, MAP2, rc, switch_cost_bps=COST_BPS)
                rows.append(summ(r, nm))
            gm = {x["rule"]: x for x in rows}
            pairs = [{"rule": nm, "cagr_base": bmap[nm]["cagr_pct"], "cagr_gated": gm[nm]["cagr_pct"],
                      "d_cagr": gm[nm]["cagr_pct"] - bmap[nm]["cagr_pct"],
                      "mdd_base": bmap[nm]["mdd_pct"], "mdd_gated": gm[nm]["mdd_pct"],
                      "d_mdd": abs(bmap[nm]["mdd_pct"]) - abs(gm[nm]["mdd_pct"]),
                      "mar_base": bmap[nm]["mar"], "mar_gated": gm[nm]["mar"]} for nm, _ in grid]
            gated[gname] = {
                "cagr": dist(rows, "cagr_pct"), "mdd": dist(rows, "mdd_pct"), "mar": dist(rows, "mar"),
                "turnover": dist(rows, "turnover_per_year"),
                "improved_cagr": sum(1 for p in pairs if p["d_cagr"] > 0),
                "improved_mdd": sum(1 for p in pairs if p["d_mdd"] > 0),
                "improved_mar": sum(1 for p in pairs if p["mar_gated"] > p["mar_base"]),
                "median_d_cagr": st.median([p["d_cagr"] for p in pairs]),
                "median_d_mdd": st.median([p["d_mdd"] for p in pairs]),
                "rows": rows if key == "A" else None,
            }

        # 2. 게이트 단독 (추세 없음)
        solo = []
        for gname, g in gates.items():
            states = {d: (S.UP if g.get(d) is True else S.NEUTRAL) for d in wd}
            solo.append(summ(BT.run(dates, states, rets, MAP2, rc, switch_cost_bps=COST_BPS), gname))

        # 3. 변동성 타게팅 (연속 비중) — 추세 없음 / 추세와 결합
        vt = []
        for n, vb in (("13w", vol13), ("26w", vol26)):
            for tgt in VOL_TARGETS:
                w = S.vol_target_weight(vb, tgt)
                r = BT.run_weights(dates, w, rets, "TQQQ", rc, switch_cost_bps=COST_BPS)
                vt.append(summ(r, "vt%s_t%.0f" % (n, tgt)))
                for tn in ("sma40_b0", "mom26_t6"):
                    tf = dict(grid)[tn]
                    tstates = tf(wd, wc)
                    w2 = {d: (w.get(d, 0.0) if tstates.get(d) == S.UP else 0.0) for d in wd}
                    r2 = BT.run_weights(dates, w2, rets, "TQQQ", rc, switch_cost_bps=COST_BPS)
                    vt.append(summ(r2, "vt%s_t%.0f+%s" % (n, tgt, tn)))

        rep[key] = {
            "period": [dates[0].isoformat(), dates[-1].isoformat(), len(dates)],
            "bench_tqqq": {"cagr_pct": bench_t.cagr_pct, "mdd_pct": bench_t.mdd_pct,
                           "mar": mar(bench_t.cagr_pct, bench_t.mdd_pct)},
            "bench_qqq": {"cagr_pct": bench_q.cagr_pct, "mdd_pct": bench_q.mdd_pct,
                          "mar": mar(bench_q.cagr_pct, bench_q.mdd_pct)},
            "base": {"cagr": dist(base, "cagr_pct"), "mdd": dist(base, "mdd_pct"),
                     "mar": dist(base, "mar"), "turnover": dist(base, "turnover_per_year")},
            "gated": gated,
            "solo": solo,
            "vol_target": vt,
        }

    # 최선 게이트(구간 B의 MAR 중앙값 기준)로 비용 민감도 + 표본외
    bestg = max(rep["B"]["gated"].items(), key=lambda kv: kv[1]["mar"]["median"])[0]
    rep["best_gate"] = bestg
    rep["cost"] = {}
    for c in COSTS:
        row = {}
        for key, (dates, rets) in periods.items():
            b = [BT.run(dates, fn(wd, wc), rets, MAP2, rc, switch_cost_bps=c).cagr_pct for nm, fn in grid]
            g = [BT.run(dates, S.gate_states(fn(wd, wc), gates[bestg]), rets, MAP2, rc,
                        switch_cost_bps=c).cagr_pct for nm, fn in grid]
            row[key] = {"base_median": st.median(b), "gated_median": st.median(g)}
        rep["cost"]["%.0fbp" % c] = row

    isd = [d for d in dA if d <= OOS_SPLIT]
    ood = [d for d in dA if d >= OOS_SPLIT]
    sp = {}
    for lbl, dts in (("is", isd), ("oos", ood)):
        b = [st.median([BT.run(dts, fn(wd, wc), rets_a, MAP2, rc, switch_cost_bps=COST_BPS).cagr_pct
                        for nm, fn in grid])]
        g = [st.median([BT.run(dts, S.gate_states(fn(wd, wc), gates[bestg]), rets_a, MAP2, rc,
                               switch_cost_bps=COST_BPS).cagr_pct for nm, fn in grid])]
        sp[lbl] = {"base_median": b[0], "gated_median": g[0],
                   "period": [dts[0].isoformat(), dts[-1].isoformat()]}
    rep["split"] = sp

    # 후보 4종을 같은 축에서 위기 구간·표본외로 본다
    TREND = "sma40_b0"
    tf = dict(grid)[TREND]
    def cands(dates, rets, cost=COST_BPS):
        out = {}
        out["추세만 (%s)" % TREND] = BT.run(dates, tf(wd, wc), rets, MAP2, rc, switch_cost_bps=cost)
        out["추세+게이트 (%s)" % bestg] = BT.run(dates, S.gate_states(tf(wd, wc), gates[bestg]),
                                                rets, MAP2, rc, switch_cost_bps=cost)
        w = S.vol_target_weight(vol13, 20.0)
        ts = tf(wd, wc)
        out["타게팅 vt13w_t20"] = BT.run_weights(dates, w, rets, "TQQQ", rc, switch_cost_bps=cost)
        out["타게팅+추세"] = BT.run_weights(
            dates, {d: (w.get(d, 0.0) if ts.get(d) == S.UP else 0.0) for d in wd},
            rets, "TQQQ", rc, switch_cost_bps=cost)
        return out

    rep["candidates"] = {}
    for key, (dates, rets) in periods.items():
        rep["candidates"][key] = {k: summ(v, k) for k, v in cands(dates, rets).items()}
        rep["candidates"][key]["TQQQ 보유"] = summ(BT.buy_and_hold(dates, rets, "TQQQ"), "TQQQ 보유")
        rep["candidates"][key]["QQQ 보유"] = summ(BT.buy_and_hold(dates, rets, "QQQ"), "QQQ 보유")

    rep["candidates"]["split"] = {}
    for lbl, dts in (("is", isd), ("oos", ood)):
        rep["candidates"]["split"][lbl] = {k: summ(v, k) for k, v in cands(dts, rets_a).items()}
        rep["candidates"]["split"][lbl]["TQQQ 보유"] = summ(BT.buy_and_hold(dts, rets_a, "TQQQ"), "TQQQ 보유")

    rep["crisis"] = {"trend_rule": TREND, "gate": bestg, "windows": []}
    for nm, lo, hi in (("닷컴 2000-03~2002-10", dt.date(2000, 3, 1), dt.date(2002, 10, 31)),
                       ("금융위기 2007-11~2009-03", dt.date(2007, 11, 1), dt.date(2009, 3, 31)),
                       ("2020 코로나 2~4월", dt.date(2020, 2, 1), dt.date(2020, 4, 30)),
                       ("2020 회복 5~12월", dt.date(2020, 5, 1), dt.date(2020, 12, 31)),
                       ("2022 약세장", dt.date(2021, 11, 1), dt.date(2022, 12, 31))):
        w = [d for d in dB if lo <= d <= hi]
        if len(w) < 5:
            continue
        e = {"name": nm, "weeks": len(w)}
        e["median_vol_13w"] = st.median([vol13[d] for d in w if d in vol13])
        for k, v in cands(w, rets_b).items():
            ex = None
            if v.weeks_in:
                tot = sum(v.weeks_in.values())
                ex = 100.0 * v.weeks_in[S.UP] / tot if tot else None
            elif getattr(v, "mean_weight", None) is not None:
                ex = 100.0 * v.mean_weight
            e[k] = {"total_pct": v.total_pct, "mdd_pct": v.mdd_pct, "exposure_pct": ex}
        for sym in ("TQQQ", "QQQ"):
            bh = BT.buy_and_hold(w, rets_b, sym)
            e["%s 보유" % sym] = {"total_pct": bh.total_pct, "mdd_pct": bh.mdd_pct, "exposure_pct": 100.0}
        e["전액 현금"] = {"total_pct": BT.run(w, {d: S.NEUTRAL for d in wd}, rets_b, MAP2, rc,
                                              switch_cost_bps=0.0).total_pct,
                          "mdd_pct": 0.0, "exposure_pct": 0.0}
        rep["crisis"]["windows"].append(e)

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "experiment_vol.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2, sort_keys=True, default=str)

    for key in ("A", "B"):
        R = rep[key]
        print("\n[구간 %s] %s ~ %s (%d주)  TQQQ보유 CAGR %+.2f%% MDD %.2f%% MAR %.3f" % (
            key, R["period"][0], R["period"][1], R["period"][2],
            R["bench_tqqq"]["cagr_pct"], R["bench_tqqq"]["mdd_pct"], R["bench_tqqq"]["mar"]))
        b = R["base"]
        print("  게이트 없음(추세만)   CAGR 중앙 %+7.2f%% | MDD 중앙 %7.2f%% | MAR 중앙 %.3f | 회전 %.1f" % (
            b["cagr"]["median"], b["mdd"]["median"], b["mar"]["median"], b["turnover"]["median"]))
        print("  %-14s %8s %9s %7s %7s %7s %7s" % ("게이트", "CAGR중앙", "MDD중앙", "MAR", "CAGR↑", "MDD↑", "MAR↑"))
        for gname, g in sorted(R["gated"].items(), key=lambda kv: -kv[1]["mar"]["median"]):
            print("  %-14s %+8.2f %+9.2f %7.3f %5d/%d %5d/%d %5d/%d" % (
                gname, g["cagr"]["median"], g["mdd"]["median"], g["mar"]["median"],
                g["improved_cagr"], len(grid), g["improved_mdd"], len(grid), g["improved_mar"], len(grid)))
        so = sorted(R["solo"], key=lambda x: -x["mar"])[:3]
        print("  게이트 단독 상위3: " + " | ".join(
            "%s CAGR %+.2f%% MDD %.1f%% MAR %.3f" % (x["rule"], x["cagr_pct"], x["mdd_pct"], x["mar"]) for x in so))
        vt = sorted(R["vol_target"], key=lambda x: -x["mar"])[:4]
        print("  변동성 타게팅 상위4:")
        for x in vt:
            print("      %-24s CAGR %+7.2f%% MDD %7.2f%% MAR %.3f 평균비중 %.2f 회전 %.1f" % (
                x["rule"], x["cagr_pct"], x["mdd_pct"], x["mar"], x["mean_weight"], x["turnover_per_year"]))

    print("\n[최선 게이트 = %s] 비용 민감도 (CAGR 중앙값)" % rep["best_gate"])
    for c in COSTS:
        v = rep["cost"]["%.0fbp" % c]
        print("  %-5s A: 기본 %+7.2f%% → 게이트 %+7.2f%% (%+6.2f%%p) | B: 기본 %+7.2f%% → 게이트 %+7.2f%% (%+6.2f%%p)" % (
            "%.0fbp" % c, v["A"]["base_median"], v["A"]["gated_median"],
            v["A"]["gated_median"] - v["A"]["base_median"],
            v["B"]["base_median"], v["B"]["gated_median"],
            v["B"]["gated_median"] - v["B"]["base_median"]))
    ORDER = ["QQQ 보유", "TQQQ 보유", "추세만 (sma40_b0)", "추세+게이트 (%s)" % rep["best_gate"],
             "타게팅 vt13w_t20", "타게팅+추세"]
    for key in ("A", "B"):
        print("\n[후보 대조 — 구간 %s]" % key)
        for k in ORDER:
            x = rep["candidates"][key][k]
            print("  %-26s CAGR %+8.2f%%  MDD %8.2f%%  MAR %6.3f  평균비중 %s" % (
                k, x["cagr_pct"], x["mdd_pct"], x["mar"] or 0,
                ("%.2f" % x["mean_weight"]) if x["mean_weight"] is not None else "  — "))
    print("\n[위기 구간 — 추세 %s · 게이트 %s]" % (rep["crisis"]["trend_rule"], rep["crisis"]["gate"]))
    for w in rep["crisis"]["windows"]:
        print("  %s" % w["name"])
        print("      (%d주, 13주 실현변동성 중앙 %.1f%%)" % (w["weeks"], w["median_vol_13w"]))
        for k in ORDER + ["전액 현금"]:
            ex = w[k].get("exposure_pct")
            print("      %-26s %+9.2f%%  (MDD %7.2f%%, 노출 %s)" % (
                k, w[k]["total_pct"], w[k]["mdd_pct"], ("%5.1f%%" % ex) if ex is not None else "  — "))
    print("\n[후보별 표본내/표본외 — 구간 A]")
    for k in ORDER[1:]:
        i = rep["candidates"]["split"]["is"].get(k)
        o = rep["candidates"]["split"]["oos"].get(k)
        if i and o:
            print("  %-26s 표본내 %+7.2f%% → 표본외 %+7.2f%%  (MDD 표본외 %7.2f%%)" % (
                k, i["cagr_pct"], o["cagr_pct"], o["mdd_pct"]))
    print("\n[표본내/표본외 — 구간 A]")
    for lbl in ("is", "oos"):
        s_ = rep["split"][lbl]
        print("  %-4s %s~%s  기본 %+7.2f%% → 게이트 %+7.2f%% (%+6.2f%%p)" % (
            lbl, s_["period"][0], s_["period"][1], s_["base_median"], s_["gated_median"],
            s_["gated_median"] - s_["base_median"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
