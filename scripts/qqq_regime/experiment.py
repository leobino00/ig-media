# -*- coding: utf-8 -*-
"""레짐 전환 실험 — TQQQ / SQQQ / 현금 3상태.

    python3 scripts/qqq_regime/experiment.py            # 전체 실행 + 보고서 작성
    python3 scripts/qqq_regime/experiment.py --quick    # 요약만 표준출력

규칙 하나의 수익률은 의미가 없다. 규칙 전수의 **분포**를 낸다.
"""

import argparse
import datetime as dt
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import backtest as BT
import prices
import signals as S

DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "출력")

REAL_START = dt.date(2010, 2, 19)   # TQQQ·SQQQ 실제 가격 시작
OOS_SPLIT = dt.date(2019, 1, 1)     # 표본내/표본외 경계
DEFAULT_COST_BPS = 10.0


def load_all():
    q = prices.load_series(os.path.join(DATA, "qqq_weekly_adj.csv"))
    t = prices.load_series(os.path.join(DATA, "tqqq_weekly_adj.csv"))
    s = prices.load_series(os.path.join(DATA, "sqqq_weekly_adj.csv"))
    rc = prices.RateCurve(os.path.join(DATA, "ffr_weekly.csv"))
    rets = {"QQQ": prices.to_returns(q), "TQQQ": prices.to_returns(t), "SQQQ": prices.to_returns(s)}
    qd = [d for d, _ in q]
    qc = [v for _, v in q]
    return q, qd, qc, rets, rc


def window(dates, lo=None, hi=None):
    return [d for d in dates if (lo is None or d >= lo) and (hi is None or d <= hi)]


MAPPINGS = {
    "3상태(TQQQ/SQQQ/현금)": {S.UP: "TQQQ", S.DOWN: "SQQQ", S.NEUTRAL: None},
    "숏없음(TQQQ/현금)": {S.UP: "TQQQ", S.DOWN: None, S.NEUTRAL: None},
    "1배(QQQ/현금)": {S.UP: "QQQ", S.DOWN: None, S.NEUTRAL: None},
}


def run_grid(qd, qc, rets, rc, bt_dates, mapping, cost_bps=DEFAULT_COST_BPS):
    rows = []
    for name, fn in S.build_grid():
        sig = fn(qd, qc)
        r = BT.run(bt_dates, sig, rets, mapping, rc, switch_cost_bps=cost_bps)
        rows.append({
            "rule": name,
            "cagr_pct": r.cagr_pct,
            "mdd_pct": r.mdd_pct,
            "vol_pct": r.vol_pct,
            "switches_per_year": r.switches_per_year,
            "weeks_in": dict(r.weeks_in),
            "annual": r.annual,
            "total_pct": r.total_pct,
        })
    return rows


