# -*- coding: utf-8 -*-
"""비대칭 진입/이탈 실험 — 나가는 속도와 들어오는 속도를 따로 정한다.

앞선 실험들의 결말:
    · SQQQ 숏 다리   → 기각 (35개 규칙 전부 악화)
    · 일간 전환       → 기각 (톱질로 두 구간 모두 악화)
    · 변동성 게이트   → 부분 채택 (낙폭 58/60 개선, 2020 V자 회복의 절반을 놓침)

남은 축: **진입과 이탈의 속도를 다르게 하면 그 트레이드오프가 움직이는가.**

주의 — 방향을 헷갈리면 안 된다:
    진입이 느리면  → 닷컴 같은 긴 하락에 강하고, 2020 같은 V자 회복에 약하다
    진입이 빠르면  → 그 반대다
**한쪽이 다른 쪽보다 낫다는 가설이 아니라, 프런티어가 있는지를 보는 실험이다.**
그래서 격자를 두 방향에 대칭으로 깔았다 (진입빠름 132 · 이탈빠름 132 · 대칭 24).

    python3 scripts/qqq_regime/experiment_asym.py
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
GATE = "vol13w_p80"

DOTCOM = ("닷컴 2000-03~2002-10", dt.date(2000, 3, 1), dt.date(2002, 10, 31))
V2020 = ("2020 회복 5~12월", dt.date(2020, 5, 1), dt.date(2020, 12, 31))
WINDOWS = [DOTCOM,
           ("금융위기 2007-11~2009-03", dt.date(2007, 11, 1), dt.date(2009, 3, 31)),
           ("2020 코로나 2~4월", dt.date(2020, 2, 1), dt.date(2020, 4, 30)),
           V2020,
           ("2022 약세장", dt.date(2021, 11, 1), dt.date(2022, 12, 31))]


def mar(c, m):
    return None if (c is None or not m) else c / abs(m)


def dist(rows, key):
    v = sorted(x[key] for x in rows if x.get(key) is not None)
    if not v:
        return None
    q = st.quantiles(v, n=4) if len(v) > 3 else [v[0], st.median(v), v[-1]]
    return {"n": len(v), "min": v[0], "p25": q[0], "median": st.median(v),
            "p75": q[2], "max": v[-1]}


def main():
    qw = prices.load_series(os.path.join(DATA, "qqq_weekly_adj.csv"))
    tw = prices.load_series(os.path.join(DATA, "tqqq_weekly_adj.csv"))
    qp = prices.load_series(os.path.join(DATA, "qqq_daily.csv"), "close")
    rc = prices.RateCurve(os.path.join(DATA, "ffr_weekly.csv"))
    wd = [d for d, _ in qw]
    wc = [v for _, v in qw]

    rets_a = {"QQQ": prices.to_returns(qw), "TQQQ": prices.to_returns(tw)}
    dA = [d for d in wd if d >= REAL_START and (d in rets_a["TQQQ"] or d == REAL_START)]
    fee = LV.fit_fee([d for d, _ in qp if REAL_START <= d <= dA[-1]],
                     [v for d, v in qp if REAL_START <= d <= dA[-1]], 3.0, rc,
                     BT.buy_and_hold(dA, rets_a, "TQQQ").cagr_pct)
    simw = LV.to_weekly(LV.simulate_daily([d for d, _ in qp if d <= dA[-1]],
                                          [v for d, v in qp if d <= dA[-1]], 3.0, rc, fee), wd)
    rets_b = {"QQQ": prices.to_returns(qw), "TQQQ": prices.to_returns(simw)}
    dB = [d for d in wd if d >= LONG_START and (d in rets_b["TQQQ"] or d == LONG_START)]

    vol13 = S.realized_vol(wd, wc, 13)
    gate = S.vol_gate_pct(vol13, wd, 80.0, 104)
    grid = S.build_asym_grid()

    rep = {"generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "n_rules": len(grid), "cost_bps": COST_BPS, "gate": GATE,
           "kinds": {k: sum(1 for _, _, p in grid if S.asym_kind(p) == k)
                     for k in ("대칭", "이탈빠름(진입느림)", "진입빠름(이탈느림)")}}

    periods = {"A": (dA, rets_a), "B": (dB, rets_b)}
    for key, (dates, rets) in periods.items():
        rows = []
        for name, fn, prm in grid:
            states = fn(wd, wc)
            for gated in (False, True):
                stt = S.gate_states(states, gate) if gated else states
                r = BT.run(dates, stt, rets, MAP2, rc, switch_cost_bps=COST_BPS)
                wi = sum(r.weeks_in.values())
                rows.append({
                    "rule": name, "gated": gated, "kind": S.asym_kind(prm), **prm,
                    "cagr_pct": r.cagr_pct, "mdd_pct": r.mdd_pct, "mar": mar(r.cagr_pct, r.mdd_pct),
                    "switches_per_year": r.switches_per_year,
                    "pct_in": 100.0 * r.weeks_in[S.UP] / wi if wi else None})
        bt = BT.buy_and_hold(dates, rets, "TQQQ")
        bq = BT.buy_and_hold(dates, rets, "QQQ")
        by_kind = {}
        for g in (False, True):
            for k in rep["kinds"]:
                sub = [x for x in rows if x["gated"] is g and x["kind"] == k]
                by_kind["%s|%s" % ("게이트" if g else "기본", k)] = {
                    "cagr": dist(sub, "cagr_pct"), "mdd": dist(sub, "mdd_pct"), "mar": dist(sub, "mar")}
        rep[key] = {
            "period": [dates[0].isoformat(), dates[-1].isoformat(), len(dates)],
            "bench": {"TQQQ": {"cagr_pct": bt.cagr_pct, "mdd_pct": bt.mdd_pct,
                               "mar": mar(bt.cagr_pct, bt.mdd_pct)},
                      "QQQ": {"cagr_pct": bq.cagr_pct, "mdd_pct": bq.mdd_pct,
                              "mar": mar(bq.cagr_pct, bq.mdd_pct)}},
            "by_kind": by_kind,
            "rows": rows if key == "B" else None,
        }

    # 두 극단 구간에서의 프런티어 — 닷컴 방어 vs 2020 회복
    front = []
    for name, fn, prm in grid:
        states = fn(wd, wc)
        e = {"rule": name, "kind": S.asym_kind(prm), **prm}
        for gated in (False, True):
            stt = S.gate_states(states, gate) if gated else states
            tag = "게이트" if gated else "기본"
            for wnm, lo, hi in (DOTCOM, V2020):
                w = [d for d in dB if lo <= d <= hi]
                r = BT.run(w, stt, rets_b, MAP2, rc, switch_cost_bps=COST_BPS)
                e["%s|%s" % (tag, "닷컴" if wnm == DOTCOM[0] else "2020회복")] = r.total_pct
            rr = BT.run(dB, stt, rets_b, MAP2, rc, switch_cost_bps=COST_BPS)
            e["%s|CAGR" % tag] = rr.cagr_pct
            e["%s|MDD" % tag] = rr.mdd_pct
            e["%s|MAR" % tag] = mar(rr.cagr_pct, rr.mdd_pct)
        front.append(e)
    rep["frontier"] = front

    # 기준선: 대칭 + 게이트 (직전 실험의 최선) 과 비교해 **둘 다 나은** 설정이 있는가
    base = [x for x in front if x["kind"] == "대칭"]
    base_best = max(base, key=lambda x: x["게이트|MAR"])
    dom = [x for x in front
           if x["게이트|닷컴"] > base_best["게이트|닷컴"] and x["게이트|2020회복"] > base_best["게이트|2020회복"]]
    rep["dominance"] = {
        "baseline_rule": base_best["rule"],
        "baseline": {k: base_best[k] for k in ("게이트|닷컴", "게이트|2020회복", "게이트|CAGR", "게이트|MDD", "게이트|MAR")},
        "n_dominating": len(dom),
        "dominating": sorted(dom, key=lambda x: -x["게이트|MAR"])[:10],
    }

    # 거울짝 — 진입/이탈 파라미터를 맞바꾼 설정끼리 비교한다.
    # 두 설정은 「거르는 양」이 정확히 같고 **방향만 반대**이므로 노출 교란이 사라진다.
    fmap = {x["rule"]: x for x in front}
    rmap = {x["rule"]: x for x in rep["B"]["rows"] if x["gated"]}
    mirrors = []
    seen = set()
    for name, fn, prm in grid:
        if S.asym_kind(prm) == "대칭":
            continue
        mir = "a%d_e%.0f-%d_x%.0f-%d" % (prm["sma"], prm["exit_band"], prm["exit_confirm"],
                                         prm["enter_band"], prm["enter_confirm"])
        if mir not in fmap or (mir, name) in seen:
            continue
        seen.add((name, mir))
        fast_in = name if S.asym_kind(prm) == "진입빠름(이탈느림)" else mir
        fast_out = mir if fast_in == name else name
        mirrors.append({
            "fast_in": fast_in, "fast_out": fast_out,
            "cagr_fast_in": fmap[fast_in]["게이트|CAGR"], "cagr_fast_out": fmap[fast_out]["게이트|CAGR"],
            "mdd_fast_in": fmap[fast_in]["게이트|MDD"], "mdd_fast_out": fmap[fast_out]["게이트|MDD"],
            "mar_fast_in": fmap[fast_in]["게이트|MAR"], "mar_fast_out": fmap[fast_out]["게이트|MAR"],
            "dot_fast_in": fmap[fast_in]["게이트|닷컴"], "dot_fast_out": fmap[fast_out]["게이트|닷컴"],
            "pct_in_fast_in": rmap[fast_in]["pct_in"], "pct_in_fast_out": rmap[fast_out]["pct_in"],
        })
    rep["mirror"] = {
        "n": len(mirrors),
        "fast_in_better_cagr": sum(1 for m in mirrors if m["cagr_fast_in"] > m["cagr_fast_out"]),
        "fast_in_better_mdd": sum(1 for m in mirrors if abs(m["mdd_fast_in"]) < abs(m["mdd_fast_out"])),
        "fast_in_better_mar": sum(1 for m in mirrors if m["mar_fast_in"] > m["mar_fast_out"]),
        "fast_in_better_dotcom": sum(1 for m in mirrors if m["dot_fast_in"] > m["dot_fast_out"]),
        "median_d_cagr": st.median([m["cagr_fast_in"] - m["cagr_fast_out"] for m in mirrors]),
        "median_d_mdd": st.median([abs(m["mdd_fast_out"]) - abs(m["mdd_fast_in"]) for m in mirrors]),
        "median_d_dotcom": st.median([m["dot_fast_in"] - m["dot_fast_out"] for m in mirrors]),
        "median_d_pct_in": st.median([m["pct_in_fast_in"] - m["pct_in_fast_out"] for m in mirrors]),
        "rows": mirrors,
    }

    # 2020 회복에서 게이트가 결과를 지배하는가
    v_gated = [x["게이트|2020회복"] for x in front]
    v_base = [x["기본|2020회복"] for x in front]
    rep["v2020"] = {
        "gated_distinct": len(set(round(x, 2) for x in v_gated)),
        "gated_mode_share": max(sum(1 for y in v_gated if abs(y - x) < 0.01) for x in v_gated) / len(v_gated),
        "gated_range": [min(v_gated), max(v_gated)],
        "base_range": [min(v_base), max(v_base)],
        "base_median_by_kind": {k: st.median([x["기본|2020회복"] for x in front if x["kind"] == k])
                                for k in rep["kinds"]},
    }

    # 표본외 (구간 A)
    isd = [d for d in dA if d <= OOS_SPLIT]
    ood = [d for d in dA if d >= OOS_SPLIT]
    sp = {}
    for k in rep["kinds"]:
        for g in (False, True):
            tag = "%s|%s" % ("게이트" if g else "기본", k)
            vi, vo = [], []
            for name, fn, prm in grid:
                if S.asym_kind(prm) != k:
                    continue
                stt = S.gate_states(fn(wd, wc), gate) if g else fn(wd, wc)
                vi.append(BT.run(isd, stt, rets_a, MAP2, rc, switch_cost_bps=COST_BPS).cagr_pct)
                vo.append(BT.run(ood, stt, rets_a, MAP2, rc, switch_cost_bps=COST_BPS).cagr_pct)
            sp[tag] = {"is_median": st.median(vi), "oos_median": st.median(vo)}
    rep["split"] = {"is_period": [isd[0].isoformat(), isd[-1].isoformat()],
                    "oos_period": [ood[0].isoformat(), ood[-1].isoformat()], "by_kind": sp}

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "experiment_asym.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2, sort_keys=True, default=str)

    print("격자 %d개 — %s" % (rep["n_rules"], rep["kinds"]))
    for key in ("A", "B"):
        R = rep[key]
        print("\n[구간 %s] %s~%s (%d주)  TQQQ보유 CAGR %+.2f%% MDD %.2f%%" % (
            key, R["period"][0], R["period"][1], R["period"][2],
            R["bench"]["TQQQ"]["cagr_pct"], R["bench"]["TQQQ"]["mdd_pct"]))
        print("  %-28s %9s %9s %7s" % ("부류", "CAGR중앙", "MDD중앙", "MAR중앙"))
        for k, v in R["by_kind"].items():
            print("  %-28s %+9.2f %+9.2f %7.3f" % (k, v["cagr"]["median"], v["mdd"]["median"], v["mar"]["median"]))
    print("\n[두 극단 구간 — 구간 B, 게이트 적용]")
    print("  %-28s %10s %12s %9s %9s" % ("부류", "닷컴중앙", "2020회복중앙", "CAGR중앙", "MDD중앙"))
    for k in rep["kinds"]:
        sub = [x for x in front if x["kind"] == k]
        print("  %-28s %+10.2f %+12.2f %+9.2f %+9.2f" % (
            k, st.median([x["게이트|닷컴"] for x in sub]), st.median([x["게이트|2020회복"] for x in sub]),
            st.median([x["게이트|CAGR"] for x in sub]), st.median([x["게이트|MDD"] for x in sub])))
    dmn = rep["dominance"]
    print("\n[지배 검사] 기준선 = 대칭 최선 `%s`" % dmn["baseline_rule"])
    print("  기준선: 닷컴 %+.2f%% · 2020회복 %+.2f%% · CAGR %+.2f%% · MDD %.2f%% · MAR %.3f" % (
        dmn["baseline"]["게이트|닷컴"], dmn["baseline"]["게이트|2020회복"],
        dmn["baseline"]["게이트|CAGR"], dmn["baseline"]["게이트|MDD"], dmn["baseline"]["게이트|MAR"]))
    print("  두 구간 **모두**에서 기준선을 이긴 설정: %d / %d" % (dmn["n_dominating"], rep["n_rules"]))
    for x in dmn["dominating"][:5]:
        print("      %-22s [%s] 닷컴 %+8.2f%% · 2020회복 %+8.2f%% · CAGR %+7.2f%% · MDD %7.2f%% · MAR %.3f" % (
            x["rule"], x["kind"], x["게이트|닷컴"], x["게이트|2020회복"],
            x["게이트|CAGR"], x["게이트|MDD"], x["게이트|MAR"]))
    M = rep["mirror"]
    print("\n[거울짝 비교 — 진입/이탈 파라미터를 맞바꾼 %d쌍, 게이트 적용, 구간 B]" % M["n"])
    print("  거르는 양이 같고 방향만 반대이므로 노출 교란이 없다.")
    print("  진입빠름이 우세: CAGR %d/%d · 낙폭 %d/%d · MAR %d/%d · 닷컴 %d/%d" % (
        M["fast_in_better_cagr"], M["n"], M["fast_in_better_mdd"], M["n"],
        M["fast_in_better_mar"], M["n"], M["fast_in_better_dotcom"], M["n"]))
    print("  중앙 차이: CAGR %+.2f%%p · 낙폭 %+.2f%%p · 닷컴 %+.2f%%p · 노출 %+.1f%%p" % (
        M["median_d_cagr"], M["median_d_mdd"], M["median_d_dotcom"], M["median_d_pct_in"]))
    V = rep["v2020"]
    print("\n[2020 회복 — 게이트가 결과를 지배하는가]")
    print("  게이트 적용: 서로 다른 값 %d개, 최빈값 비중 %.0f%%, 범위 %+.2f ~ %+.2f" % (
        V["gated_distinct"], 100 * V["gated_mode_share"], V["gated_range"][0], V["gated_range"][1]))
    print("  게이트 없음: 범위 %+.2f ~ %+.2f · 부류별 중앙 %s" % (
        V["base_range"][0], V["base_range"][1],
        " / ".join("%s %+.1f%%" % (k, v) for k, v in V["base_median_by_kind"].items())))
    print("\n[표본내/표본외 — 구간 A, 부류별 CAGR 중앙값]")
    for k, v in rep["split"]["by_kind"].items():
        print("  %-28s 표본내 %+7.2f%% → 표본외 %+7.2f%%  (%+6.2f%%p)" % (
            k, v["is_median"], v["oos_median"], v["oos_median"] - v["is_median"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
