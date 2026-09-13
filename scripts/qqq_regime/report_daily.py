# -*- coding: utf-8 -*-
"""experiment_daily.json → 보고서-일간전환.md"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "출력")


def f(x, nd=2, suf="%"):
    return "결측" if x is None else ("%+.*f%s" % (nd, x, suf))


def fa(x, nd=2, suf="%"):
    return "결측" if x is None else ("%.*f%s" % (nd, x, suf))


def main():
    with open(os.path.join(OUT, "experiment_daily.json"), encoding="utf-8") as fh:
        r = json.load(fh)
    A, B, C = r["A"], r["B"], r["crisis"]
    ps, pbs = A["pair_summary"], B["pair_summary"]
    n = r["n_rules"]
    L = []
    P = L.append

    P("# 일간 전환 vs 주간 전환 — 2상태(TQQQ/현금)")
    P("")
    P("생성 %s · 규칙 %d쌍 · 기본 전환비용 %.0fbp" % (r["generated_at"], n, r["cost_bps"]))
    P("")
    P("> **실험 기록이다. 투자 판정이 아니다.** 어드바이저 프로토콜·판정기록부와 무관하다.")
    P("")
    P("## 질문")
    P("")
    P("2상태 주간 실험에서 닷컴 구간 손실이 −54%였다. 주간 종가로만 전환하니 급락을 며칠씩 맞고 나간다.")
    P("**매일 전환하면 그게 줄어드는가?**")
    P("")
    P("## 답 — 아니다. 더 나빠진다")
    P("")
    P("| 구간 | 전환 | CAGR 중앙 | 최대낙폭 중앙 | MAR 중앙 | 전환 횟수 |")
    P("|---|---|---|---|---|---|")
    for key, lab in (("A", "A. 2010~2026 (실제 TQQQ)"), ("B", "B. 2000~2026 (시뮬 TQQQ)")):
        g = r[key]
        P("| **%s** | 주간 | **%s** | **%s** | %.3f | %.1f회/년 |" % (
            lab, f(g["weekly"]["cagr"]["median"]), fa(g["weekly"]["mdd"]["median"]),
            g["weekly"]["mar"]["median"], g["weekly"]["sw"]["median"]))
        P("| | 일간 | %s | %s | %.3f | %.1f회/년 |" % (
            f(g["daily"]["cagr"]["median"]), fa(g["daily"]["mdd"]["median"]),
            g["daily"]["mar"]["median"], g["daily"]["sw"]["median"]))
    P("")
    P("**두 구간 모두 일간이 수익률도 낮고 낙폭도 깊다.** 전환 횟수만 약 2배가 된다.")
    P("붕괴가 들어간 구간 B에서 차이가 특히 크다 — CAGR %s → %s, 낙폭 %s → %s." % (
        f(B["weekly"]["cagr"]["median"]), f(B["daily"]["cagr"]["median"]),
        fa(B["weekly"]["mdd"]["median"]), fa(B["daily"]["mdd"]["median"])))
    P("")
    P("## 짝 비교 — 전환 주기 효과만 분리한다")
    P("")
    P("규칙 %d개를 **길이가 같은 짝**으로 묶었다 (1주 = 5거래일). 예: 주간 `sma40_b0`(40주) ↔ 일간 `sma200_b0`(200일)." % n)
    P("같은 달력 길이·같은 구간·같은 비용이므로 **바뀐 것은 전환 주기뿐**이다.")
    P("")
    P("| 구간 | 일간이 CAGR 우세 | 일간이 낙폭 우세 | CAGR 차 중앙 | 낙폭 개선 중앙 |")
    P("|---|---|---|---|---|")
    P("| A. 2010~2026 | %d / %d | %d / %d | %sp | %sp |" % (
        ps["daily_better_cagr"], ps["n"], ps["daily_better_mdd"], ps["n"],
        f(ps["median_d_cagr"]), f(ps["median_d_mdd"])))
    P("| B. 2000~2026 | %d / %d | %d / %d | %sp | %sp |" % (
        pbs["daily_better_cagr"], pbs["n"], pbs["daily_better_mdd"], pbs["n"],
        f(pbs["median_d_cagr"]), f(pbs["median_d_mdd"])))
    P("")
    P("(낙폭 개선은 **양수면 일간이 얕다**는 뜻이다.)")
    P("")
    P("## 비용 때문인가, 신호 때문인가 — 둘 다인데 구간마다 다르다")
    P("")
    P("| 전환비용 | A 일간 | A 주간 | A 차 | B 일간 | B 주간 | B 차 |")
    P("|---|---|---|---|---|---|---|")
    for k in sorted(A["cost"], key=lambda x: float(x[:-2])):
        a, b = A["cost"][k], B["cost"][k]
        P("| %s | %s | %s | %sp | %s | %s | %sp |" % (
            k, f(a["daily_median"]), f(a["weekly_median"]), f(a["daily_median"] - a["weekly_median"]),
            f(b["daily_median"]), f(b["weekly_median"]), f(b["daily_median"] - b["weekly_median"])))
    P("")
    a0 = A["cost"]["0bp"]
    b0 = B["cost"]["0bp"]
    P("**구간 A에서는 비용이 원인이다.** 비용 0에서는 일간이 오히려 %sp 앞선다(%s vs %s)."
      % (f(a0["daily_median"] - a0["weekly_median"]), f(a0["daily_median"]), f(a0["weekly_median"])))
    P("비용이 10bp만 붙어도 %sp로 뒤집힌다 — 전환이 2배이므로 비용도 2배 물린다."
      % f(A["cost"]["10bp"]["daily_median"] - A["cost"]["10bp"]["weekly_median"]))
    P("")
    P("**구간 B에서는 비용이 아니다.** 비용 0에서도 일간이 %sp 뒤진다(%s vs %s)."
      % (f(b0["daily_median"] - b0["weekly_median"]), f(b0["daily_median"]), f(b0["weekly_median"])))
    P("붕괴 구간에서 **일간 신호가 톱질(whipsaw)에 걸린다** — 저점에서 팔고 반등에서 사기를 반복한다.")
    P("주간 종가는 그 잡음을 걸러 준다. 이것이 이 실험의 핵심 결과다.")
    P("")
    P("## 위기 구간 — 짝지은 규칙으로만 비교")
    P("")
    P("> 서로 다른 규칙끼리 비교하면 「전환 주기 효과」와 「규칙 효과」가 섞인다. 아래는 전부 같은 길이의 짝이다.")
    P("")
    for pr in C["probes"]:
        P("### %s — 주간 `%s` ↔ 일간 `%s`" % (pr["label"], pr["weekly_rule"], pr["daily_rule"]))
        P("")
        P("| 구간 | 주간 | 주간 MDD | 전환 | 일간 | 일간 MDD | 전환 | TQQQ 보유 |")
        P("|---|---|---|---|---|---|---|---|")
        for w in pr["windows"]:
            P("| %s | **%s** | %s | %d | **%s** | %s | %d | %s |" % (
                w["name"], f(w["weekly_total_pct"]), fa(w["weekly_mdd_pct"]), w["weekly_switches"],
                f(w["daily_total_pct"]), fa(w["daily_mdd_pct"]), w["daily_switches"],
                f(w["tqqq_total_pct"])))
        P("")
    dot = C["probes"][1]["windows"][0]
    cov = [w for w in C["probes"][1]["windows"] if "코로나" in w["name"]][0]
    P("**닷컴에서 일간이 무너진다.** 200일선 짝에서 주간 %s vs 일간 %s — %sp 차이다."
      % (f(dot["weekly_total_pct"]), f(dot["daily_total_pct"]),
         f(dot["daily_total_pct"] - dot["weekly_total_pct"])))
    P("전환 횟수가 %d회 vs %d회다. 2년 반 동안 지수가 갈지자로 흘러내리면서 일간 신호가 계속 톱질당했다."
      % (dot["weekly_switches"], dot["daily_switches"]))
    P("")
    P("**반대로 2020 코로나에서는 일간이 이긴다** — 주간 %s vs 일간 %s."
      % (f(cov["weekly_total_pct"]), f(cov["daily_total_pct"])))
    P("한 달 만에 꺾고 한 달 만에 되돌린 **V자 급락**이라 빠른 신호가 유리했다.")
    P("")
    P("**규칙은 이렇게 읽는다: 일간 전환은 빠른 급락에 강하고, 길게 끄는 하락장에 약하다.**")
    P("그리고 나스닥 3배를 죽이는 것은 V자 급락이 아니라 **길게 끄는 하락장**이다.")
    P("")
    P("## 표본외 — 일간에서도 규칙 고르기는 안 된다")
    P("")
    sp = A["split"]
    P("| 항목 | 값 |")
    P("|---|---|")
    P("| 표본내 (%s ~ %s) 최고 | `%s` %s |" % (sp["is_period"][0], sp["is_period"][1],
                                               sp["best_is_rule"], f(sp["best_is_cagr"])))
    P("| 그 규칙의 표본외 | %s (**%d/%d위**) |" % (f(sp["oos_cagr_of_that"]), sp["oos_rank_of_that"], n))
    P("| 순위상관 | %+.3f |" % sp["rank_corr"])
    P("| 표본내 top5 중 표본외 top10 잔류 | **%d / 5** |" % sp["top5_still_top10"])
    P("| 표본외 TQQQ 그냥 보유 | %s |" % f(sp["oos_bench_tqqq"]))
    P("")
    P("주간 실험(순위상관 +0.637 · 잔류 1/5)과 거의 같다. 전환 주기를 바꿔도 **규칙 선택의 불안정성은 그대로**다.")
    P("")
    P("## 벤치마크 대비")
    P("")
    bt, bq = A["bench_tqqq"], A["bench_qqq"]
    P("| 구간 A (2010~2026) | CAGR | 최대낙폭 | MAR |")
    P("|---|---|---|---|")
    P("| TQQQ 그냥 보유 | %s | %s | %.3f |" % (f(bt["cagr_pct"]), fa(bt["mdd_pct"]), bt["mar"]))
    P("| QQQ 그냥 보유 | %s | %s | %.3f |" % (f(bq["cagr_pct"]), fa(bq["mdd_pct"]), bq["mar"]))
    P("| 일간 규칙 중앙 | %s | %s | %.3f |" % (
        f(A["daily"]["cagr"]["median"]), fa(A["daily"]["mdd"]["median"]), A["daily"]["mar"]["median"]))
    P("")
    P("TQQQ 보유보다 나은 일간 규칙: CAGR **%d/%d**, MAR **%d/%d**."
      % (A["beat_tqqq_cagr_daily"], n, A["beat_tqqq_mar_daily"], n))
    P("")
    P("## 한계")
    P("")
    for c in [
        "**일중 가격을 쓰지 않는다.** 종가로만 전환한다. 장중 손절·역지정가는 결과가 다를 수 있고, "
        "이 실험은 그것을 시험하지 않았다.",
        "**슬리피지를 비용에 뭉뚱그렸다.** 실제로는 급락일에 스프레드가 벌어진다 — 일간 전환이 불리해지는 방향이고, "
        "50bp 시나리오가 그 상한 근처다.",
        "**구간 B는 시뮬레이션이다.** 다만 전환 횟수(톱질의 직접 증거)는 모형과 무관하게 관측된다.",
        "**세금이 없다.** 전환 %.1f회/년이면 국내 계좌 양도세가 크게 붙는다. 일간 전환이 특히 불리하다."
        % A["daily"]["sw"]["median"],
        "**환율이 없다.** 전부 달러 기준이다.",
        "**배당 반영 시점이 주 단위다.** 일봉 총수익은 주간 factor로 복원했으므로 배당 한 건의 반영이 "
        "최대 4거래일 밀린다. 금요일마다 수정종가와 정확히 일치한다 (오차 1e-8%).",
    ]:
        P("- %s" % c)
    P("")
    P("## 규칙 전수 — 구간 A 짝 비교 (주간 CAGR 내림차순)")
    P("")
    P("| 주간 규칙 | 일간 짝 | 주간 CAGR | 일간 CAGR | 차 | 주간 MDD | 일간 MDD | 주간 전환 | 일간 전환 |")
    P("|---|---|---|---|---|---|---|---|---|")
    for p in sorted(A["pairs"], key=lambda x: -x["cagr_w"]):
        P("| `%s` | `%s` | %s | %s | %s | %s | %s | %.1f | %.1f |" % (
            p["weekly"], p["daily"], f(p["cagr_w"]), f(p["cagr_d"]), f(p["d_cagr"]),
            fa(p["mdd_w"]), fa(p["mdd_d"]), p["sw_w"], p["sw_d"]))
    P("")

    path = os.path.join(OUT, "보고서-일간전환.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    sys.stdout.write("썼다: %s (%d행)\n" % (path, len(L) + 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