def dist(rows, key="cagr_pct"):
    v = sorted(x[key] for x in rows)
    return {
        "n": len(v), "min": v[0], "p25": st.quantiles(v, n=4)[0] if len(v) > 3 else v[0],
        "median": st.median(v), "p75": st.quantiles(v, n=4)[2] if len(v) > 3 else v[-1],
        "max": v[-1], "mean": st.mean(v),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)

    q, qd, qc, rets, rc = load_all()
    # 세 종목 수익률이 모두 존재하는 주 + 시작 기준주. 교집합으로만 구성한다.
    common = set(rets["TQQQ"]) & set(rets["SQQQ"]) & set(rets["QQQ"])
    bt_full = [d for d in qd if d >= REAL_START and (d in common or d == REAL_START)]
    if len(bt_full) < 100:
        raise SystemExit("정렬된 공통 주가 너무 적다: %d" % len(bt_full))
    is_dates = window(bt_full, None, OOS_SPLIT)
    oos_dates = window(bt_full, OOS_SPLIT, None)

    report = {"generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}
    report["period"] = {"full": [bt_full[0].isoformat(), bt_full[-1].isoformat(), len(bt_full)],
                        "is": [is_dates[0].isoformat(), is_dates[-1].isoformat(), len(is_dates)],
                        "oos": [oos_dates[0].isoformat(), oos_dates[-1].isoformat(), len(oos_dates)]}

    # 벤치마크
    bench = {}
    for sym in ("QQQ", "TQQQ", "SQQQ"):
        b = BT.buy_and_hold(bt_full, rets, sym)
        bench[sym] = {"cagr_pct": b.cagr_pct, "mdd_pct": b.mdd_pct, "vol_pct": b.vol_pct,
                      "total_pct": b.total_pct, "annual": b.annual}
    report["benchmark"] = bench

    # 매핑별 전수 그리드
    report["grids"] = {}
    for label, mapping in MAPPINGS.items():
        rows = run_grid(qd, qc, rets, rc, bt_full, mapping)
        report["grids"][label] = {"rows": rows, "cagr_dist": dist(rows), "mdd_dist": dist(rows, "mdd_pct")}

    # 표본내/표본외 (3상태만)
    m3 = MAPPINGS["3상태(TQQQ/SQQQ/현금)"]
    is_rows = run_grid(qd, qc, rets, rc, is_dates, m3)
    oos_rows = run_grid(qd, qc, rets, rc, oos_dates, m3)
    is_by = {r["rule"]: r for r in is_rows}
    best_is = max(is_rows, key=lambda r: r["cagr_pct"])
    oos_by = {r["rule"]: r for r in oos_rows}
    report["split"] = {
        "is": {"rows": is_rows, "dist": dist(is_rows)},
        "oos": {"rows": oos_rows, "dist": dist(oos_rows)},
        "best_is_rule": best_is["rule"],
        "best_is_cagr": best_is["cagr_pct"],
        "that_rule_oos_cagr": oos_by[best_is["rule"]]["cagr_pct"],
        "oos_rank_of_best_is": sorted(oos_rows, key=lambda r: -r["cagr_pct"]).index(oos_by[best_is["rule"]]) + 1,
    }

    # 비용 민감도 (3상태)
    report["cost_sensitivity"] = {}
    for c in (0.0, 5.0, 10.0, 20.0, 50.0):
        rows = run_grid(qd, qc, rets, rc, bt_full, m3, cost_bps=c)
        report["cost_sensitivity"]["%.0fbp" % c] = dist(rows)

    # 대조군 — 신호 없이 한 자산에 고정
    ctrl = {}
    for label, state in (("항상 UP", S.UP), ("항상 DOWN", S.DOWN), ("항상 현금", S.NEUTRAL)):
        r = BT.run(bt_full, {d: state for d in qd}, rets, m3, rc, switch_cost_bps=DEFAULT_COST_BPS)
        ctrl[label] = {"cagr_pct": r.cagr_pct, "mdd_pct": r.mdd_pct, "switches": r.switches}
    report["control"] = ctrl

    # 미래참조 검증 — 신호를 한 주 당겨(= 부정행위) 돌리면 결과가 크게 좋아져야 한다.
    #   좋아지지 않으면 엔진이 이미 미래를 보고 있다는 뜻이다.
    cheat_rows = []
    honest_rows = []
    for name, fn in S.build_grid():
        sig = fn(qd, qc)
        cheat = {qd[i - 1]: sig[qd[i]] for i in range(1, len(qd)) if qd[i] in sig}
        honest_rows.append(BT.run(bt_full, sig, rets, m3, rc).cagr_pct)
        cheat_rows.append(BT.run(bt_full, cheat, rets, m3, rc).cagr_pct)
    report["lookahead_check"] = {
        "honest_median_cagr": st.median(honest_rows),
        "cheat_median_cagr": st.median(cheat_rows),
        "gap_pp": st.median(cheat_rows) - st.median(honest_rows),
    }

    # 장기 신호 시험 — 1999년부터 실제 QQQ 만으로. 닷컴·금융위기 포함, 시뮬레이션 없음.
    long_dates = [d for d in qd if d >= dt.date(2000, 1, 1)]
    long_rows = run_grid(qd, qc, rets, rc, long_dates, MAPPINGS["1배(QQQ/현금)"])
    long_bh = BT.buy_and_hold(long_dates, rets, "QQQ")
    report["long_1x"] = {
        "period": [long_dates[0].isoformat(), long_dates[-1].isoformat(), len(long_dates)],
        "rows": long_rows, "dist": dist(long_rows), "mdd_dist": dist(long_rows, "mdd_pct"),
        "buy_hold": {"cagr_pct": long_bh.cagr_pct, "mdd_pct": long_bh.mdd_pct, "annual": long_bh.annual},
    }

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "experiment.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, sort_keys=True, default=str)

    # 요약 출력
    p = report["period"]["full"]
    print("기간 %s ~ %s (%d주)" % (p[0], p[1], p[2]))
    print("\n[벤치마크 바이앤홀드]")
    for k, v in bench.items():
        print("  %-5s CAGR %+8.2f%%  MDD %8.2f%%  변동성 %6.2f%%" % (k, v["cagr_pct"], v["mdd_pct"], v["vol_pct"]))
    print("\n[규칙 %d개 전수 — CAGR 분포]" % report["grids"]["3상태(TQQQ/SQQQ/현금)"]["cagr_dist"]["n"])
    for label in MAPPINGS:
        d = report["grids"][label]["cagr_dist"]
        m = report["grids"][label]["mdd_dist"]
        print("  %-22s 최저 %+7.2f | 25%% %+7.2f | 중앙 %+7.2f | 75%% %+7.2f | 최고 %+7.2f   (MDD 중앙 %7.2f%%)"
              % (label, d["min"], d["p25"], d["median"], d["p75"], d["max"], m["median"]))
    sp = report["split"]
    print("\n[표본내 최고 규칙의 표본외 성적]")
    print("  표본내 최고: %s  CAGR %+.2f%%" % (sp["best_is_rule"], sp["best_is_cagr"]))
    print("  같은 규칙 표본외 CAGR %+.2f%%  (표본외 순위 %d/%d)"
          % (sp["that_rule_oos_cagr"], sp["oos_rank_of_best_is"], len(sp["oos"]["rows"])))
    print("  표본내 중앙 %+.2f%%  →  표본외 중앙 %+.2f%%" % (sp["is"]["dist"]["median"], sp["oos"]["dist"]["median"]))
    print("\n[거래비용 민감도 — 3상태 CAGR 중앙값]")
    for k, v in report["cost_sensitivity"].items():
        print("  %-6s 중앙 %+7.2f%%  최고 %+7.2f%%" % (k, v["median"], v["max"]))
    print("\n[대조군]")
    for k, v in ctrl.items():
        print("  %-9s CAGR %+8.2f%%  MDD %8.2f%%  전환 %d회" % (k, v["cagr_pct"], v["mdd_pct"], v["switches"]))
    lc = report["lookahead_check"]
    print("\n[미래참조 검증] 정직 중앙 %+.2f%%  vs  한 주 당겨봄(부정) 중앙 %+.2f%%  차 %+.2f%%p"
          % (lc["honest_median_cagr"], lc["cheat_median_cagr"], lc["gap_pp"]))
    lg = report["long_1x"]
    print("\n[장기 신호 시험 1배 — %s ~ %s, %d주]" % tuple(lg["period"]))
    print("  QQQ 바이앤홀드      CAGR %+7.2f%%  MDD %7.2f%%" % (lg["buy_hold"]["cagr_pct"], lg["buy_hold"]["mdd_pct"]))
    print("  규칙 전수 CAGR      최저 %+7.2f | 중앙 %+7.2f | 최고 %+7.2f"
          % (lg["dist"]["min"], lg["dist"]["median"], lg["dist"]["max"]))
    print("  규칙 전수 MDD       최악 %7.2f | 중앙 %7.2f | 최선 %7.2f"
          % (lg["mdd_dist"]["min"], lg["mdd_dist"]["median"], lg["mdd_dist"]["max"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
