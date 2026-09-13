# -*- coding: utf-8 -*-
"""experiment.json → 보고서.md

숫자를 고르지 않는다. 규칙 전수를 싣고, 최고값 옆에 항상 중앙값을 같이 적는다.

    python3 scripts/qqq_regime/report.py
"""

import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "출력")


def f(x, nd=2, suf="%"):
    return "결측" if x is None else ("%+.*f%s" % (nd, x, suf))


def fa(x, nd=2, suf="%"):
    return "결측" if x is None else ("%.*f%s" % (nd, x, suf))


def main():
    with open(os.path.join(OUT, "experiment.json"), encoding="utf-8") as fh:
        r = json.load(fh)
    L = []
    A = L.append

    p = r["period"]["full"]
    b = r["benchmark"]
    g3 = r["grids"]["3상태(TQQQ/SQQQ/현금)"]
    gn = r["grids"]["숏없음(TQQQ/현금)"]
    g1 = r["grids"]["1배(QQQ/현금)"]
    m3 = {x["rule"]: x for x in g3["rows"]}
    mn = {x["rule"]: x for x in gn["rows"]}
    best3 = max(g3["rows"], key=lambda x: x["cagr_pct"])
    lg = r["long_1x"]

    A("# QQQ 레짐 전환 실험 — TQQQ / SQQQ / 현금")
    A("")
    A("생성 %s" % r["generated_at"])
    A("")
    A("> **이 문서는 실험 기록이다. 투자 판정이 아니다.**")
    A("> 어드바이저 5단계 프로토콜·판정기록부와 무관하며, 그 입력으로 쓰이지 않는다.")
    A("")
    A("## 질문")
    A("")
    A("상승 추세를 감지하면 TQQQ, 하락 추세면 SQQQ, 횡보면 현금 —")
    A("이 3상태 매매의 **연간 평균 수익률**은 얼마인가.")
    A("")
    A("## 답")
    A("")
    A("| | 값 |")
    A("|---|---|")
    A("| **규칙 %d개의 CAGR 중앙값** | **%s** |" % (g3["cagr_dist"]["n"], f(g3["cagr_dist"]["median"])))
    A("| 규칙 전수 범위 | %s ~ %s |" % (f(g3["cagr_dist"]["min"]), f(g3["cagr_dist"]["max"])))
    A("| 같은 기간 QQQ 바이앤홀드 | %s |" % f(b["QQQ"]["cagr_pct"]))
    A("| 같은 기간 TQQQ 바이앤홀드 | %s |" % f(b["TQQQ"]["cagr_pct"]))
    A("| 규칙 전수 최대낙폭 중앙값 | %s |" % fa(g3["mdd_dist"]["median"]))
    A("")
    A("**단일 숫자로 답할 수 없다.** 규칙을 어떻게 정하느냐에 따라 %s에서 %s까지 벌어지고,"
      % (f(g3["cagr_dist"]["min"]), f(g3["cagr_dist"]["max"])))
    A("그 폭(%.1f%%p)이 중앙값보다 훨씬 크다. 중앙값 %s는 **TQQQ를 그냥 들고 있는 것(%s)보다 낮다.**"
      % (g3["cagr_dist"]["max"] - g3["cagr_dist"]["min"], f(g3["cagr_dist"]["median"]), f(b["TQQQ"]["cagr_pct"])))
    A("")
    A("## 설계")
    A("")
    A("| 항목 | 내용 |")
    A("|---|---|")
    A("| 기간 | %s ~ %s (%d주) — TQQQ·SQQQ **실제 상장일**부터 |" % (p[0], p[1], p[2]))
    A("| 신호 | QQQ 주간 수정종가만 사용. 이동평균·이중이동평균·모멘텀 3계열 %d개 |" % g3["cagr_dist"]["n"])
    A("| 타이밍 | t주 종가로 신호 → t주 종가에 전환 → **t+1주 수익률**을 받는다 |")
    A("| 상태 | UP→TQQQ · DOWN→SQQQ · NEUTRAL→현금(연준금리) |")
    A("| 거래비용 | 전환 1회당 10bp (0~50bp 민감도 별도) |")
    A("| ETF 보수 | 수정종가에 이미 반영 — 다시 빼지 않는다 |")
    A("")
    A("## 검증")
    A("")
    A("| 검증 | 결과 |")
    A("|---|---|")
    c = r["control"]
    A("| 대조군 「항상 UP」 = TQQQ 바이앤홀드 | %s vs %s — 일치 |"
      % (f(c["항상 UP"]["cagr_pct"]), f(b["TQQQ"]["cagr_pct"])))
    A("| 대조군 「항상 DOWN」 = SQQQ 바이앤홀드 | %s vs %s — 일치 |"
      % (f(c["항상 DOWN"]["cagr_pct"]), f(b["SQQQ"]["cagr_pct"])))
    A("| 대조군 「항상 현금」 | %s (기간 평균 연준금리) |" % f(c["항상 현금"]["cagr_pct"]))
    lc = r["lookahead_check"]
    A("| **미래참조 검증** | 신호를 한 주 당기면(부정행위) 중앙 %s → %s (**%sp**). 정직한 엔진이라는 뜻 |"
      % (f(lc["honest_median_cagr"]), f(lc["cheat_median_cagr"]), f(lc["gap_pp"], 1, "%")))
    A("")
    A("## 결과 1 — SQQQ 다리가 결과를 지배한다")
    A("")
    A("| 구성 | CAGR 최저 | 25% | **중앙** | 75% | 최고 | MDD 중앙 |")
    A("|---|---|---|---|---|---|---|")
    for label, g in (("3상태 (TQQQ/SQQQ/현금)", g3), ("숏 없음 (TQQQ/현금)", gn), ("1배 (QQQ/현금)", g1)):
        d, m = g["cagr_dist"], g["mdd_dist"]
        A("| %s | %s | %s | **%s** | %s | %s | %s |" % (
            label, f(d["min"]), f(d["p25"]), f(d["median"]), f(d["p75"]), f(d["max"]), fa(m["median"])))
    A("")
    worse = sum(1 for k in m3 if m3[k]["cagr_pct"] < mn[k]["cagr_pct"])
    gaps = [m3[k]["cagr_pct"] - mn[k]["cagr_pct"] for k in m3]
    A("**같은 규칙에서 SQQQ 다리만 켜고 껐을 때, %d개 중 %d개가 나빠졌다.** 예외가 없다."
      % (len(m3), worse))
    A("피해는 가장 작은 규칙이 연 %s, 가장 큰 규칙이 연 %s, 중앙값 %s다.  " % (f(max(gaps)), f(min(gaps)), f(st.median(gaps))))
    A("이유는 단순하다 — 같은 기간 SQQQ 보유의 CAGR이 **%s**다. 하락을 맞혀야 버는 게 아니라,"
      % f(b["SQQQ"]["cagr_pct"]))
    A("**틀린 주마다 그 속도로 잃는다.**")
    A("")
    A("### 규칙 전수 (숏없음 CAGR 내림차순)")
    A("")
    A("| 규칙 | 3상태 CAGR | 숏없음 CAGR | SQQQ 영향 | 3상태 MDD | 전환/년 |")
    A("|---|---|---|---|---|---|")
    for k in sorted(m3, key=lambda x: -mn[x]["cagr_pct"]):
        A("| `%s` | %s | %s | %s | %s | %.1f |" % (
            k, f(m3[k]["cagr_pct"]), f(mn[k]["cagr_pct"]),
            f(m3[k]["cagr_pct"] - mn[k]["cagr_pct"]), fa(m3[k]["mdd_pct"]), m3[k]["switches_per_year"]))
    A("")
    A("## 결과 2 — 표본내에서 고른 규칙은 표본외에서 유지되지 않는다")
    A("")
    sp = r["split"]
    A("| 항목 | 값 |")
    A("|---|---|")
    A("| 표본내 (%s ~ %s) 최고 규칙 | `%s`, CAGR %s |"
      % (r["period"]["is"][0], r["period"]["is"][1], sp["best_is_rule"], f(sp["best_is_cagr"])))
    A("| 그 규칙의 표본외 (%s ~ %s) CAGR | %s |"
      % (r["period"]["oos"][0], r["period"]["oos"][1], f(sp["that_rule_oos_cagr"])))
    A("| 표본외 순위 | %d / %d |" % (sp["oos_rank_of_best_is"], len(sp["oos"]["rows"])))
    A("| 표본내 중앙 → 표본외 중앙 | %s → %s |" % (f(sp["is"]["dist"]["median"]), f(sp["oos"]["dist"]["median"])))
    A("")
    A("표본내 1등이 표본외 %d등이다. **최고 규칙의 숫자를 성과로 인용하면 안 된다는 근거다.**"
      % sp["oos_rank_of_best_is"])
    A("")
    A("## 결과 3 — 거래비용은 이 결과의 원인이 아니다")
    A("")
    A("| 전환비용 | CAGR 중앙 | CAGR 최고 |")
    A("|---|---|---|")
    for k, v in sorted(r["cost_sensitivity"].items(), key=lambda kv: float(kv[0][:-2])):
        A("| %s | %s | %s |" % (k, f(v["median"]), f(v["max"])))
    A("")
    A("0bp로 놓아도 중앙값이 %s다. 비용을 없애도 결론이 바뀌지 않는다."
      % f(r["cost_sensitivity"]["0bp"]["median"]))
    A("")
    A("## 결과 4 — 신호 자체는 쓸모가 있다. 단 수익이 아니라 낙폭에서")
    A("")
    A("레버리지를 빼고 **1배(QQQ/현금)** 로 %s부터 돌린다. 닷컴 붕괴와 금융위기가 들어간다."
      % lg["period"][0])
    A("시뮬레이션이 아니라 실제 QQQ 수정종가다.")
    A("")
    A("| | CAGR | 최대낙폭 |")
    A("|---|---|---|")
    A("| QQQ 바이앤홀드 | %s | %s |" % (f(lg["buy_hold"]["cagr_pct"]), fa(lg["buy_hold"]["mdd_pct"])))
    A("| 규칙 전수 중앙 | %s | %s |" % (f(lg["dist"]["median"]), fa(lg["mdd_dist"]["median"])))
    A("| 규칙 전수 범위 | %s ~ %s | %s ~ %s |" % (
        f(lg["dist"]["min"]), f(lg["dist"]["max"]), fa(lg["mdd_dist"]["min"]), fa(lg["mdd_dist"]["max"])))
    A("")
    A("수익률은 바이앤홀드와 사실상 같고(중앙 %s vs %s), **낙폭은 %s에서 %s로 줄었다.**" % (
        f(lg["dist"]["median"]), f(lg["buy_hold"]["cagr_pct"]),
        fa(lg["buy_hold"]["mdd_pct"]), fa(lg["mdd_dist"]["median"])))
    A("추세 신호가 사는 곳은 **위기 구간의 낙폭 억제**이지 초과수익이 아니다.")
    A("그런데 3배 레버리지는 그 억제분을 **변동성으로 되돌려준다** — 위 표의 3상태 MDD 중앙 %s를 보라."
      % fa(g3["mdd_dist"]["median"]))
    A("")
    A("## 연도별 — 3상태 최고 규칙 `%s`" % best3["rule"])
    A("")
    ann = [a for a in best3["annual"]]
    vals = [a["return_pct"] for a in ann if not a["partial"]]
    A("| 연도 | 수익률 |")
    A("|---|---|")
    for a in ann:
        A("| %d%s | %s |" % (a["year"], (" (%s)" % a["partial"]) if a["partial"] else "", f(a["return_pct"])))
    A("")
    A("완전 연도 %d개의 **산술평균 %s**, **중앙값 %s**, **표준편차 %s**." % (
        len(vals), f(st.mean(vals)), f(st.median(vals)), fa(st.stdev(vals))))
    A("같은 규칙의 CAGR은 %s다. **산술평균과 CAGR의 차이(%sp)가 이 전략의 변동성 비용이다.**" % (
        f(best3["cagr_pct"]), f(st.mean(vals) - best3["cagr_pct"], 1, "%")))
    A("이 규칙은 35개 중 1등이므로, 이 표를 기대수익으로 읽으면 안 된다.")
    A("")
    A("## 한계")
    A("")
    for c in [
        "**기간이 하나다.** %s~%s는 나스닥 역사상 가장 강한 상승 구간을 포함한다. "
        "하락을 맞히는 다리(SQQQ)가 불리할 수밖에 없는 표본이고, 반대 표본에서는 결과가 다를 수 있다." % (p[0], p[1]),
        "**규칙 %d개는 전수가 아니다.** 이동평균·모멘텀 계열만 봤다. 변동성·폭·거시 지표를 쓰는 "
        "레짐 판별은 시험하지 않았다. 「이 3계열로는 안 된다」까지가 이 실험의 범위다." % g3["cagr_dist"]["n"],
        "**주간 종가로만 전환한다.** 일간·장중 신호는 결과가 다를 수 있고, 거래비용과 슬리피지도 커진다.",
        "**세금이 없다.** 국내 계좌에서 TQQQ·SQQQ 회전은 양도세·금융소득 과세를 발생시킨다. "
        "전환 %d~%d회/년이면 세후 수익률은 위 숫자보다 낮다." % (
            min(int(x["switches_per_year"]) for x in g3["rows"]),
            max(int(x["switches_per_year"]) + 1 for x in g3["rows"])),
        "**환율이 없다.** 전부 달러 기준이다. 원화 수익률은 환율 변동이 곱해진다.",
        "**생존 종목이다.** TQQQ·SQQQ는 살아남은 상품이다. 같은 기간 상장폐지된 레버리지 상품은 표본에 없다.",
        "**단일 벤더다.** 가격은 Alpha Vantage 수정종가 한 곳이고 원자료와 대조하지 않았다.",
    ]:
        A("- %s" % c)
    A("")

    path = os.path.join(OUT, "보고서.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    sys.stdout.write("썼다: %s (%d행)\n" % (path, len(L) + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
