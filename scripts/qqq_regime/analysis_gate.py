# -*- coding: utf-8 -*-
"""변동성 게이트는 왜 살아남았는가 — 원인 분해와 귀무가설 검정.

네 번의 실험에서 셋이 기각되고 게이트만 남았다. 그것이 진짜 정보인지,
아니면 **노출을 줄인 결과**인지를 먼저 가른다. 비대칭 실험에서 「진입이 빠르다」가
「노출이 많다」와 같은 말이었던 것과 같은 함정이다.

## 귀무가설 (반드시 먼저 기각해야 한다)

    H0: 게이트에는 정보가 없다. 같은 비율로 아무 주나 막아도 결과가 같다.

검정: **순환이동 검정(circular shift).** 게이트 시계열을 k주만큼 돌린다.
노출 비율과 연속 구간 길이 분포가 **정확히 보존**되고, 오직 「어느 주를 막는가」의
시간 정렬만 깨진다. 실제 게이트(k=0)가 surrogate 분포의 어디에 있는지를 본다.

## 원인 후보

    H1 변동성 끌림   : 3배 상품은 고변동 구간에서 ~3σ² 만큼 구조적으로 잃는다
    H2 변동성 지속   : 변동성은 자기상관이 있어 과거가 미래를 예고한다
    H3 변동성-수익 음의 관계 : 고변동 구간의 기대수익 자체가 낮다
    H4 추세신호 오류 거르기 : 고변동 구간에서 추세 신호의 적중률이 낮다

H1은 예측이 아니라 **비용 회피**다. H2 없이는 H1도 쓸 수 없다 (과거 변동성으로
미래 구간을 막는 것이므로). 넷을 따로 재서 어느 것이 얼마나 기여하는지 본다.

    python3 scripts/qqq_regime/analysis_gate.py
"""

import datetime as dt
import json
import math
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
COST_BPS = 10.0
MAP2 = {S.UP: "TQQQ", S.DOWN: None, S.NEUTRAL: None}
TREND = "sma40_b0"
N_QUINTILE = 5


def quintile_edges(vals, n=N_QUINTILE):
    v = sorted(vals)
    return [v[int(len(v) * i / n)] for i in range(1, n)]


def bucket(x, edges):
    for i, e in enumerate(edges):
        if x < e:
            return i
    return len(edges)


def autocorr(xs, lag):
    a, b = xs[:-lag], xs[lag:]
    if len(a) < 3:
        return None
    return st.correlation(a, b)


def circular_shift(gate, dates, k):
    """게이트 값을 k주 돌린다. 노출과 연속구간 길이 분포가 정확히 보존된다."""
    ds = [d for d in dates if d in gate]
    vals = [gate[d] for d in ds]
    n = len(vals)
    return {ds[i]: vals[(i + k) % n] for i in range(n)}


def main():
    qw = prices.load_series(os.path.join(DATA, "qqq_weekly_adj.csv"))
    tw = prices.load_series(os.path.join(DATA, "tqqq_weekly_adj.csv"))
    qp = prices.load_series(os.path.join(DATA, "qqq_daily.csv"), "close")
    rc = prices.RateCurve(os.path.join(DATA, "ffr_weekly.csv"))
    wd = [d for d, _ in qw]
    wc = [v for _, v in qw]

    rq = prices.to_returns(qw)
    rt_real = prices.to_returns(tw)
    dA = [d for d in wd if d >= REAL_START and (d in rt_real or d == REAL_START)]
    fee = LV.fit_fee([d for d, _ in qp if REAL_START <= d <= dA[-1]],
                     [v for d, v in qp if REAL_START <= d <= dA[-1]], 3.0, rc,
                     BT.buy_and_hold(dA, {"TQQQ": rt_real}, "TQQQ").cagr_pct)
    simw = LV.to_weekly(LV.simulate_daily([d for d, _ in qp if d <= dA[-1]],
                                          [v for d, v in qp if d <= dA[-1]], 3.0, rc, fee), wd)
    rt_sim = prices.to_returns(simw)
    dB = [d for d in wd if d >= LONG_START and (d in rt_sim or d == LONG_START)]

    vol = S.realized_vol(wd, wc, 13)
    gate = S.vol_gate_pct(vol, wd, 80.0, 104)
    trend = dict(S.build_grid_wide())[TREND](wd, wc)

    rep = {"generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "gate": "vol13w_p80", "trend": TREND, "cost_bps": COST_BPS}

    # ---------------------------------------------------------- H1 변동성 끌림
    # 주간 로그수익 기준 끌림 = ln(1+r_3x) - 3*ln(1+r_qqq). 이론값은 -3*sigma^2 (연율).
    drag_rows = []
    for label, rt, dates in (("실제 TQQQ", rt_real, dA), ("시뮬 TQQQ", rt_sim, dB)):
        pts = [(vol[d], math.log(1 + rt[d]) - 3.0 * math.log(1 + rq[d]))
               for d in dates if d in vol and d in rt and d in rq]
        edges = quintile_edges([p[0] for p in pts])
        buckets = [[] for _ in range(N_QUINTILE)]
        for v, g in pts:
            buckets[bucket(v, edges)].append((v, g))
        rows = []
        for i, b in enumerate(buckets):
            sig = st.mean([x[0] for x in b]) / 100.0           # 연율 소수
            measured = st.mean([x[1] for x in b]) * 52 * 100.0  # 연율 %
            theory = -3.0 * sig * sig * 100.0
            rows.append({"quintile": i + 1, "n": len(b),
                         "mean_vol_pct": st.mean([x[0] for x in b]),
                         "measured_drag_pct": measured, "theory_drag_pct": theory,
                         "residual_pp": measured - theory})
        drag_rows.append({"label": label, "period": [dates[0].isoformat(), dates[-1].isoformat()],
                          "rows": rows})
    rep["H1_drag"] = drag_rows

    # ---------------------------------------------------------- H2 변동성 지속
    vs = [vol[d] for d in wd if d in vol]
    vdates = [d for d in wd if d in vol]
    edges = quintile_edges(vs)
    trans = [[0] * N_QUINTILE for _ in range(N_QUINTILE)]
    LAG = 13
    for i in range(len(vs) - LAG):
        trans[bucket(vs[i], edges)][bucket(vs[i + LAG], edges)] += 1
    rep["H2_persistence"] = {
        "autocorr": {str(l): autocorr(vs, l) for l in (1, 4, 13, 26, 52)},
        "lag_weeks": LAG,
        "transition_pct": [[100.0 * c / sum(row) if sum(row) else None for c in row] for row in trans],
        "stay_top_pct": 100.0 * trans[4][4] / sum(trans[4]) if sum(trans[4]) else None,
        "stay_bottom_pct": 100.0 * trans[0][0] / sum(trans[0]) if sum(trans[0]) else None,
    }

    # ------------------------------------------ H3 변동성 → 향후 수익 / H4 신호 적중
    fwd = []
    for i, d in enumerate(vdates[:-1]):
        nxt = vdates[i + 1]
        if nxt not in rq or nxt not in rt_sim:
            continue
        cashr = rc.period_return(d, 52) or 0.0
        fwd.append({"q": bucket(vol[d], edges), "rq": rq[nxt], "rt": rt_sim[nxt],
                    "cash": cashr, "trend_up": trend.get(d) == S.UP})
    h3 = []
    for q in range(N_QUINTILE):
        sub = [x for x in fwd if x["q"] == q]
        up = [x for x in sub if x["trend_up"]]
        h3.append({
            "quintile": q + 1, "n": len(sub),
            "fwd_qqq_pct": st.mean([x["rq"] for x in sub]) * 52 * 100,
            "fwd_tqqq_pct": st.mean([x["rt"] for x in sub]) * 52 * 100,
            "trend_up_share_pct": 100.0 * len(up) / len(sub) if sub else None,
            "trend_up_hit_pct": (100.0 * sum(1 for x in up if x["rt"] > x["cash"]) / len(up)) if up else None,
            "trend_up_fwd_tqqq_pct": (st.mean([x["rt"] for x in up]) * 52 * 100) if up else None,
        })
    rep["H3_H4_by_quintile"] = h3

    # ---------------------------------------------------------- H0 순환이동 검정
    rep["H0_shift"] = {}
    for label, rt, dates in (("A 실제", rt_real, dA), ("B 시뮬", rt_sim, dB)):
        rets = {"TQQQ": rt}
        gated = S.gate_states(trend, gate)
        real = BT.run(dates, gated, rets, MAP2, rc, switch_cost_bps=COST_BPS)
        base = BT.run(dates, trend, rets, MAP2, rc, switch_cost_bps=COST_BPS)
        gds = [d for d in wd if d in gate]
        surro = []
        step = 1   # 모든 순환이동을 다 본다 — 노출 맞춘 부분집합을 충분히 만들기 위해서다
        for k in range(step, len(gds), step):
            g2 = circular_shift(gate, wd, k)
            r = BT.run(dates, S.gate_states(trend, g2), rets, MAP2, rc, switch_cost_bps=COST_BPS)
            wi = sum(r.weeks_in.values())
            surro.append({"cagr": r.cagr_pct, "mdd": r.mdd_pct,
                          "pct_in": 100.0 * r.weeks_in[S.UP] / wi if wi else None})
        cg = [x["cagr"] for x in surro]
        md = [abs(x["mdd"]) for x in surro]
        pin = [x["pct_in"] for x in surro]
        rwi = sum(real.weeks_in.values())
        real_pin = 100.0 * real.weeks_in[S.UP] / rwi if rwi else None

        # 순환이동은 게이트 자체의 노출은 보존하지만, 추세 UP 과의 **겹침**은 보존하지 않는다.
        # 그래서 결합 노출이 실제와 다른 surrogate 가 섞인다. 노출을 맞춘 부분집합으로 다시 잰다.
        band, tol = [], None
        for t in (1.0, 2.0, 3.0, 5.0):
            band = [x for x in surro if abs(x["pct_in"] - real_pin) <= t]
            tol = t
            if len(band) >= 50:
                break
        mcg = [x["cagr"] for x in band]
        mmd = [abs(x["mdd"]) for x in band]
        matched = None
        if len(band) >= 30:
            matched = {
                "n": len(band), "tolerance_pp": tol,
                "pct_in_median": st.median([x["pct_in"] for x in band]),
                "cagr_median": st.median(mcg), "mdd_median": -st.median(mmd),
                "pval_cagr": (sum(1 for x in mcg if x >= real.cagr_pct) + 1) / (len(mcg) + 1),
                "pval_mdd": (sum(1 for x in mmd if x <= abs(real.mdd_pct)) + 1) / (len(mmd) + 1),
            }
        rep["H0_shift"][label] = {
            "matched": matched,
            "n_surrogate": len(surro),
            "real_cagr": real.cagr_pct, "real_mdd": real.mdd_pct,
            "real_pct_in": 100.0 * real.weeks_in[S.UP] / rwi if rwi else None,
            "base_cagr": base.cagr_pct, "base_mdd": base.mdd_pct,
            "surr_cagr_median": st.median(cg), "surr_cagr_min": min(cg), "surr_cagr_max": max(cg),
            "surr_mdd_median": -st.median(md), "surr_mdd_best": -min(md), "surr_mdd_worst": -max(md),
            "surr_pct_in_median": st.median(pin),
            "pval_cagr": (sum(1 for x in cg if x >= real.cagr_pct) + 1) / (len(cg) + 1),
            "pval_mdd": (sum(1 for x in md if x <= abs(real.mdd_pct)) + 1) / (len(md) + 1),
        }

    # ----------------------------- 중복성: 추세가 이미 고변동 구간을 거르는가
    #  끌림(H1)도 지속성(H2)도 실재하는데 게이트가 추세 위에서 정보를 못 보이면,
    #  가장 그럴듯한 설명은 **추세가 이미 그 일을 하고 있다**는 것이다.
    ds_both = [d for d in wd if d in gate and d in trend]
    t_up = [d for d in ds_both if trend[d] == S.UP]
    blocked = [d for d in ds_both if gate[d] is False]
    both = [d for d in t_up if gate[d] is False]
    rep["redundancy"] = {
        "weeks": len(ds_both),
        "trend_up_pct": 100.0 * len(t_up) / len(ds_both),
        "gate_blocked_pct": 100.0 * len(blocked) / len(ds_both),
        "blocked_and_trend_down_pct": 100.0 * (len(blocked) - len(both)) / len(blocked) if blocked else None,
        "gate_adds_pct": 100.0 * len(both) / len(ds_both),
        "phi": st.correlation([1.0 if trend[d] == S.UP else 0.0 for d in ds_both],
                              [1.0 if gate[d] is True else 0.0 for d in ds_both]),
    }

    # 게이트 **단독** (추세 없이) 의 순환이동 검정 — 중복이 없으면 여기선 정보가 보여야 한다
    rep["H0_shift_solo"] = {}
    for label, rt, dates in (("A 실제", rt_real, dA), ("B 시뮬", rt_sim, dB)):
        rets = {"TQQQ": rt}
        solo = {d: (S.UP if gate.get(d) is True else S.NEUTRAL) for d in wd}
        real = BT.run(dates, solo, rets, MAP2, rc, switch_cost_bps=COST_BPS)
        rwi = sum(real.weeks_in.values())
        real_pin = 100.0 * real.weeks_in[S.UP] / rwi if rwi else None
        gds = [d for d in wd if d in gate]
        sur = []
        for k in range(1, len(gds)):
            g2 = circular_shift(gate, wd, k)
            r = BT.run(dates, {d: (S.UP if g2.get(d) is True else S.NEUTRAL) for d in wd},
                       rets, MAP2, rc, switch_cost_bps=COST_BPS)
            wi = sum(r.weeks_in.values())
            sur.append({"cagr": r.cagr_pct, "mdd": r.mdd_pct,
                        "pct_in": 100.0 * r.weeks_in[S.UP] / wi if wi else None})
        cg = [x["cagr"] for x in sur]
        md = [abs(x["mdd"]) for x in sur]
        rep["H0_shift_solo"][label] = {
            "n_surrogate": len(sur), "real_cagr": real.cagr_pct, "real_mdd": real.mdd_pct,
            "real_pct_in": real_pin,
            "surr_pct_in_median": st.median([x["pct_in"] for x in sur]),
            "surr_cagr_median": st.median(cg), "surr_mdd_median": -st.median(md),
            "pval_cagr": (sum(1 for x in cg if x >= real.cagr_pct) + 1) / (len(cg) + 1),
            "pval_mdd": (sum(1 for x in md if x <= abs(real.mdd_pct)) + 1) / (len(md) + 1),
            "bench_tqqq_cagr": BT.buy_and_hold(dates, rets, "TQQQ").cagr_pct,
            "bench_tqqq_mdd": BT.buy_and_hold(dates, rets, "TQQQ").mdd_pct,
        }

    # ------------------------------------- 노출만 맞춘 대조군 (상수 비중 / 무작위 블록)
    rep["exposure_control"] = {}
    for label, rt, dates in (("A 실제", rt_real, dA), ("B 시뮬", rt_sim, dB)):
        rets = {"TQQQ": rt}
        gated = S.gate_states(trend, gate)
        rg = BT.run(dates, gated, rets, MAP2, rc, switch_cost_bps=COST_BPS)
        wi = sum(rg.weeks_in.values())
        share = rg.weeks_in[S.UP] / wi if wi else 0.0
        tstates = trend
        tw_ = BT.run(dates, tstates, rets, MAP2, rc, switch_cost_bps=COST_BPS)
        twi = sum(tw_.weeks_in.values())
        tshare = tw_.weeks_in[S.UP] / twi if twi else 0.0
        scale = share / tshare if tshare else 0.0
        const = BT.run_weights(dates, {d: (scale if tstates.get(d) == S.UP else 0.0) for d in wd},
                               rets, "TQQQ", rc, switch_cost_bps=COST_BPS)
        rep["exposure_control"][label] = {
            "gate_pct_in": 100 * share, "trend_pct_in": 100 * tshare, "scale": scale,
            "gate_cagr": rg.cagr_pct, "gate_mdd": rg.mdd_pct,
            "const_cagr": const.cagr_pct, "const_mdd": const.mdd_pct,
            "const_mean_weight": const.mean_weight,
        }

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "analysis_gate.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2, sort_keys=True, default=str)

    print("=== H0 순환이동 검정 — 게이트에 정보가 있는가 ===")
    for k, v in rep["H0_shift"].items():
        print("[%s] surrogate %d개 (노출 중앙 %.1f%% vs 실제 %.1f%%)" % (
            k, v["n_surrogate"], v["surr_pct_in_median"], v["real_pct_in"]))
        print("   CAGR  실제 %+7.2f%% | surrogate 중앙 %+7.2f%% (범위 %+7.2f ~ %+7.2f)  p=%.4f" % (
            v["real_cagr"], v["surr_cagr_median"], v["surr_cagr_min"], v["surr_cagr_max"], v["pval_cagr"]))
        print("   MDD   실제 %+7.2f%% | surrogate 중앙 %+7.2f%% (최선 %+7.2f ~ 최악 %+7.2f)  p=%.4f" % (
            v["real_mdd"], v["surr_mdd_median"], v["surr_mdd_best"], v["surr_mdd_worst"], v["pval_mdd"]))
        print("   (게이트 없는 추세만: CAGR %+.2f%% · MDD %+.2f%%)" % (v["base_cagr"], v["base_mdd"]))
        m = v.get("matched")
        if m:
            print("   노출 맞춘 %d개(±%.0f%%p, 중앙 %.1f%%): CAGR 중앙 %+7.2f%% p=%.4f | MDD 중앙 %+7.2f%% p=%.4f" % (
                m["n"], m["tolerance_pp"], m["pct_in_median"], m["cagr_median"], m["pval_cagr"],
                m["mdd_median"], m["pval_mdd"]))
        else:
            print("   노출 맞춘 부분집합이 30개 미만 — 보고하지 않는다")
    rd = rep["redundancy"]
    print("\n=== 중복성 — 추세가 이미 고변동 구간을 거르는가 ===")
    print("   %d주 중 추세 UP %.1f%% · 게이트 차단 %.1f%%" % (
        rd["weeks"], rd["trend_up_pct"], rd["gate_blocked_pct"]))
    print("   게이트가 막은 주의 %.1f%%는 추세가 이미 DOWN 이었다" % rd["blocked_and_trend_down_pct"])
    print("   게이트가 **추가로** 막은 주: 전체의 %.1f%%  (상관 phi = %.3f)" % (rd["gate_adds_pct"], rd["phi"]))
    print("\n=== 게이트 단독(추세 없이) 순환이동 검정 ===")
    for k, v in rep["H0_shift_solo"].items():
        print("   [%s] surrogate %d개 (노출 중앙 %.1f%% vs 실제 %.1f%%)" % (
            k, v["n_surrogate"], v["surr_pct_in_median"], v["real_pct_in"]))
        print("       CAGR 실제 %+7.2f%% | surrogate 중앙 %+7.2f%%  p=%.4f" % (
            v["real_cagr"], v["surr_cagr_median"], v["pval_cagr"]))
        print("       MDD  실제 %+7.2f%% | surrogate 중앙 %+7.2f%%  p=%.4f" % (
            v["real_mdd"], v["surr_mdd_median"], v["pval_mdd"]))
        print("       (TQQQ 보유: CAGR %+.2f%% · MDD %+.2f%%)" % (v["bench_tqqq_cagr"], v["bench_tqqq_mdd"]))
    print("\n=== 노출만 맞춘 대조군 (추세 UP 구간에 상수 비중) ===")
    for k, v in rep["exposure_control"].items():
        print("  [%s] 게이트 노출 %.1f%% ← 추세 %.1f%% x %.3f" % (
            k, v["gate_pct_in"], v["trend_pct_in"], v["scale"]))
        print("        게이트  CAGR %+7.2f%%  MDD %+7.2f%%" % (v["gate_cagr"], v["gate_mdd"]))
        print("        상수비중 CAGR %+7.2f%%  MDD %+7.2f%% (평균비중 %.2f)" % (
            v["const_cagr"], v["const_mdd"], v["const_mean_weight"]))
    print("\n=== H1 변동성 끌림 — 측정 vs 이론(-3σ²) ===")
    for blk in rep["H1_drag"]:
        print("[%s] %s ~ %s" % (blk["label"], blk["period"][0], blk["period"][1]))
        print("   %8s %6s %10s %12s %12s %10s" % ("5분위", "n", "평균변동성", "측정끌림/년", "이론끌림/년", "잔차"))
        for x in blk["rows"]:
            print("   %8d %6d %9.1f%% %11.2f%% %11.2f%% %9.2f%%p" % (
                x["quintile"], x["n"], x["mean_vol_pct"], x["measured_drag_pct"],
                x["theory_drag_pct"], x["residual_pp"]))
    h2 = rep["H2_persistence"]
    print("\n=== H2 변동성 지속 ===")
    print("   자기상관: " + " · ".join("%s주 %.3f" % (k, v) for k, v in h2["autocorr"].items()))
    print("   %d주 뒤 최상위 5분위에 그대로 있을 확률 %.1f%% (무정보면 20%%)" % (h2["lag_weeks"], h2["stay_top_pct"]))
    print("   %d주 뒤 최하위 5분위에 그대로 있을 확률 %.1f%%" % (h2["lag_weeks"], h2["stay_bottom_pct"]))
    print("\n=== H3·H4 변동성 5분위별 향후 1주 (연율 환산) ===")
    print("   %8s %6s %11s %12s %12s %11s" % ("5분위", "n", "QQQ", "TQQQ(시뮬)", "추세UP비율", "UP적중률"))
    for x in rep["H3_H4_by_quintile"]:
        print("   %8d %6d %10.2f%% %11.2f%% %11.1f%% %10.1f%%" % (
            x["quintile"], x["n"], x["fwd_qqq_pct"], x["fwd_tqqq_pct"],
            x["trend_up_share_pct"], x["trend_up_hit_pct"] or 0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
